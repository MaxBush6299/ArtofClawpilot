from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    ArtistPromptPackage,
    ArtistResult,
    CriticReview,
    CritiquesState,
    CuratorPlan,
    FailureCode,
    GalleryImageRecord,
    GalleryState,
    ImageSettings,
    NextBrief,
    PublishOutcome,
    RuntimeConfig,
    SkipOutcome,
)

ROOM_ID_RE = re.compile(r"^room-\d{2}$")
RUN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PUBLIC_ASSET_RE = re.compile(r"^/gallery/\d{4}/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.png$")
REPO_ASSET_RE = re.compile(r"^public[\\/]+gallery[\\/]+\d{4}[\\/]+\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.png$")
SKIP_STAGE_VALUES = {"curator", "critic", "artist", "publish"}
MAI_MIN_DIMENSION = 768
MAI_MAX_TOTAL_PIXELS = 1_048_576
ROOM_IMAGE_CAPACITY = 5
IMAGE_FAILURE_REASON_CODES = {
    FailureCode.CONTENT_FILTERED.value,
    FailureCode.GENERATION.value,
    FailureCode.RESPONSE_SHAPE.value,
}


@dataclass(slots=True)
class ContractValidationError(ValueError):
    category: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.category}:{self.code}: {self.message}"


@dataclass(slots=True)
class PreRunValidationResult:
    existing_outcome: str | None = None


def _raise(category: str, code: str, message: str, **details: Any) -> None:
    raise ContractValidationError(category=category, code=code, message=message, details=details)


def _require(condition: bool, category: str, code: str, message: str, **details: Any) -> None:
    if not condition:
        _raise(category, code, message, **details)


def validate_runtime_config(config: RuntimeConfig) -> None:
    _require(bool(config.repo_owner), "config", "repo_owner_missing", "repo_owner is required")
    _require(bool(config.repo_name), "config", "repo_name_missing", "repo_name is required")
    _require(bool(config.branch), "config", "branch_missing", "branch is required")
    _require(RUN_DATE_RE.match(config.run_date) is not None, "config", "run_date_invalid", "run_date must be YYYY-MM-DD")
    _require(bool(config.reasoning_model.endpoint), "config", "reasoning_endpoint_missing", "reasoning endpoint is required")
    _require(bool(config.reasoning_model.deployment), "config", "reasoning_deployment_missing", "reasoning deployment is required")
    _require(bool(config.reasoning_model.api_version), "config", "reasoning_api_version_missing", "reasoning api version is required")
    _require(bool(config.image_model.endpoint), "config", "image_endpoint_missing", "image endpoint is required")
    _require(bool(config.image_model.deployment), "config", "image_deployment_missing", "image deployment is required")
    validate_image_settings(config.image_model.settings, category="config", code_prefix="image")


def validate_image_settings(settings: ImageSettings, *, category: str, code_prefix: str) -> None:
    _require(settings.width >= MAI_MIN_DIMENSION, category, f"{code_prefix}_width_invalid", "width must be at least 768", width=settings.width)
    _require(settings.height >= MAI_MIN_DIMENSION, category, f"{code_prefix}_height_invalid", "height must be at least 768", height=settings.height)
    _require(
        settings.width * settings.height <= MAI_MAX_TOTAL_PIXELS,
        category,
        f"{code_prefix}_dimensions_invalid",
        "width * height must be <= 1,048,576 for MAI image generation",
        width=settings.width,
        height=settings.height,
    )


