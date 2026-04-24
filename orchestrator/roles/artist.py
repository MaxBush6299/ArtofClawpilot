from __future__ import annotations

from ..contracts import ArtistPromptPackage, ArtistReasoningAudit, ArtistResult, CriticReview, CuratorPlan, FailureCode, GalleryRoom, RunContext
from ..integrations.foundry import ReasoningClient, ReasoningStepRequest
from ..validation import ContractValidationError, validate_artist_result
from .parsing import optional_string_list, parse_generation_settings, require_object, require_string, require_string_list

ANALYZE_PROMPT = """You are the Artist analysis step for Art of Clawpilot.
Return JSON only.
Analyze the curator brief, room context, and optional critic suggestion.
Do not draft the final image prompt yet."""

DRAFT_PROMPT = """You are the Artist drafting step for Art of Clawpilot.
Return JSON only.
Produce the candidate image prompt package for MAI-Image-2e."""

REVIEW_PROMPT = """You are the Artist review step for Art of Clawpilot.
Return JSON only.
Review the candidate prompt package, tighten it if needed, and finalize the package for one MAI-Image-2e call."""

ANALYZE_CONTRACT = {
    "constraints": ["string"],
    "visualTargets": ["string"],
    "riskChecks": ["string"],
}

DRAFT_CONTRACT = {
    "title": "string",
    "prompt": "40-120 word string",
    "artistNote": "2-4 sentence string",
    "promptSummary": "1-2 sentence string",
    "generation": {"width": 1024, "height": 1024},
    "safetyNotes": ["string"],
}

REVIEW_CONTRACT = {
    "promptPackage": {
        **DRAFT_CONTRACT,
        "reviewedPrompt": "40-120 word string",
        "reviewStatus": "final-reviewed",
    },
    "reviewNotes": ["string"],
}


class ArtistRole:
    def run(
        self,
        *,
        context: RunContext,
        curator_plan: CuratorPlan,
        room: GalleryRoom,
        critic_review: CriticReview | None,
        reasoning: ReasoningClient,
    ) -> ArtistResult:
        audit_usage = []
        expected_stages: tuple[str, ...] = ("analyze", "draft", "review")

        def complete_stage(*, stage: str, system_prompt: str, input_payload: dict[str, object], response_contract: dict[str, object]):
            if len(audit_usage) >= len(expected_stages):
                raise ContractValidationError(
                    category="role_output",
                    code="artist_call_budget_exceeded",
                    message="Artist reasoning flow exceeded the 3-call budget.",
                    details={"reasonCode": FailureCode.CALL_BUDGET.value, "callCount": len(audit_usage)},
                )
            expected_stage = expected_stages[len(audit_usage)]
            if stage != expected_stage:
                raise ContractValidationError(
                    category="role_output",
                    code="artist_stage_order_invalid",
                    message="Artist reasoning flow must follow analyze -> draft -> review.",
                    details={"expectedStage": expected_stage, "actualStage": stage},
                )
            payload, usage = reasoning.complete_json(
                ReasoningStepRequest(
                    role="artist",
                    stage=stage,
                    system_prompt=system_prompt,
                    input_payload=input_payload,
                    response_contract=response_contract,
                )
            )
            audit_usage.append(usage)
            return payload

        try:
            analysis_payload = complete_stage(
                stage="analyze",
                system_prompt=ANALYZE_PROMPT,
                input_payload={
                    "runDate": context.run_date,
                    "curatorPlan": {
                        "targetRoomId": curator_plan.target_room_id,
                        "styleRequest": curator_plan.style_request,
                        "notes": curator_plan.notes,
                        "artistBrief": curator_plan.artist_brief,
                    },
                    "room": room.to_dict(),
                    "criticSuggestion": critic_review.critique.suggestion if critic_review else None,
                },
                response_contract=ANALYZE_CONTRACT,
            )
            analysis = {
                "constraints": require_string_list(analysis_payload, "constraints", role="artist", step="analyze"),
                "visualTargets": require_string_list(analysis_payload, "visualTargets", role="artist", step="analyze"),
                "riskChecks": require_string_list(analysis_payload, "riskChecks", role="artist", step="analyze"),
            }

            draft_payload = complete_stage(
                stage="draft",
                system_prompt=DRAFT_PROMPT,
                input_payload={
                    "analysis": analysis,
                    "curatorPlan": {
                        "styleRequest": curator_plan.style_request,
                        "artistBrief": curator_plan.artist_brief,
                    },
                    "criticSuggestion": critic_review.critique.suggestion if critic_review else None,
                },
                response_contract=DRAFT_CONTRACT,
            )
            draft_generation = parse_generation_settings(draft_payload, role="artist", step="draft")
            draft = {
                "title": require_string(draft_payload, "title", role="artist", step="draft"),
                "prompt": require_string(draft_payload, "prompt", role="artist", step="draft"),
                "artistNote": require_string(draft_payload, "artistNote", role="artist", step="draft"),
                "promptSummary": require_string(draft_payload, "promptSummary", role="artist", step="draft"),
                "generation": {
                    "width": draft_generation.width,
                    "height": draft_generation.height,
                },
                "safetyNotes": optional_string_list(draft_payload, "safetyNotes", role="artist", step="draft"),
            }

            review_payload = complete_stage(
                stage="review",
                system_prompt=REVIEW_PROMPT,
                input_payload={
                    "analysis": analysis,
                    "draft": draft,
                },
                response_contract=REVIEW_CONTRACT,
            )
            if getattr(reasoning, "force_artist_budget_overflow", False):
                complete_stage(
                    stage="overflow-check",
                    system_prompt=REVIEW_PROMPT,
                    input_payload={
                        "analysis": analysis,
                        "draft": draft,
                    },
                    response_contract=REVIEW_CONTRACT,
                )
            review_prompt_package = require_object(review_payload.get("promptPackage"), role="artist", step="review", label="promptPackage")
            review = {
                "promptPackage": review_prompt_package,
                "reviewNotes": optional_string_list(review_payload, "reviewNotes", role="artist", step="review"),
            }
            reviewed_generation = parse_generation_settings(review_prompt_package, role="artist", step="review")
            prompt_package = ArtistPromptPackage(
                title=require_string(review_prompt_package, "title", role="artist", step="review"),
                prompt=require_string(review_prompt_package, "reviewedPrompt", role="artist", step="review"),
                reviewed_prompt=require_string(review_prompt_package, "reviewedPrompt", role="artist", step="review"),
                artist_note=require_string(review_prompt_package, "artistNote", role="artist", step="review"),
                prompt_summary=require_string(review_prompt_package, "promptSummary", role="artist", step="review"),
                review_status=require_string(review_prompt_package, "reviewStatus", role="artist", step="review"),
                generation=reviewed_generation,
                safety_notes=optional_string_list(review_prompt_package, "safetyNotes", role="artist", step="review"),
            )

            result = ArtistResult(
                prompt_package=prompt_package,
                reasoning_audit=ArtistReasoningAudit(
                    analysis=analysis,
                    draft=draft,
                    review=review,
                    call_count=len(audit_usage),
                    usage=audit_usage,
                ),
            )
            validate_artist_result(result)
            return result
        except ContractValidationError as exc:
            exc.details.setdefault("callCount", len(audit_usage))
            exc.details.setdefault("usageStages", [usage.stage for usage in audit_usage])
            raise
