from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import (
    CriticReview,
    CritiqueEntry,
    CritiquesState,
    CuratorPlan,
    FailureCode,
    FailureStage,
    GalleryImageRecord,
    GalleryState,
    ImageGenerationResult,
    ImageModelConfig,
    NextBrief,
    PublishOutcome,
    RoleFailure,
    RunContext,
    RuntimeConfig,
    SkipOutcome,
)
from .integrations.foundry import FoundryImageClient, FoundryReasoningClient, FoundryTransportError
from .integrations.identity import ContainerAppsManagedIdentityTokenProvider
from .roles import ArtistRole, CriticRole, CuratorRole
from .state.load import load_critiques_state, load_gallery_state, load_next_brief
from .state.write import write_critiques_state, write_gallery_state, write_next_brief
from .validation import (
    ContractValidationError,
    PreRunValidationResult,
    validate_critiques_state,
    validate_gallery_state,
    validate_next_brief,
    validate_pre_run_state,
    validate_publish_outcome,
    validate_publish_state_transition,
    validate_publish_write_set,
    validate_skip_write_set,
    validate_skip_outcome,
    validate_skip_state_transition,
)

FIXTURE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn5nQAAAABJRU5ErkJggg=="
)
DOMAIN_SKIP_CODES = {
    FailureCode.CALL_BUDGET,
    FailureCode.CONTENT_FILTERED,
    FailureCode.GENERATION,
    FailureCode.MALFORMED_OUTPUT,
    FailureCode.RESPONSE_SHAPE,
    FailureCode.VALIDATION,
}
GUIDING_DESCRIPTION_MAX_CHARS = 1000


@dataclass(slots=True)
class OrchestratorError(RuntimeError):
    phase: str
    code: str
    message: str
    exit_code: int

    def __str__(self) -> str:
        return f"[{self.phase}] {self.code}: {self.message}"


@dataclass(slots=True)
class RuntimeArgs:
    repo_root: Path
    config: RuntimeConfig
    dry_run: bool
    allow_dirty: bool
    use_fixtures: bool
    fixture_scenario: str
    git_author_name: str
    git_author_email: str
    trigger_source: str
    request_id: str | None
    caller_identity: str | None
    correlation_id: str | None
    guiding_description: str | None


@dataclass(slots=True)
class RunEvidence:
    curator_reasoning_calls: int = 0
    critic_reasoning_calls: int = 0
    artist_reasoning_calls: int = 0
    image_generation_calls: int = 0
    handoff_status: str = "not_started"
    handoff_prompt_chars: int = 0
    handoff_usage_stages: tuple[str, ...] = ()