def validate_gallery_state(state: GalleryState) -> None:
    _require(state.version == 1, "pre_run", "gallery_version_invalid", "gallery.json version must be 1", version=state.version)
    seen_room_ids: set[str] = set()
    seen_image_ids: set[str] = set()
    seen_run_ids: set[str] = set()
    for room in state.rooms:
        _require(ROOM_ID_RE.match(room.id) is not None, "pre_run", "room_id_invalid", "room id must look like room-01", room_id=room.id)
        _require(room.id not in seen_room_ids, "pre_run", "room_id_duplicate", "duplicate room id", room_id=room.id)
        seen_room_ids.add(room.id)
        _require(
            len(room.images) <= ROOM_IMAGE_CAPACITY,
            "pre_run",
            "room_capacity_exceeded",
            f"rooms may contain at most {ROOM_IMAGE_CAPACITY} images",
            room_id=room.id,
            count=len(room.images),
        )
        for image in room.images:
            validate_existing_image_record(image)
            _require(image.id not in seen_image_ids, "pre_run", "image_id_duplicate", "duplicate image id", image_id=image.id)
            seen_image_ids.add(image.id)
            run_id = image.effective_run_id()
            _require(run_id not in seen_run_ids, "pre_run", "run_id_duplicate", "multiple published images share the same runId", run_id=run_id)
            seen_run_ids.add(run_id)
    seen_skip_ids: set[str] = set()
    for skip in state.skipped:
        validate_skip_record(skip, category="pre_run", require_error=False)
        _require(skip.run_id not in seen_skip_ids, "pre_run", "skip_run_id_duplicate", "duplicate skip runId", run_id=skip.run_id)
        _require(skip.run_id not in seen_run_ids, "pre_run", "run_id_conflict", "runId cannot appear in both image and skip ledgers", run_id=skip.run_id)
        seen_skip_ids.add(skip.run_id)


def validate_existing_image_record(image: GalleryImageRecord) -> None:
    for field_name in ("id", "title", "path", "created_at", "artist_note"):
        _require(bool(getattr(image, field_name)), "pre_run", "image_field_missing", f"image record missing {field_name}", field=field_name, image_id=image.id)
    if image.run_date is not None:
        _require(RUN_DATE_RE.match(image.run_date) is not None, "pre_run", "image_run_date_invalid", "image runDate must be YYYY-MM-DD", image_id=image.id)
    if image.prompt_summary is not None:
        _require(bool(image.prompt_summary.strip()), "pre_run", "image_prompt_summary_invalid", "promptSummary cannot be blank", image_id=image.id)
    _require(image.path.startswith("/gallery/"), "pre_run", "image_path_invalid", "image path must live under /gallery/", image_id=image.id, path=image.path)


def validate_critiques_state(state: CritiquesState) -> None:
    seen_ids: set[str] = set()
    for entry in state.entries:
        _require(entry.id not in seen_ids, "pre_run", "critique_id_duplicate", "duplicate critique id", critique_id=entry.id)
        seen_ids.add(entry.id)
        _require(bool(entry.title), "pre_run", "critique_title_missing", "critique title is required", critique_id=entry.id)
        _require(bool(entry.date), "pre_run", "critique_date_missing", "critique date is required", critique_id=entry.id)
        _require(bool(entry.image_ref), "pre_run", "critique_image_ref_missing", "critique imageRef is required", critique_id=entry.id)
        _require(bool(entry.body), "pre_run", "critique_body_missing", "critique body is required", critique_id=entry.id)
        _require(bool(entry.suggestion), "pre_run", "critique_suggestion_missing", "critique suggestion is required", critique_id=entry.id)


def validate_next_brief(brief: NextBrief) -> None:
    _require(brief.day >= 1, "pre_run", "brief_day_invalid", "next-brief day must be >= 1", day=brief.day)
    _require(ROOM_ID_RE.match(brief.target_room) is not None, "pre_run", "brief_room_invalid", "next-brief targetRoom must look like room-01", target_room=brief.target_room)
    _require(bool(brief.notes.strip()), "pre_run", "brief_notes_missing", "next-brief notes are required")


def resolve_existing_outcome(state: GalleryState, run_date: str, run_id: str) -> str | None:
    for skip in state.skipped:
        if skip.run_id == run_id:
            return "skip"
    for room in state.rooms:
        for image in room.images:
            if image.effective_run_id() == run_id:
                return "publish"
    return None


def validate_pre_run_state(
    *,
    config: RuntimeConfig,
    gallery: GalleryState,
    critiques: CritiquesState,
    next_brief: NextBrief,
) -> PreRunValidationResult:
    validate_runtime_config(config)
    validate_gallery_state(gallery)
    validate_critiques_state(critiques)
    validate_next_brief(next_brief)
    return PreRunValidationResult(existing_outcome=resolve_existing_outcome(gallery, config.run_date, config.run_id))


