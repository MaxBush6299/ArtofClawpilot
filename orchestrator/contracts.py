from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class StringEnum(str, Enum):
    pass


class FailureStage(StringEnum):
    PRE_RUN = "pre_run"
    CURATOR = "curator"
    CRITIC = "critic"
    ARTIST = "artist"
    PUBLISH = "publish"


class FailureCode(StringEnum):
    AUTH = "auth_failed"
    CALL_BUDGET = "call_budget_exceeded"
    CONFIG = "config_invalid"
    DEPLOYMENT = "deployment_not_found"
    CONTENT_FILTERED = "content_filtered"
    MALFORMED_OUTPUT = "malformed_model_output"
    VALIDATION = "validation_failed"
    API = "api_error"
    GENERATION = "foundry_generation_failed"
    RESPONSE_SHAPE = "response_shape_invalid"


class OutcomeKind(StringEnum):
    PUBLISH = "publish"
    SKIP = "skip"


@dataclass(slots=True)
class ReasoningModelConfig:
    endpoint: str
    deployment: str
    api_version: str
    max_completion_tokens: int = 4_000
    reasoning_effort: str = "medium"


@dataclass(slots=True)
class ImageSettings:
    width: int = 1024
    height: int = 1024


@dataclass(slots=True)
class ImageModelConfig:
    endpoint: str
    deployment: str
    api_version: str | None = None
    settings: ImageSettings = field(default_factory=ImageSettings)


@dataclass(slots=True)
class RuntimeConfig:
    repo_owner: str
    repo_name: str
    branch: str
    run_date: str
    run_id: str
    reasoning_model: ReasoningModelConfig
    image_model: ImageModelConfig


@dataclass(slots=True)
class GalleryImageRecord:
    id: str
    title: str
    path: str
    created_at: str
    artist_note: str
    prompt_summary: str | None = None
    criticism: str | None = None
    run_date: str | None = None
    run_id: str | None = None
    model: str | None = None
    reasoning_model: str | None = None
    slug: str | None = None
    prompt: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GalleryImageRecord":
        return cls(
            id=raw["id"],
            title=raw["title"],
            path=raw["path"],
            created_at=raw["createdAt"],
            artist_note=raw["artistNote"],
            prompt_summary=raw.get("promptSummary"),
            criticism=raw.get("criticism"),
            run_date=raw.get("runDate"),
            run_id=raw.get("runId"),
            model=raw.get("model"),
            reasoning_model=raw.get("reasoningModel"),
            slug=raw.get("slug"),
            prompt=raw.get("prompt"),
        )

    def effective_run_date(self) -> str:
        return self.run_date or self.created_at[:10]
    
    def effective_run_id(self) -> str:
        return self.run_id or self.id

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "path": self.path,
            "createdAt": self.created_at,
            "artistNote": self.artist_note,
            "criticism": self.criticism,
        }
        if self.slug is not None:
            payload["slug"] = self.slug
        if self.prompt is not None:
            payload["prompt"] = self.prompt
        if self.prompt_summary is not None:
            payload["promptSummary"] = self.prompt_summary
        if self.run_date is not None:
            payload["runDate"] = self.run_date
        if self.run_id is not None:
            payload["runId"] = self.run_id
        if self.model is not None:
            payload["model"] = self.model
        if self.reasoning_model is not None:
            payload["reasoningModel"] = self.reasoning_model
        return payload


