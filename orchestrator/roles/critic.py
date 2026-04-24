from __future__ import annotations

from ..contracts import CriticReview, CritiqueEntry, CritiquesState, GalleryImageRecord, RunContext
from ..integrations.foundry import ReasoningClient, ReasoningStepRequest
from ..validation import validate_critic_review
from .parsing import require_string, require_string_list

CRITIC_SYSTEM_PROMPT = """You are the Critic role for Art of Clawpilot.
Return JSON only.
Review the last published piece, produce a newspaper-style critique, and give one concrete suggestion for the next piece."""

CRITIC_RESPONSE_CONTRACT = {
    "title": "string",
    "themes": ["string", "string"],
    "body": "string",
    "suggestion": "string",
    "pullQuote": "single sentence string",
}


class CriticRole:
    def run(
        self,
        *,
        context: RunContext,
        latest_image: GalleryImageRecord,
        critiques: CritiquesState,
        reasoning: ReasoningClient,
    ) -> CriticReview:
        payload, usage = reasoning.complete_json(
            ReasoningStepRequest(
                role="critic",
                stage="critique",
                system_prompt=CRITIC_SYSTEM_PROMPT,
                input_payload={
                    "runDate": context.run_date,
                    "latestImage": latest_image.to_dict(),
                    "priorCritiques": [entry.to_dict() for entry in critiques.entries[-2:]],
                },
                response_contract=CRITIC_RESPONSE_CONTRACT,
            )
        )
        review = CriticReview(
            critique=CritiqueEntry(
                id=latest_image.id,
                title=require_string(payload, "title", role="critic", step="critique"),
                date=context.started_at,
                image_ref=latest_image.path,
                themes=require_string_list(payload, "themes", role="critic", step="critique"),
                body=require_string(payload, "body", role="critic", step="critique"),
                suggestion=require_string(payload, "suggestion", role="critic", step="critique"),
            ),
            pull_quote=require_string(payload, "pullQuote", role="critic", step="critique"),
            usage=usage,
        )
        validate_critic_review(review)
        return review