def ensure_run_id_available(state: GalleryState, run_id: str) -> None:
    for room in state.rooms:
        for image in room.images:
            _require(image.effective_run_id() != run_id, "pre_run", "run_id_already_published", "runId already has a published image", run_id=run_id)
    for skip in state.skipped:
        _require(skip.run_id != run_id, "pre_run", "run_id_already_skipped", "runId already has a skip record", run_id=run_id)


def validate_curator_plan(plan: CuratorPlan) -> None:
    _require(ROOM_ID_RE.match(plan.target_room_id) is not None, "role_output", "curator_room_invalid", "Curator target room is invalid", target_room=plan.target_room_id)
    _require(bool(plan.notes.strip()), "role_output", "curator_notes_missing", "Curator notes are required")
    _require(bool(plan.artist_brief.strip()), "role_output", "curator_artist_brief_missing", "Curator artist brief is required")
    if plan.style_request is not None:
        _require(bool(plan.style_request.strip()), "role_output", "curator_style_request_invalid", "styleRequest cannot be blank when present")


def validate_critic_review(review: CriticReview) -> None:
    _require(bool(review.pull_quote.strip()), "role_output", "critic_pull_quote_missing", "Critic pull quote is required")
    validate_critiques_state(CritiquesState(entries=[review.critique]))


def validate_artist_prompt_package(prompt_package: ArtistPromptPackage) -> None:
    _require(bool(prompt_package.title.strip()), "role_output", "artist_title_missing", "Artist title is required")
    _require(bool(prompt_package.prompt.strip()), "role_output", "artist_prompt_missing", "Artist prompt is required")
    _require(bool(prompt_package.artist_note.strip()), "role_output", "artist_note_missing", "Artist note is required")
    _require(bool(prompt_package.prompt_summary.strip()), "role_output", "artist_prompt_summary_missing", "Artist prompt summary is required")
    _require(
        bool((prompt_package.reviewed_prompt or "").strip()),
        "role_output",
        "artist_reviewed_prompt_missing",
        "Artist reviewedPrompt is required before image generation",
    )
    _require(
        prompt_package.review_status == "final-reviewed",
        "role_output",
        "artist_review_status_invalid",
        "Artist reviewStatus must be final-reviewed before image generation",
        review_status=prompt_package.review_status,
    )
    _require(
        prompt_package.prompt == prompt_package.reviewed_prompt,
        "role_output",
        "artist_prompt_handoff_invalid",
        "Image generation handoff must use the final reviewed prompt package",
    )
    validate_image_settings(prompt_package.generation, category="role_output", code_prefix="artist_generation")


def validate_artist_result(result: ArtistResult) -> None:
    validate_artist_prompt_package(result.prompt_package)
    _require(result.reasoning_audit.call_count == 3, "role_output", "artist_call_count_invalid", "Artist must make exactly 3 reasoning calls", call_count=result.reasoning_audit.call_count)
    _require(len(result.reasoning_audit.usage) == 3, "role_output", "artist_usage_count_invalid", "Artist audit must contain 3 usage entries", usage_count=len(result.reasoning_audit.usage))
    _require(
        [usage.stage for usage in result.reasoning_audit.usage] == ["analyze", "draft", "review"],
        "role_output",
        "artist_usage_order_invalid",
        "Artist audit stages must prove analyze -> draft -> review order",
        usage_stages=[usage.stage for usage in result.reasoning_audit.usage],
    )


def validate_publish_outcome(outcome: PublishOutcome) -> None:
    _require(RUN_DATE_RE.match(outcome.run_date) is not None, "post_run", "publish_run_date_invalid", "publish runDate must be YYYY-MM-DD")
    _require(ROOM_ID_RE.match(outcome.room_id) is not None, "post_run", "publish_room_invalid", "publish room must look like room-01")
    validate_new_image_record(outcome.image_record, expected_run_date=outcome.run_date)
    _require(PUBLIC_ASSET_RE.match(outcome.image_record.path) is not None, "post_run", "publish_public_path_invalid", "published image path must follow /gallery/YYYY/YYYY-MM-DD-slug.png", path=outcome.image_record.path)
    _require(REPO_ASSET_RE.match(outcome.asset_repo_path) is not None, "post_run", "publish_repo_path_invalid", "asset repo path must follow public\\gallery\\YYYY\\YYYY-MM-DD-slug.png", path=outcome.asset_repo_path)
    _require(outcome.image_result.mime_type == "image/png", "post_run", "publish_mime_invalid", "published asset must be image/png", mime_type=outcome.image_result.mime_type)
    _require(len(outcome.image_result.image_bytes) > 0, "post_run", "publish_bytes_missing", "published asset must contain bytes")
    if outcome.critique is not None:
        validate_critiques_state(CritiquesState(entries=[outcome.critique]))
    if outcome.next_brief is not None:
        validate_next_brief(outcome.next_brief)