@dataclass(slots=True)
class GalleryRoom:
    id: str
    name: str
    theme: str
    images: list[GalleryImageRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GalleryRoom":
        return cls(
            id=raw["id"],
            name=raw["name"],
            theme=raw.get("theme", ""),
            images=[GalleryImageRecord.from_dict(image) for image in raw.get("images", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "theme": self.theme,
            "images": [image.to_dict() for image in self.images],
        }


@dataclass(slots=True)
class SkipError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SkipError":
        return cls(
            code=raw["code"],
            message=raw["message"],
            details=dict(raw.get("details", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(slots=True)
class SkipRecord:
    id: str
    run_date: str
    run_id: str
    stage: str
    reason_code: str
    message: str
    created_at: str
    retryable: bool
    error: SkipError | None = None
    creative_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SkipRecord":
        run_id = raw.get("runId")
        if run_id is None:
            run_id = raw["id"]
        return cls(
            id=raw["id"],
            run_date=raw["runDate"],
            run_id=run_id,
            stage=raw["stage"],
            reason_code=raw["reasonCode"],
            message=raw["message"],
            created_at=raw["createdAt"],
            retryable=bool(raw["retryable"]),
            error=SkipError.from_dict(raw["error"]) if isinstance(raw.get("error"), dict) else None,
            creative_context=dict(raw.get("creativeContext", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "runDate": self.run_date,
            "runId": self.run_id,
            "stage": self.stage,
            "reasonCode": self.reason_code,
            "message": self.message,
            "createdAt": self.created_at,
            "retryable": self.retryable,
        }
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        if self.creative_context:
            payload["creativeContext"] = self.creative_context
        return payload


@dataclass(slots=True)
class GalleryState:
    version: int
    rooms: list[GalleryRoom] = field(default_factory=list)
    skipped: list[SkipRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GalleryState":
        return cls(
            version=raw.get("version", 1),
            rooms=[GalleryRoom.from_dict(room) for room in raw.get("rooms", [])],
            skipped=[SkipRecord.from_dict(skip) for skip in raw.get("skipped", [])],
        )

    def latest_image(self) -> GalleryImageRecord | None:
        images = [image for room in self.rooms for image in room.images]
        if not images:
            return None
        return max(images, key=lambda image: (image.effective_run_date(), image.created_at, image.id))

    def find_room(self, room_id: str) -> GalleryRoom | None:
        for room in self.rooms:
            if room.id == room_id:
                return room
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "rooms": [room.to_dict() for room in self.rooms],
            "skipped": [skip.to_dict() for skip in self.skipped],
        }


@dataclass(slots=True)
class CritiqueEntry:
    id: str
    title: str
    date: str
    image_ref: str
    themes: list[str]
    body: str
    suggestion: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CritiqueEntry":
        return cls(
            id=raw["id"],
            title=raw["title"],
            date=raw["date"],
            image_ref=raw["imageRef"],
            themes=list(raw.get("themes", [])),
            body=raw["body"],
            suggestion=raw["suggestion"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "imageRef": self.image_ref,
            "themes": self.themes,
            "body": self.body,
            "suggestion": self.suggestion,
        }


@dataclass(slots=True)
class CritiquesState:
    entries: list[CritiqueEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CritiquesState":
        return cls(entries=[CritiqueEntry.from_dict(entry) for entry in raw.get("entries", [])])

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self.entries]}


@dataclass(slots=True)
class NextBrief:
    day: int
    target_room: str
    style_request: str | None
    notes: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "NextBrief":
        return cls(
            day=int(raw["day"]),
            target_room=raw["targetRoom"],
            style_request=raw.get("styleRequest"),
            notes=raw["notes"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "targetRoom": self.target_room,
            "styleRequest": self.style_request,
            "notes": self.notes,
        }


@dataclass(slots=True)
class RunContext:
    run_date: str
    run_id: str
    started_at: str
    repo_root: str
    trace_id: str


@dataclass(slots=True)
class ReasoningUsage:
    role: str
    stage: str
    deployment: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    response_id: str | None = None
    provider_model: str | None = None
    created: int | None = None
    system_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RoleFailure:
    stage: FailureStage
    reason_code: FailureCode
    message: str
    retryable: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_skip_record(
        self,
        run_date: str,
        run_id: str,
        created_at: str,
        *,
        creative_context: dict[str, Any] | None = None,
    ) -> SkipRecord:
        return SkipRecord(
            id=f"skip-{run_id}",
            run_date=run_date,
            run_id=run_id,
            stage=self.stage.value,
            reason_code=self.reason_code.value,
            message=self.message,
            created_at=created_at,
            retryable=self.retryable,
            error=SkipError(code=self.reason_code.value, message=self.message, details=self.details),
            creative_context=creative_context or {},
        )


@dataclass(slots=True)
class CuratorPlan:
    target_room_id: str
    style_request: str | None
    notes: str
    artist_brief: str
    carry_forward: dict[str, Any] = field(default_factory=dict)
    usage: ReasoningUsage | None = None


@dataclass(slots=True)
class CriticReview:
    critique: CritiqueEntry
    pull_quote: str
    usage: ReasoningUsage | None = None


@dataclass(slots=True)
class ArtistPromptPackage:
    title: str
    prompt: str
    artist_note: str
    prompt_summary: str
    reviewed_prompt: str | None = None
    review_status: str | None = None
    generation: ImageSettings = field(default_factory=ImageSettings)
    safety_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ArtistPromptPackage":
        generation = raw.get("generation", {})
        reviewed_prompt = raw.get("reviewedPrompt") or raw.get("prompt")
        return cls(
            title=raw["title"],
            prompt=raw.get("prompt") or reviewed_prompt,
            artist_note=raw["artistNote"],
            prompt_summary=raw["promptSummary"],
            reviewed_prompt=reviewed_prompt,
            review_status=raw.get("reviewStatus"),
            generation=ImageSettings(
                width=int(generation.get("width", 1024)),
                height=int(generation.get("height", 1024)),
            ),
            safety_notes=list(raw.get("safetyNotes", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "title": self.title,
            "prompt": self.prompt,
            "artistNote": self.artist_note,
            "promptSummary": self.prompt_summary,
            "generation": {
                "width": self.generation.width,
                "height": self.generation.height,
            },
            "safetyNotes": self.safety_notes,
        }
        if self.reviewed_prompt is not None:
            payload["reviewedPrompt"] = self.reviewed_prompt
        if self.review_status is not None:
            payload["reviewStatus"] = self.review_status
        return payload


@dataclass(slots=True)
class ArtistReasoningAudit:
    analysis: dict[str, Any]
    draft: dict[str, Any]
    review: dict[str, Any]
    call_count: int
    usage: list[ReasoningUsage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "draft": self.draft,
            "review": self.review,
            "callCount": self.call_count,
            "usage": [item.to_dict() for item in self.usage],
        }


@dataclass(slots=True)
class ArtistResult:
    prompt_package: ArtistPromptPackage
    reasoning_audit: ArtistReasoningAudit


@dataclass(slots=True)
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    model: str
    deployment: str
    response_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PublishOutcome:
    run_date: str
    room_id: str
    image_record: GalleryImageRecord
    image_result: ImageGenerationResult
    asset_repo_path: str
    critique: CritiqueEntry | None = None
    next_brief: NextBrief | None = None
    reasoning_audit: ArtistReasoningAudit | None = None


@dataclass(slots=True)
class SkipOutcome:
    run_date: str
    skip_record: SkipRecord
    critique: CritiqueEntry | None = None
    next_brief: NextBrief | None = None
