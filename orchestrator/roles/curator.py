from __future__ import annotations

from ..contracts import CritiquesState, CuratorPlan, GalleryState, NextBrief, RunContext
from ..integrations.foundry import ReasoningClient, ReasoningStepRequest
from ..validation import validate_curator_plan
from .parsing import optional_object, optional_string, require_string

CURATOR_SYSTEM_PROMPT = """You are the Curator role for Art of Clawpilot.
Return JSON only.
Choose the target room, write a concise style request, and emit an artist brief.
Do not mention tools, git, or file writes."""

CURATOR_RESPONSE_CONTRACT = {
    "targetRoomId": "string room-##",
    "styleRequest": "string or null",
    "notes": "string",
    "artistBrief": "string",
    "carryForward": {"nextDayTheme": "optional string"},
}


class CuratorRole:
    def run(
        self,
        *,
        context: RunContext,
        gallery: GalleryState,
        critiques: CritiquesState,
        previous_brief: NextBrief,
        reasoning: ReasoningClient,
    ) -> CuratorPlan:
        latest_suggestion = critiques.entries[-1].suggestion if critiques.entries else None
        payload, usage = reasoning.complete_json(
            ReasoningStepRequest(
                role="curator",
                stage="curate",
                system_prompt=CURATOR_SYSTEM_PROMPT,
                input_payload={
                    "runDate": context.run_date,
                    "gallery": gallery.to_dict(),
                    "previousBrief": previous_brief.to_dict(),
                    "latestCriticSuggestion": latest_suggestion,
                },
                response_contract=CURATOR_RESPONSE_CONTRACT,
            )
        )
        plan = CuratorPlan(
            target_room_id=require_string(payload, "targetRoomId", role="curator", step="curate"),
            style_request=optional_string(payload, "styleRequest", role="curator", step="curate"),
            notes=require_string(payload, "notes", role="curator", step="curate"),
            artist_brief=require_string(payload, "artistBrief", role="curator", step="curate"),
            carry_forward=optional_object(payload, "carryForward", role="curator", step="curate"),
            usage=usage,
        )
        validate_curator_plan(plan)
        return plan