def validate_skip_outcome(outcome: SkipOutcome) -> None:
    validate_skip_record(outcome.skip_record, category="post_run", require_error=True)
    _require(outcome.skip_record.run_date == outcome.run_date, "post_run", "skip_run_date_mismatch", "skip record runDate must match outcome runDate")
    if outcome.skip_record.reason_code in IMAGE_FAILURE_REASON_CODES:
        _require(
            bool(outcome.skip_record.creative_context),
            "post_run",
            "skip_creative_context_missing",
            "image-generation skips must include creativeContext for later review",
            reason_code=outcome.skip_record.reason_code,
        )
    if outcome.critique is not None:
        validate_critiques_state(CritiquesState(entries=[outcome.critique]))
    if outcome.next_brief is not None:
        validate_next_brief(outcome.next_brief)


def validate_publish_state_transition(*, before: GalleryState, after: GalleryState, outcome: PublishOutcome) -> None:
    expected_run_id = outcome.image_record.effective_run_id()
    before_run_ids = {image.effective_run_id() for room in before.rooms for image in room.images}
    after_matches = [
        (room.id, image)
        for room in after.rooms
        for image in room.images
        if image.effective_run_id() == expected_run_id
    ]
    _require(len(after_matches) == 1, "post_run", "publish_transition_count_invalid", "publish must add exactly one image for the runId", run_id=expected_run_id)
    added_room_id, image = after_matches[0]
    _require(added_room_id == outcome.room_id, "post_run", "publish_transition_room_invalid", "published image landed in the wrong room", expected_room=outcome.room_id, actual_room=added_room_id)
    _require(image.id == outcome.image_record.id, "post_run", "publish_transition_image_invalid", "published image id does not match outcome", image_id=image.id)
    _require(expected_run_id not in before_run_ids, "post_run", "publish_transition_prior_run_id", "runId already existed before publish", run_id=expected_run_id)
    _require(all(skip.run_id != expected_run_id for skip in after.skipped), "post_run", "publish_transition_skip_conflict", "publish runId cannot also exist in skip ledger", run_id=expected_run_id)


def validate_skip_state_transition(*, before: GalleryState, after: GalleryState, outcome: SkipOutcome) -> None:
    before_skip_run_ids = {skip.run_id for skip in before.skipped}
    after_skip_matches = [skip for skip in after.skipped if skip.run_id == outcome.skip_record.run_id]
    _require(len(after_skip_matches) == 1, "post_run", "skip_transition_count_invalid", "skip must add exactly one skip record for the runId", run_id=outcome.skip_record.run_id)
    _require(outcome.skip_record.run_id not in before_skip_run_ids, "post_run", "skip_transition_prior_run_id", "runId already existed before skip", run_id=outcome.skip_record.run_id)
    _require(
        all(image.effective_run_id() != outcome.skip_record.run_id for room in after.rooms for image in room.images),
        "post_run",
        "skip_transition_publish_conflict",
        "skip runId cannot also exist in image ledger",
        run_id=outcome.skip_record.run_id,
    )