def parse_args() -> RuntimeArgs:
    parser = argparse.ArgumentParser(description="Art of Clawpilot hosted Python orchestrator.")
    default_repo_root = Path(
        (Path.cwd() if not __package__ else Path(__file__).resolve().parents[1])
        if not (repo_workspace := os.environ.get("REPO_WORKSPACE"))
        else repo_workspace
    )
    run_date_default = os.environ.get("RUN_DATE_UTC") or datetime.now(UTC).date().isoformat()
    
    parser.add_argument("--repo-root", default=str(default_repo_root))
    parser.add_argument("--run-date", default=run_date_default)
    parser.add_argument("--run-id", default=None, help="Unique run identity for idempotency (e.g., scheduled-2026-04-27 or manual-2026-04-27-abc123)")
    parser.add_argument(
        "--trigger-source",
        default=os.environ.get("TRIGGER_SOURCE") or "scheduled",
        help="Source that initiated this run, such as scheduled, manual-api, or manual-cli.",
    )
    parser.add_argument("--request-id", default=os.environ.get("REQUEST_ID") or None)
    parser.add_argument("--caller-identity", default=os.environ.get("CALLER_IDENTITY") or None)
    parser.add_argument("--correlation-id", default=os.environ.get("CORRELATION_ID") or None)
    parser.add_argument(
        "--guiding-description",
        default=os.environ.get("GUIDING_DESCRIPTION") or None,
        help="Optional advisory context for Curator. Max 1000 characters; not a prompt override.",
    )
    parser.add_argument("--repo-owner", default=os.environ.get("GITHUB_OWNER") or "MaxBush6299")
    parser.add_argument("--repo-name", default=os.environ.get("GITHUB_REPO") or "ArtofClawpilot")
    parser.add_argument("--branch", default=os.environ.get("GITHUB_BRANCH") or "main")
    parser.add_argument(
        "--reasoning-endpoint",
        default=os.environ.get("FOUNDRY_REASONING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
        or "https://example.openai.azure.com",
    )
    parser.add_argument(
        "--reasoning-deployment",
        default=os.environ.get("FOUNDRY_REASONING_DEPLOYMENT")
        or os.environ.get("FOUNDRY_DEPLOYMENT")
        or "grok-4-20-reasoning",
    )
    parser.add_argument("--reasoning-api-version", default=os.environ.get("FOUNDRY_REASONING_API_VERSION") or "2024-10-21")
    parser.add_argument(
        "--image-endpoint",
        default=os.environ.get("FOUNDRY_IMAGE_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
        or "https://example.services.ai.azure.com",
    )
    parser.add_argument(
        "--image-deployment",
        default=os.environ.get("FOUNDRY_IMAGE_DEPLOYMENT")
        or os.environ.get("FOUNDRY_DEPLOYMENT")
        or "MAI-Image-2e",
    )
    parser.add_argument(
        "--image-api-version",
        default=os.environ.get("FOUNDRY_IMAGE_API_VERSION") or "2025-04-01-preview",
    )
    parser.add_argument("--image-width", type=int, default=int(os.environ.get("FOUNDRY_IMAGE_WIDTH", "1024")))
    parser.add_argument("--image-height", type=int, default=int(os.environ.get("FOUNDRY_IMAGE_HEIGHT", "1024")))
    parser.add_argument("--dry-run", action="store_true", help="Execute the full contract without mutating the repository.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow an existing dirty repo. Intended for local dry runs only.")
    parser.add_argument(
        "--use-fixtures",
        action="store_true",
        help="Use deterministic local reasoning/image fixtures instead of live Foundry calls.",
    )
    parser.add_argument(
        "--fixture-scenario",
        choices=(
            "publish",
            "skip-generation-failure",
            "malformed-curator",
            "malformed-critic",
            "malformed-artist-review",
            "artist-call-budget-overflow",
            "image-auth-failure",
            "image-deployment-failure",
            "image-content-filter",
            "image-malformed-response",
        ),
        default=os.environ.get("ORCHESTRATOR_FIXTURE_SCENARIO") or "publish",
        help="Choose the deterministic fixture scenario when fixtures are enabled.",
    )
    parser.add_argument("--git-author-name", default=os.environ.get("GIT_AUTHOR_NAME") or "Art of Clawpilot Bot")
    parser.add_argument(
        "--git-author-email",
        default=os.environ.get("GIT_AUTHOR_EMAIL") or "artofclawpilot-bot@users.noreply.github.com",
    )
    parsed = parser.parse_args()
    parsed.run_id = parsed.run_id or os.environ.get("RUN_ID") or f"scheduled-{parsed.run_date}"
    guiding_description = parsed.guiding_description.strip() if parsed.guiding_description else None
    if guiding_description is not None and len(guiding_description) > GUIDING_DESCRIPTION_MAX_CHARS:
        parser.error(f"--guiding-description must be {GUIDING_DESCRIPTION_MAX_CHARS} characters or fewer")
    config = RuntimeConfig(
        repo_owner=parsed.repo_owner,
        repo_name=parsed.repo_name,
        branch=parsed.branch,
        run_date=parsed.run_date,
        run_id=parsed.run_id,
        reasoning_model=parsed_reasoning_model(parsed),
        image_model=parsed_image_model(parsed),
        trigger_source=parsed.trigger_source,
    )
    return RuntimeArgs(
        repo_root=Path(parsed.repo_root).resolve(),
        config=config,
        dry_run=parsed.dry_run,
        allow_dirty=parsed.allow_dirty,
        use_fixtures=parsed.use_fixtures or parsed.dry_run,
        fixture_scenario=parsed.fixture_scenario,
        git_author_name=parsed.git_author_name,
        git_author_email=parsed.git_author_email,
        trigger_source=parsed.trigger_source,
        request_id=parsed.request_id,
        caller_identity=parsed.caller_identity,
        correlation_id=parsed.correlation_id,
        guiding_description=guiding_description,
    )


def parsed_reasoning_model(parsed: argparse.Namespace):
    from .contracts import ReasoningModelConfig

    return ReasoningModelConfig(
        endpoint=parsed.reasoning_endpoint,
        deployment=parsed.reasoning_deployment,
        api_version=parsed.reasoning_api_version,
    )


def parsed_image_model(parsed: argparse.Namespace) -> ImageModelConfig:
    from .contracts import ImageSettings

    return ImageModelConfig(
        endpoint=parsed.image_endpoint,
        deployment=parsed.image_deployment,
        api_version=parsed.image_api_version,
        settings=ImageSettings(width=parsed.image_width, height=parsed.image_height),
    )


LOG_RUNTIME_CONTEXT: dict[str, Any] = {
    "component": "orchestrator",
    "runtime": "aca-job",
}

for env_name, field_name in (
    ("HOSTED_JOB_NAME", "jobName"),
    ("CONTAINER_APP_JOB_NAME", "jobName"),
    ("CONTAINER_APP_JOB_EXECUTION_NAME", "jobExecutionName"),
    ("CONTAINER_APP_REPLICA_NAME", "replicaName"),
):
    env_value = os.environ.get(env_name)
    if env_value and field_name not in LOG_RUNTIME_CONTEXT:
        LOG_RUNTIME_CONTEXT[field_name] = env_value


def set_log_context(context: RunContext) -> None:
    LOG_RUNTIME_CONTEXT["runDate"] = context.run_date
    LOG_RUNTIME_CONTEXT["runId"] = context.run_id
    LOG_RUNTIME_CONTEXT["traceId"] = context.trace_id
    LOG_RUNTIME_CONTEXT["triggerSource"] = context.trigger_source
    if context.request_id:
        LOG_RUNTIME_CONTEXT["requestId"] = context.request_id
    if context.caller_identity:
        LOG_RUNTIME_CONTEXT["callerIdentity"] = context.caller_identity
    if context.correlation_id:
        LOG_RUNTIME_CONTEXT["correlationId"] = context.correlation_id


def emit_log(
    phase: str,
    event: str,
    *,
    level: str = "INFO",
    stream: Any = sys.stdout,
    message: str | None = None,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "phase": phase,
        "event": event,
        **LOG_RUNTIME_CONTEXT,
    }
    if message is not None:
        payload["message"] = message
    payload.update({key: value for key, value in fields.items() if value is not None})
    print(json.dumps(payload, separators=(",", ":"), default=str), file=stream, flush=True)


def phase_log(
    phase: str,
    message: str,
    *,
    event: str = "status",
    level: str = "INFO",
    stream: Any = sys.stdout,
    **fields: Any,
) -> None:
    emit_log(phase, event, level=level, stream=stream, message=message, **fields)


def log_role_failure(failure: RoleFailure, *, outcome_kind: str) -> None:
    phase_log(
        failure.stage.value,
        failure.message,
        event="failure_classified",
        level="WARNING" if outcome_kind == "skip" else "ERROR",
        stream=sys.stderr,
        outcome=outcome_kind,
        reasonCode=failure.reason_code.value,
        retryable=failure.retryable,
        errorDetails=failure.details or None,
    )


def run_git(repo_root: Path, *args: str) -> str:
    command = ["git", "--no-pager", *args]
    result = subprocess.run(command, cwd=repo_root, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise OrchestratorError("pre_run", "git_command_failed", stderr, exit_code=12)
    return result.stdout.rstrip("\r\n")


def ensure_repo_state(repo_root: Path, branch: str, *, allow_dirty: bool) -> None:
    if not (repo_root / ".git").exists():
        raise OrchestratorError("pre_run", "repo_missing_git", f"{repo_root} is not a git checkout.", exit_code=12)
    current_branch = run_git(repo_root, "branch", "--show-current")
    if current_branch and current_branch != branch:
        raise OrchestratorError(
            "pre_run",
            "repo_branch_mismatch",
            f"expected branch {branch}, found {current_branch}",
            exit_code=12,
        )
    if allow_dirty:
        return
    status = run_git(repo_root, "status", "--porcelain")
    if status:
        raise OrchestratorError("pre_run", "repo_dirty", "workspace must be clean before mutation.", exit_code=12)


def workspace_delta(repo_root: Path) -> set[str]:
    status = run_git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    changed: set[str] = set()
    for line in status.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.add(path.replace("\\", "/"))
    return changed


def slugify(value: str) -> str:
    lowered = value.lower()
    slug = "".join(char if char.isalnum() else "-" for char in lowered)
    parts = [part for part in slug.split("-") if part]
    return "-".join(parts)[:80] or "daily-piece"


def resolve_room(gallery: GalleryState, room_id: str) -> Any:
    room = gallery.find_room(room_id)
    if room is None:
        raise ContractValidationError(
            category="role_output",
            code="curator_room_missing",
            message=f"Curator selected unknown room {room_id}.",
        )
    return room


def select_next_brief_room(gallery: GalleryState) -> str:
    ordered = sorted(gallery.rooms, key=lambda room: (len(room.images), room.id))
    return ordered[0].id if ordered else "room-01"


def build_next_brief(previous_brief: NextBrief, gallery_after: GalleryState, curator_plan: CuratorPlan, critic_review: CriticReview | None) -> NextBrief:
    carry_forward_theme = curator_plan.carry_forward.get("nextDayTheme")
    notes = carry_forward_theme or (critic_review.critique.suggestion if critic_review else None) or curator_plan.notes
    return NextBrief(
        day=previous_brief.day + 1,
        target_room=select_next_brief_room(gallery_after),
        style_request=carry_forward_theme or curator_plan.style_request,
        notes=notes.strip(),
    )


def has_persisted_critique(critiques: CritiquesState, critique_id: str) -> bool:
    return any(entry.id == critique_id for entry in critiques.entries)


def append_critique_if_new(critiques: CritiquesState, critique: CritiqueEntry | None) -> bool:
    if critique is None:
        return False
    if has_persisted_critique(critiques, critique.id):
        phase_log(
            "validation",
            "skipping duplicate critique append because the critique id already exists",
            event="critique_append_no_op",
            critiqueId=critique.id,
        )
        return False
    critiques.entries.append(critique)
    return True


def build_publish_outcome(
    *,
    context: RunContext,
    config: RuntimeConfig,
    curator_plan: CuratorPlan,
    critic_review: CriticReview | None,
    artist_result,
    image_result: ImageGenerationResult,
) -> PublishOutcome:
    slug = slugify(artist_result.prompt_package.title)
    year = context.run_date[:4]
    run_id_suffix = context.run_id.split('-')[-1][:8]
    asset_repo_path = Path("public") / "gallery" / year / f"{context.run_date}-{slug}-{run_id_suffix}.png"
    public_path = f"/gallery/{year}/{context.run_date}-{slug}-{run_id_suffix}.png"
    image_record = GalleryImageRecord(
        id=context.run_id,
        title=artist_result.prompt_package.title,
        path=public_path,
        created_at=context.started_at,
        artist_note=artist_result.prompt_package.artist_note,
        prompt_summary=artist_result.prompt_package.prompt_summary,
        criticism=critic_review.pull_quote if critic_review else None,
        run_date=context.run_date,
        run_id=context.run_id,
        model=image_result.deployment,
        reasoning_model=config.reasoning_model.deployment,
        slug=slug,
        prompt=artist_result.prompt_package.prompt,
        trigger_source=context.trigger_source,
    )
    return PublishOutcome(
        run_date=context.run_date,
        room_id=curator_plan.target_room_id,
        image_record=image_record,
        image_result=image_result,
        asset_repo_path=asset_repo_path.as_posix(),
        critique=critic_review.critique if critic_review else None,
        reasoning_audit=artist_result.reasoning_audit,
    )


def apply_publish_outcome(
    *,
    gallery: GalleryState,
    critiques,
    previous_brief: NextBrief,
    outcome: PublishOutcome,
    curator_plan: CuratorPlan,
    critic_review: CriticReview | None,
):
    updated_gallery = GalleryState.from_dict(gallery.to_dict())
    target_room = updated_gallery.find_room(outcome.room_id)
    if target_room is None:
        raise ContractValidationError("post_run", "publish_room_missing", f"Room {outcome.room_id} does not exist.")
    target_room.images.append(outcome.image_record)
    updated_critiques = type(critiques).from_dict(critiques.to_dict())
    append_critique_if_new(updated_critiques, outcome.critique)
    next_brief = build_next_brief(previous_brief, updated_gallery, curator_plan, critic_review)
    validate_gallery_state(updated_gallery)
    validate_critiques_state(updated_critiques)
    validate_next_brief(next_brief)
    validate_publish_state_transition(before=gallery, after=updated_gallery, outcome=outcome)
    return updated_gallery, updated_critiques, next_brief


def apply_skip_outcome(*, gallery: GalleryState, critiques, previous_brief: NextBrief, outcome: SkipOutcome):
    updated_gallery = GalleryState.from_dict(gallery.to_dict())
    updated_gallery.skipped.append(outcome.skip_record)
    updated_critiques = type(critiques).from_dict(critiques.to_dict())
    append_critique_if_new(updated_critiques, outcome.critique)
    next_brief = outcome.next_brief or previous_brief
    validate_gallery_state(updated_gallery)
    validate_critiques_state(updated_critiques)
    validate_next_brief(next_brief)
    validate_skip_state_transition(before=gallery, after=updated_gallery, outcome=outcome)
    return updated_gallery, updated_critiques, next_brief


def states_differ(before: Any, after: Any) -> bool:
    return before.to_dict() != after.to_dict()


def persist_publish_outcome(
    repo_root: Path,
    gallery,
    critiques,
    next_brief: NextBrief,
    outcome: PublishOutcome,
    *,
    previous_critiques,
    previous_brief: NextBrief,
) -> None:
    asset_path = repo_root / Path(outcome.asset_repo_path)
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(outcome.image_result.image_bytes)
    write_gallery_state(repo_root, gallery)
    if critiques is not None and states_differ(previous_critiques, critiques):
        write_critiques_state(repo_root, critiques)
    if next_brief is not None and states_differ(previous_brief, next_brief):
        write_next_brief(repo_root, next_brief)


def persist_skip_outcome(
    repo_root: Path,
    gallery,
    critiques,
    next_brief: NextBrief,
    *,
    previous_critiques,
    previous_brief: NextBrief,
) -> None:
    write_gallery_state(repo_root, gallery)
    if critiques is not None and states_differ(previous_critiques, critiques):
        write_critiques_state(repo_root, critiques)
    if next_brief is not None and states_differ(previous_brief, next_brief):
        write_next_brief(repo_root, next_brief)


def should_skip_from_failure(failure: RoleFailure) -> bool:
    return failure.reason_code in DOMAIN_SKIP_CODES


def map_contract_failure(stage: FailureStage, exc: ContractValidationError) -> RoleFailure:
    reason_code = FailureCode.VALIDATION
    raw_reason_code = exc.details.get("reasonCode")
    if isinstance(raw_reason_code, str):
        try:
            reason_code = FailureCode(raw_reason_code)
        except ValueError:
            reason_code = FailureCode.VALIDATION
    return RoleFailure(
        stage=stage,
        reason_code=reason_code,
        message=exc.message,
        retryable=False,
        details={"category": exc.category, "code": exc.code, **exc.details},
    )


def map_foundry_failure(stage: FailureStage, exc: FoundryTransportError) -> RoleFailure:
    return RoleFailure(
        stage=stage,
        reason_code=exc.code,
        message=exc.message,
        retryable=exc.code in {FailureCode.API, FailureCode.GENERATION},
        details={"statusCode": exc.status_code, "body": exc.body},
    )


class FixtureReasoningClient:
    def __init__(self, deployment: str, scenario: str):
        self._deployment = deployment
        self._scenario = scenario
        self.force_artist_budget_overflow = scenario == "artist-call-budget-overflow"

    def complete_json(self, step):
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        if step.role == "curator":
            if self._scenario == "malformed-curator":
                return ({"notes": "missing room and brief"}, _fixture_usage(step, self._deployment, usage))
            brief = step.input_payload["previousBrief"]
            return (
                {
                    "targetRoomId": brief["targetRoom"],
                    "styleRequest": brief.get("styleRequest") or "luminous museum realism",
                    "notes": brief["notes"],
                    "artistBrief": f"Create one museum-grade piece for {step.input_payload['runDate']}.",
                    "carryForward": {"nextDayTheme": "continue the luminous museum realism thread"},
                },
                _fixture_usage(step, self._deployment, usage),
            )
        if step.role == "critic":
            if self._scenario == "malformed-critic":
                return ({"title": "Broken critique", "themes": "not-a-list"}, _fixture_usage(step, self._deployment, usage))
            latest = step.input_payload["latestImage"]
            return (
                {
                    "title": f"Critic on {latest['title']}",
                    "themes": ["continuity", "light"],
                    "body": f"{latest['title']} sustains the gallery's daily rhythm with deliberate atmosphere.",
                    "suggestion": "Push the next composition toward clearer geometry and stronger spatial depth.",
                    "pullQuote": "A poised image that invites the next room to take a bolder step.",
                },
                _fixture_usage(step, self._deployment, usage),
            )
        if step.stage == "analyze":
            return (
                {
                    "constraints": ["publish exactly one image"],
                    "visualTargets": ["gallery-ready composition", "clear focal structure"],
                    "riskChecks": ["avoid draft-only language"],
                },
                _fixture_usage(step, self._deployment, usage),
            )
        if step.stage == "draft":
            return (
                {
                    "title": "Dry Run Radiance",
                    "prompt": "Create a museum-grade painting of a radiant hall with strong geometry, quiet atmosphere, and luminous depth.",
                    "artistNote": "A dry-run stand-in that follows the hosted contract without external model calls.",
                    "promptSummary": "A luminous geometric hall rendered as a calm museum-grade painting.",
                    "generation": {"width": 1024, "height": 1024},
                    "safetyNotes": ["fixture-only prompt package"],
                },
                _fixture_usage(step, self._deployment, usage),
            )
        if self._scenario == "malformed-artist-review":
            return (
                {
                    "promptPackage": {
                        "title": "Dry Run Radiance",
                        "artistNote": "Broken review package",
                        "promptSummary": "Missing reviewed prompt on purpose.",
                        "reviewStatus": "draft",
                        "generation": {"width": 1024, "height": 1024},
                    }
                },
                _fixture_usage(step, self._deployment, usage),
            )
        return (
            {
                "promptPackage": {
                    "title": "Dry Run Radiance",
                    "prompt": "Create a museum-grade painting of a radiant hall with strong geometry, quiet atmosphere, and luminous depth.",
                    "reviewedPrompt": "Create a museum-grade painting of a radiant hall with strong geometry, quiet atmosphere, and luminous depth.",
                    "artistNote": "A dry-run stand-in that follows the hosted contract without external model calls.",
                    "promptSummary": "A luminous geometric hall rendered as a calm museum-grade painting.",
                    "reviewStatus": "final-reviewed",
                    "generation": {"width": 1024, "height": 1024},
                    "safetyNotes": ["fixture-only prompt package"],
                },
                "reviewNotes": ["final-ready fixture payload"],
            },
            _fixture_usage(step, self._deployment, usage),
        )


def _fixture_usage(step, deployment: str, usage: dict[str, Any]):
    from .contracts import ReasoningUsage

    return ReasoningUsage(
        role=step.role,
        stage=step.stage,
        deployment=deployment,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=0,
        finish_reason="stop",
        response_id=f"fixture-{step.role}-{step.stage}",
        provider_model=deployment,
    )


class FixtureImageClient:
    def __init__(self, deployment: str, scenario: str):
        self._deployment = deployment
        self._scenario = scenario

    def generate_image(self, prompt_package) -> ImageGenerationResult:
        if self._scenario == "skip-generation-failure":
            raise FoundryTransportError(
                code=FailureCode.GENERATION,
                message="Fixture image generation failed after reviewed prompt handoff.",
            )
        if self._scenario == "image-auth-failure":
            raise FoundryTransportError(code=FailureCode.AUTH, message="Fixture managed identity auth failed.", status_code=401)
        if self._scenario == "image-deployment-failure":
            raise FoundryTransportError(code=FailureCode.DEPLOYMENT, message="Fixture MAI deployment was not found.", status_code=404)
        if self._scenario == "image-content-filter":
            raise FoundryTransportError(code=FailureCode.CONTENT_FILTERED, message="Fixture MAI response was content filtered.")
        if self._scenario == "image-malformed-response":
            raise FoundryTransportError(code=FailureCode.RESPONSE_SHAPE, message="Fixture MAI response was malformed.")
        return ImageGenerationResult(
            image_bytes=base64.b64decode(FIXTURE_PNG_BASE64),
            mime_type="image/png",
            model=self._deployment,
            deployment=self._deployment,
            response_metadata={
                "operation": "mai_image_generation",
                "endpoint": "https://fixture.services.ai.azure.com",
                "deployment": self._deployment,
                "providerModel": self._deployment,
                "request": {
                    "promptChars": len(prompt_package.reviewed_prompt or prompt_package.prompt),
                    "width": prompt_package.generation.width,
                    "height": prompt_package.generation.height,
                    "reviewStatus": prompt_package.review_status,
                },
                "response": {
                    "responseId": "fixture-image",
                    "created": 0,
                    "fixture": True,
                    "promptSummary": prompt_package.prompt_summary,
                    "outputItemCount": 1,
                    "raw": {
                        "data": [{"b64_json": FIXTURE_PNG_BASE64}],
                    },
                },
            },
        )


def build_reasoning_client(args: RuntimeArgs):
    if args.use_fixtures:
        return FixtureReasoningClient(args.config.reasoning_model.deployment, args.fixture_scenario)
    token_provider = ContainerAppsManagedIdentityTokenProvider()
    return FoundryReasoningClient(args.config.reasoning_model, token_provider=token_provider)


def build_image_client(args: RuntimeArgs):
    if args.use_fixtures:
        return FixtureImageClient(args.config.image_model.deployment, args.fixture_scenario)
    token_provider = ContainerAppsManagedIdentityTokenProvider()
    return FoundryImageClient(args.config.image_model, token_provider=token_provider)


def record_reviewed_prompt_handoff(evidence: RunEvidence, artist_result) -> None:
    evidence.handoff_status = artist_result.prompt_package.review_status or "missing"
    evidence.handoff_prompt_chars = len(artist_result.prompt_package.reviewed_prompt or artist_result.prompt_package.prompt)
    evidence.handoff_usage_stages = tuple(usage.stage for usage in artist_result.reasoning_audit.usage)
    phase_log(
        "artist",
        "reviewed prompt handoff ready: "
        f"status={evidence.handoff_status}, "
        f"promptChars={evidence.handoff_prompt_chars}, "
        f"usageStages={','.join(evidence.handoff_usage_stages)}",
        event="reviewed_prompt_ready",
        reviewStatus=evidence.handoff_status,
        reviewedPromptChars=evidence.handoff_prompt_chars,
        usageStages=list(evidence.handoff_usage_stages),
    )


def log_reasoning_usage(usage) -> None:
    phase_log(
        usage.role,
        "usage: "
        f"stage={usage.stage}, "
        f"deployment={usage.deployment}, "
        f"model={usage.provider_model or 'unknown'}, "
        f"promptTokens={usage.prompt_tokens}, "
        f"completionTokens={usage.completion_tokens}, "
        f"totalTokens={usage.total_tokens}, "
        f"finishReason={usage.finish_reason}",
        event="reasoning_call_completed",
        stageName=usage.stage,
        deployment=usage.deployment,
        providerModel=usage.provider_model,
        promptTokens=usage.prompt_tokens,
        completionTokens=usage.completion_tokens,
        totalTokens=usage.total_tokens,
        finishReason=usage.finish_reason,
        responseId=usage.response_id,
    )


def log_image_metadata(image_result: ImageGenerationResult) -> None:
    metadata = image_result.response_metadata
    request_meta = metadata.get("request") or {}
    phase_log(
        "image_generation",
        "image metadata: "
        f"deployment={image_result.deployment}, "
        f"providerModel={metadata.get('providerModel')}, "
        f"width={request_meta.get('width')}, "
        f"height={request_meta.get('height')}, "
        f"reviewStatus={request_meta.get('reviewStatus')}",
        event="image_generation_completed",
        deployment=image_result.deployment,
        providerModel=metadata.get("providerModel"),
        width=request_meta.get("width"),
        height=request_meta.get("height"),
        reviewStatus=request_meta.get("reviewStatus"),
        responseId=(metadata.get("response") or {}).get("responseId"),
    )


def log_final_call_counts(outcome_kind: str, evidence: RunEvidence) -> None:
    phase_log(
        "result",
        "final call counts: "
        f"outcome={outcome_kind}, "
        f"curator={evidence.curator_reasoning_calls}, "
        f"critic={evidence.critic_reasoning_calls}, "
        f"artist={evidence.artist_reasoning_calls}, "
        f"image={evidence.image_generation_calls}",
        event="run_summary",
        outcome=outcome_kind,
        curatorReasoningCalls=evidence.curator_reasoning_calls,
        criticReasoningCalls=evidence.critic_reasoning_calls,
        artistReasoningCalls=evidence.artist_reasoning_calls,
        imageGenerationCalls=evidence.image_generation_calls,
    )


def log_final_handoff_proof(evidence: RunEvidence) -> None:
    phase_log(
        "result",
        "reviewed prompt proof: "
        f"status={evidence.handoff_status}, "
        f"promptChars={evidence.handoff_prompt_chars}, "
        f"usageStages={','.join(evidence.handoff_usage_stages) or 'none'}",
        event="reviewed_prompt_proof",
        reviewStatus=evidence.handoff_status,
        reviewedPromptChars=evidence.handoff_prompt_chars,
        usageStages=list(evidence.handoff_usage_stages),
    )


def build_skip_creative_context(
    *,
    previous_brief: NextBrief | None = None,
    curator_plan: CuratorPlan | None = None,
    critic_review: CriticReview | None = None,
    room=None,
    latest_image: GalleryImageRecord | None = None,
    artist_result=None,
) -> dict[str, Any]:
    creative_context: dict[str, Any] = {}
    if previous_brief is not None:
        creative_context["previousBrief"] = previous_brief.to_dict()
    if curator_plan is not None:
        creative_context["curatorPlan"] = {
            "targetRoomId": curator_plan.target_room_id,
            "styleRequest": curator_plan.style_request,
            "notes": curator_plan.notes,
            "artistBrief": curator_plan.artist_brief,
        }
    if room is not None:
        creative_context["room"] = {
            "id": room.id,
            "name": room.name,
            "theme": room.theme,
        }
    if latest_image is not None:
        creative_context["latestImage"] = {
            "id": latest_image.id,
            "title": latest_image.title,
            "path": latest_image.path,
            "runDate": latest_image.effective_run_date(),
        }
    if critic_review is not None:
        creative_context["criticReview"] = {
            "title": critic_review.critique.title,
            "suggestion": critic_review.critique.suggestion,
            "pullQuote": critic_review.pull_quote,
        }
    if artist_result is not None:
        creative_context["promptPackage"] = {
            "title": artist_result.prompt_package.title,
            "promptSummary": artist_result.prompt_package.prompt_summary,
            "artistNote": artist_result.prompt_package.artist_note,
            "reviewStatus": artist_result.prompt_package.review_status,
            "reviewedPromptChars": len(artist_result.prompt_package.reviewed_prompt or artist_result.prompt_package.prompt),
            "generation": {
                "width": artist_result.prompt_package.generation.width,
                "height": artist_result.prompt_package.generation.height,
            },
        }
    return creative_context


def build_skip_outcome(
    *,
    context: RunContext,
    failure: RoleFailure,
    critique=None,
    next_brief: NextBrief | None = None,
    creative_context: dict[str, Any] | None = None,
) -> SkipOutcome:
    return SkipOutcome(
        run_date=context.run_date,
        skip_record=failure.to_skip_record(
            context.run_date,
            context.run_id,
            context.started_at,
            creative_context=creative_context,
            trigger_source=context.trigger_source,
        ),
        critique=critique,
        next_brief=next_brief,
    )


def execute_role_steps(args: RuntimeArgs, context: RunContext, gallery, critiques, previous_brief):
    reasoning_client = build_reasoning_client(args)
    image_client = build_image_client(args)
    curator = CuratorRole()
    critic = CriticRole()
    artist = ArtistRole()
    evidence = RunEvidence()

    phase_log("curator", "running Curator role", event="phase_started")
    try:
        curator_plan = curator.run(
            context=context,
            gallery=gallery,
            critiques=critiques,
            previous_brief=previous_brief,
            reasoning=reasoning_client,
        )
        evidence.curator_reasoning_calls = 1 if curator_plan.usage is not None else 0
        if curator_plan.usage is not None:
            log_reasoning_usage(curator_plan.usage)
        room = resolve_room(gallery, curator_plan.target_room_id)
        phase_log("curator", "Curator role completed", event="phase_completed", targetRoomId=curator_plan.target_room_id)
    except ContractValidationError as exc:
        evidence.curator_reasoning_calls = 1
        failure = map_contract_failure(FailureStage.CURATOR, exc)
        log_role_failure(failure, outcome_kind="skip")
        return build_skip_outcome(
            context=context,
            failure=failure,
            creative_context=build_skip_creative_context(previous_brief=previous_brief),
        ), None, None, evidence
    except FoundryTransportError as exc:
        evidence.curator_reasoning_calls = 1
        failure = map_foundry_failure(FailureStage.CURATOR, exc)
        if should_skip_from_failure(failure):
            log_role_failure(failure, outcome_kind="skip")
            return build_skip_outcome(
                context=context,
                failure=failure,
                creative_context=build_skip_creative_context(previous_brief=previous_brief),
            ), None, None, evidence
        log_role_failure(failure, outcome_kind="hard_fail")
        raise OrchestratorError("curator", failure.reason_code.value, failure.message, exit_code=21) from exc

    latest_image = gallery.latest_image()
    critic_review: CriticReview | None = None
    if latest_image is not None:
        if has_persisted_critique(critiques, latest_image.id):
            phase_log(
                "critic",
                "skipping Critic role because the latest image already has a persisted critique",
                event="phase_skipped",
                latestImageId=latest_image.id,
                critiqueId=latest_image.id,
                reason="critique_already_persisted",
            )
        else:
            phase_log("critic", "running Critic role", event="phase_started", latestImageId=latest_image.id)
            try:
                critic_review = critic.run(
                    context=context,
                    latest_image=latest_image,
                    critiques=critiques,
                    reasoning=reasoning_client,
                )
                evidence.critic_reasoning_calls = 1 if critic_review.usage is not None else 0
                if critic_review.usage is not None:
                    log_reasoning_usage(critic_review.usage)
                phase_log("critic", "Critic role completed", event="phase_completed", critiqueId=critic_review.critique.id)
            except ContractValidationError as exc:
                evidence.critic_reasoning_calls = 1
                failure = map_contract_failure(FailureStage.CRITIC, exc)
                log_role_failure(failure, outcome_kind="skip")
                return build_skip_outcome(
                    context=context,
                    failure=failure,
                    creative_context=build_skip_creative_context(
                        curator_plan=curator_plan,
                        latest_image=latest_image,
                    ),
                ), curator_plan, critic_review, evidence
            except FoundryTransportError as exc:
                evidence.critic_reasoning_calls = 1
                failure = map_foundry_failure(FailureStage.CRITIC, exc)
                if should_skip_from_failure(failure):
                    log_role_failure(failure, outcome_kind="skip")
                    return build_skip_outcome(
                        context=context,
                        failure=failure,
                        creative_context=build_skip_creative_context(
                            curator_plan=curator_plan,
                            latest_image=latest_image,
                        ),
                    ), curator_plan, critic_review, evidence
                log_role_failure(failure, outcome_kind="hard_fail")
                raise OrchestratorError("critic", failure.reason_code.value, failure.message, exit_code=22) from exc
    else:
        phase_log("critic", "skipping Critic role because no published image exists", event="phase_skipped")

    phase_log("artist", "running Artist role", event="phase_started", roomId=room.id)
    artist_result = None
    try:
        artist_result = artist.run(
            context=context,
            curator_plan=curator_plan,
            room=room,
            critic_review=critic_review,
            reasoning=reasoning_client,
        )
        evidence.artist_reasoning_calls = artist_result.reasoning_audit.call_count
        for usage in artist_result.reasoning_audit.usage:
            log_reasoning_usage(usage)
        record_reviewed_prompt_handoff(evidence, artist_result)
        evidence.image_generation_calls += 1
        phase_log(
            "image_generation",
            "calling MAI image generation",
            event="phase_started",
            reviewStatus=evidence.handoff_status,
            promptChars=evidence.handoff_prompt_chars,
        )
        image_result = image_client.generate_image(artist_result.prompt_package)
        log_image_metadata(image_result)
        phase_log("artist", "Artist role completed", event="phase_completed", title=artist_result.prompt_package.title)
    except ContractValidationError as exc:
        evidence.artist_reasoning_calls = int(exc.details.get("callCount") or 0)
        failure = map_contract_failure(FailureStage.ARTIST, exc)
        log_role_failure(failure, outcome_kind="skip")
        return (
            build_skip_outcome(
                context=context,
                failure=failure,
                critique=critic_review.critique if critic_review else None,
                creative_context=build_skip_creative_context(
                    curator_plan=curator_plan,
                    critic_review=critic_review,
                    room=room,
                    artist_result=artist_result,
                ),
            ),
            curator_plan,
            critic_review,
            evidence,
        )
    except FoundryTransportError as exc:
        failure = map_foundry_failure(FailureStage.ARTIST, exc)
        if should_skip_from_failure(failure):
            phase_log(
                "image_generation",
                failure.message,
                event="phase_failed",
                level="WARNING",
                stream=sys.stderr,
                outcome="skip",
                reasonCode=failure.reason_code.value,
                retryable=failure.retryable,
                errorDetails=failure.details or None,
            )
            log_role_failure(failure, outcome_kind="skip")
            return build_skip_outcome(
                context=context,
                failure=failure,
                critique=critic_review.critique if critic_review else None,
                creative_context=build_skip_creative_context(
                    curator_plan=curator_plan,
                    critic_review=critic_review,
                    room=room,
                    artist_result=artist_result,
                ),
            ), curator_plan, critic_review, evidence
        phase_log(
            "image_generation",
            failure.message,
            event="phase_failed",
            level="ERROR",
            stream=sys.stderr,
            outcome="hard_fail",
            reasonCode=failure.reason_code.value,
            retryable=failure.retryable,
            errorDetails=failure.details or None,
        )
        log_role_failure(failure, outcome_kind="hard_fail")
        raise OrchestratorError("image_generation", failure.reason_code.value, failure.message, exit_code=23) from exc

    publish_outcome = build_publish_outcome(
        context=context,
        config=args.config,
        curator_plan=curator_plan,
        critic_review=critic_review,
        artist_result=artist_result,
        image_result=image_result,
    )
    validate_publish_outcome(publish_outcome)
    phase_log(
        "validation",
        "publish outcome passed validation",
        event="publish_outcome_validated",
        roomId=publish_outcome.room_id,
        assetPath=publish_outcome.asset_repo_path,
    )
    return publish_outcome, curator_plan, critic_review, evidence


def main() -> int:
    args = parse_args()
    evidence = RunEvidence()
    context = RunContext(
        run_date=args.config.run_date,
        run_id=args.config.run_id,
        started_at=datetime.now(UTC).isoformat(),
        repo_root=str(args.repo_root),
        trace_id=os.environ.get("HOSTED_TRACE_ID") or f"local-{args.config.run_id}",
        trigger_source=args.trigger_source,
        request_id=args.request_id,
        caller_identity=args.caller_identity,
        correlation_id=args.correlation_id,
        guiding_description=args.guiding_description,
    )
    set_log_context(context)
    try:
        phase_log(
            "config",
            f"resolving run for {context.run_date} with runId {context.run_id}",
            event="run_started",
            repoOwner=args.config.repo_owner,
            repoName=args.config.repo_name,
            branch=args.config.branch,
            dryRun=args.dry_run,
            useFixtures=args.use_fixtures,
            reasoningDeployment=args.config.reasoning_model.deployment,
            imageDeployment=args.config.image_model.deployment,
            triggerSource=args.trigger_source,
            requestId=args.request_id,
            callerIdentity=args.caller_identity,
            correlationId=args.correlation_id,
            hasGuidingDescription=bool(args.guiding_description),
            guidingDescriptionChars=len(args.guiding_description or ""),
        )
        ensure_repo_state(args.repo_root, args.config.branch, allow_dirty=args.allow_dirty or args.dry_run)
        phase_log(
            "git",
            "git workspace is ready for execution",
            event="repo_state_verified",
            branch=args.config.branch,
            allowDirty=args.allow_dirty or args.dry_run,
        )

        phase_log("pre_run", "loading persisted state", event="phase_started")
        gallery = load_gallery_state(args.repo_root)
        critiques = load_critiques_state(args.repo_root)
        previous_brief = load_next_brief(args.repo_root)
        pre_run: PreRunValidationResult = validate_pre_run_state(
            config=args.config,
            gallery=gallery,
            critiques=critiques,
            next_brief=previous_brief,
        )
        phase_log(
            "validation",
            "validated persisted state",
            event="preflight_validated",
            roomCount=len(gallery.rooms),
            skippedCount=len(gallery.skipped),
            critiqueCount=len(critiques.entries),
            nextBriefDay=previous_brief.day,
        )

        if pre_run.existing_outcome is not None:
            phase_log(
                "pre_run",
                f"runId {context.run_id} already resolved as {pre_run.existing_outcome}; exiting cleanly",
                event="already_resolved",
                outcome=pre_run.existing_outcome,
            )
            log_final_call_counts("no-op", evidence)
            log_final_handoff_proof(evidence)
            return 0

        outcome, curator_plan, critic_review, evidence = execute_role_steps(args, context, gallery, critiques, previous_brief)

        if isinstance(outcome, PublishOutcome):
            phase_log(
                "publish",
                "assembling publish transaction",
                event="phase_started",
                outcome="publish",
                roomId=outcome.room_id,
                assetPath=outcome.asset_repo_path,
            )
            updated_gallery, updated_critiques, next_brief = apply_publish_outcome(
                gallery=gallery,
                critiques=critiques,
                previous_brief=previous_brief,
                outcome=outcome,
                curator_plan=curator_plan,
                critic_review=critic_review,
            )
            phase_log("validation", "publish transition passed validation", event="state_transition_validated", outcome="publish")
            if args.dry_run:
                phase_log(
                    "publish",
                    f"dry run validated publish outcome for {outcome.image_record.path}",
                    event="dry_run_validated",
                    assetPath=outcome.asset_repo_path,
                    imagePath=outcome.image_record.path,
                )
                log_final_call_counts("publish", evidence)
                log_final_handoff_proof(evidence)
                return 0
            persist_publish_outcome(
                args.repo_root,
                updated_gallery,
                updated_critiques,
                next_brief,
                outcome,
                previous_critiques=critiques,
                previous_brief=previous_brief,
            )
            changed_paths = workspace_delta(args.repo_root)
            validate_publish_write_set(
                changed_paths,
                asset_repo_path=outcome.asset_repo_path,
                critiques_changed=states_differ(critiques, updated_critiques),
                next_brief_changed=states_differ(previous_brief, next_brief),
            )
            phase_log(
                "validation",
                "validated publish write set",
                event="write_set_validated",
                changedPathCount=len(changed_paths),
                changedPaths=sorted(changed_paths),
            )
            phase_log("git", "publish write set is ready for bootstrap commit", event="commit_ready", changedPathCount=len(changed_paths))
            phase_log(
                "publish",
                f"publish outcome ready for commit: {outcome.image_record.title}",
                event="outcome_ready",
                title=outcome.image_record.title,
                assetPath=outcome.asset_repo_path,
            )
            log_final_call_counts("publish", evidence)
            log_final_handoff_proof(evidence)
            return 0

        phase_log(
            "publish",
            "assembling structured skip transaction",
            event="phase_started",
            outcome="skip",
            reasonCode=outcome.skip_record.reason_code,
            skipStage=outcome.skip_record.stage,
        )
        validate_skip_outcome(outcome)
        phase_log(
            "validation",
            "structured skip passed validation",
            event="skip_outcome_validated",
            reasonCode=outcome.skip_record.reason_code,
            skipStage=outcome.skip_record.stage,
        )
        updated_gallery, updated_critiques, next_brief = apply_skip_outcome(
            gallery=gallery,
            critiques=critiques,
            previous_brief=previous_brief,
            outcome=outcome,
        )
        phase_log("validation", "skip transition passed validation", event="state_transition_validated", outcome="skip")
        if args.dry_run:
            phase_log(
                "publish",
                f"dry run validated structured skip {outcome.skip_record.reason_code}",
                event="dry_run_validated",
                reasonCode=outcome.skip_record.reason_code,
                skipStage=outcome.skip_record.stage,
            )
            log_final_call_counts("skip", evidence)
            log_final_handoff_proof(evidence)
            return 0
        persist_skip_outcome(
            args.repo_root,
            updated_gallery,
            updated_critiques,
            next_brief,
            previous_critiques=critiques,
            previous_brief=previous_brief,
        )
        changed_paths = workspace_delta(args.repo_root)
        validate_skip_write_set(
            changed_paths,
            critiques_changed=states_differ(critiques, updated_critiques),
            next_brief_changed=states_differ(previous_brief, next_brief),
        )
        phase_log(
            "validation",
            "validated skip write set",
            event="write_set_validated",
            changedPathCount=len(changed_paths),
            changedPaths=sorted(changed_paths),
        )
        phase_log("git", "skip write set is ready for bootstrap commit", event="commit_ready", changedPathCount=len(changed_paths))
        phase_log(
            "publish",
            f"skip outcome ready for commit: {outcome.skip_record.reason_code}",
            event="outcome_ready",
            reasonCode=outcome.skip_record.reason_code,
            skipStage=outcome.skip_record.stage,
        )
        log_final_call_counts("skip", evidence)
        log_final_handoff_proof(evidence)
        return 0
    except ContractValidationError as exc:
        error = OrchestratorError(exc.category, exc.code, exc.message, exit_code=11)
        emit_log(
            exc.category,
            "run_failed",
            level="ERROR",
            stream=sys.stderr,
            message=exc.message,
            errorCode=exc.code,
            exitCode=error.exit_code,
            details=exc.details or None,
        )
        return error.exit_code
    except OrchestratorError as exc:
        emit_log(
            exc.phase,
            "run_failed",
            level="ERROR",
            stream=sys.stderr,
            message=exc.message,
            errorCode=exc.code,
            exitCode=exc.exit_code,
        )
        return exc.exit_code
    except Exception as exc:
        emit_log(
            "runtime",
            "run_failed",
            level="ERROR",
            stream=sys.stderr,
            message=str(exc) or exc.__class__.__name__,
            errorCode="unhandled_exception",
            errorType=exc.__class__.__name__,
            exitCode=99,
            traceback=traceback.format_exc().splitlines(),
        )
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