def validate_skip_record(skip, *, category: str, require_error: bool) -> None:
    _require(bool(skip.id), category, "skip_id_missing", "skip id is required")
    _require(RUN_DATE_RE.match(skip.run_date) is not None, category, "skip_run_date_invalid", "skip runDate must be YYYY-MM-DD", run_date=skip.run_date)
    _require(skip.stage in SKIP_STAGE_VALUES, category, "skip_stage_invalid", "skip stage is invalid", stage=skip.stage)
    _require(bool(skip.reason_code), category, "skip_reason_code_missing", "skip reasonCode is required")
    _require(bool(skip.message.strip()), category, "skip_message_missing", "skip message is required")
    _require(bool(skip.created_at), category, "skip_created_at_missing", "skip createdAt is required")
    _require(skip.id == f"skip-{skip.run_id}", category, "skip_id_invalid", "skip id must match skip-<runId>", skip_id=skip.id)
    if skip.error is not None:
        _require(bool(skip.error.code), category, "skip_error_code_missing", "skip error code is required")
        _require(bool(skip.error.message.strip()), category, "skip_error_message_missing", "skip error message is required")
        _require(skip.error.code == skip.reason_code, category, "skip_error_code_mismatch", "skip error code must match reasonCode", error_code=skip.error.code, reason_code=skip.reason_code)
    elif require_error:
        _raise(category, "skip_error_missing", "structured skip records must include an error payload")
    _require(isinstance(skip.creative_context, dict), category, "skip_creative_context_invalid", "skip creativeContext must be an object")


def validate_new_image_record(image: GalleryImageRecord, *, expected_run_date: str) -> None:
    validate_existing_image_record(image)
    _require(image.run_date == expected_run_date, "post_run", "image_run_date_missing", "new image record must carry the expected runDate", expected_run_date=expected_run_date)
    _require(bool(image.run_id), "post_run", "image_run_id_missing", "new image record must carry runId")
    _require(bool(image.prompt_summary), "post_run", "image_prompt_summary_missing", "new image record must include promptSummary")
    _require(bool(image.model), "post_run", "image_model_missing", "new image record must include model deployment")
    _require(bool(image.reasoning_model), "post_run", "image_reasoning_model_missing", "new image record must include reasoningModel deployment")


def classify_foundry_error(message: str) -> FailureCode:
    lowered = message.lower()
    if "401" in lowered or "403" in lowered or "auth" in lowered or "token" in lowered:
        return FailureCode.AUTH
    if "404" in lowered or "deployment" in lowered:
        return FailureCode.DEPLOYMENT
    if "content" in lowered and "filter" in lowered:
        return FailureCode.CONTENT_FILTERED
    if "shape" in lowered or "missing" in lowered or "json" in lowered:
        return FailureCode.RESPONSE_SHAPE
    return FailureCode.API


def validate_publish_write_set(
    changed_paths: set[str],
    *,
    asset_repo_path: str,
    critiques_changed: bool,
    next_brief_changed: bool,
) -> None:
    expected_paths = {"data/gallery.json", _normalize_repo_path(asset_repo_path)}
    if critiques_changed:
        expected_paths.add("data/critiques.json")
    if next_brief_changed:
        expected_paths.add("data/next-brief.json")
    gallery_assets = {path for path in map(_normalize_repo_path, changed_paths) if path.startswith("public/gallery/")}
    _require(
        gallery_assets == {_normalize_repo_path(asset_repo_path)},
        "post_run",
        "publish_asset_write_set_invalid",
        "publish must write exactly one gallery asset for the runDate",
        changed_assets=sorted(gallery_assets),
    )
    _require(
        { _normalize_repo_path(path) for path in changed_paths } == expected_paths,
        "post_run",
        "publish_write_set_invalid",
        "publish write set must match the validated outcome exactly",
        expected_paths=sorted(expected_paths),
        changed_paths=sorted({ _normalize_repo_path(path) for path in changed_paths }),
    )


def validate_skip_write_set(
    changed_paths: set[str],
    *,
    critiques_changed: bool,
    next_brief_changed: bool,
) -> None:
    expected_paths = {"data/gallery.json"}
    if critiques_changed:
        expected_paths.add("data/critiques.json")
    if next_brief_changed:
        expected_paths.add("data/next-brief.json")
    normalized_paths = {_normalize_repo_path(path) for path in changed_paths}
    gallery_assets = {path for path in normalized_paths if path.startswith("public/gallery/")}
    _require(
        not gallery_assets,
        "post_run",
        "skip_asset_write_set_invalid",
        "skip outcomes must not write gallery assets",
        changed_assets=sorted(gallery_assets),
    )
    _require(
        normalized_paths == expected_paths,
        "post_run",
        "skip_write_set_invalid",
        "skip write set must match the validated outcome exactly",
        expected_paths=sorted(expected_paths),
        changed_paths=sorted(normalized_paths),
    )


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/")
