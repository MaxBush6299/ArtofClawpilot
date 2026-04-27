from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

FIXTURE_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn5nQAAAABJRU5ErkJggg=="
REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT / "workspace" / "issue-15-proof"
RUN_DATE = "2026-04-24"
PREVIOUS_DAY = "2026-04-23"
OVERLAY_PATHS = ("orchestrator", "scripts", "data", "public", "package.json")


@dataclass(slots=True)
class Scenario:
    name: str
    fixture_scenario: str
    setup: Callable[[Path], None]
    expect_exit: int
    validate: Callable[[dict[str, object]], None]


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic orchestrator proof matrix for issue #15.")
    parser.add_argument("--retain-workspaces", action="store_true", help="Keep scenario clones for inspection.")
    parser.add_argument("--scenario", action="append", default=[], help="Run only the named scenario. Repeatable.")
    args = parser.parse_args()

    scenarios = build_scenarios()
    selected = [scenario for scenario in scenarios if not args.scenario or scenario.name in set(args.scenario)]
    if not selected:
        print("No proof scenarios matched.", file=sys.stderr)
        return 2

    if WORKSPACE_ROOT.exists():
        remove_tree(WORKSPACE_ROOT)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for scenario in selected:
        try:
            run_scenario(scenario)
            print(f"PASS {scenario.name}")
        except Exception as exc:
            failures.append(f"{scenario.name}: {exc}")
            print(f"FAIL {scenario.name}: {exc}", file=sys.stderr)

    if not args.retain_workspaces and not failures:
        remove_tree(WORKSPACE_ROOT, ignore_errors=True)

    if failures:
        print("", file=sys.stderr)
        print("Proof matrix failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Verified {len(selected)} orchestrator proof scenarios.")
    return 0


def build_scenarios() -> list[Scenario]:
    return [
        Scenario("publish-happy-path", "publish", seed_publish_ready_repo, 0, validate_publish_happy_path),
        Scenario("image-generation-failure", "skip-generation-failure", seed_publish_ready_repo, 0, validate_generation_skip),
        Scenario("malformed-curator-output", "malformed-curator", seed_empty_repo, 0, validate_malformed_curator),
        Scenario("malformed-critic-output", "malformed-critic", seed_publish_ready_repo, 0, validate_malformed_critic),
        Scenario("malformed-artist-review", "malformed-artist-review", seed_publish_ready_repo, 0, validate_malformed_artist_review),
        Scenario("artist-call-budget-overflow", "artist-call-budget-overflow", seed_publish_ready_repo, 0, validate_artist_budget_overflow),
        Scenario("already-resolved-no-op", "publish", seed_same_day_publish, 0, validate_already_resolved),
        Scenario("corrupted-pre-run-gallery", "publish", seed_corrupted_gallery, 11, validate_pre_run_hard_fail),
    ]


def run_scenario(scenario: Scenario) -> None:
    scenario_root = WORKSPACE_ROOT / scenario.name
    clone_repo(scenario_root)
    scenario.setup(scenario_root)
    before_status = git_status_lines(scenario_root)

    command = [
        sys.executable,
        "-B",
        "-m",
        "orchestrator.main",
        "--repo-root",
        ".",
        "--run-date",
        RUN_DATE,
        "--dry-run",
        "--allow-dirty",
        "--use-fixtures",
        "--fixture-scenario",
        scenario.fixture_scenario,
    ]
    completed = subprocess.run(command, cwd=scenario_root, capture_output=True, text=True, check=False)
    after_status = git_status_lines(scenario_root)
    logs = parse_logs(completed.stdout, completed.stderr)
    summary = {
        "exit_code": completed.returncode,
        "before_status": before_status,
        "after_status": after_status,
        "logs": logs,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

    if completed.returncode != scenario.expect_exit:
        raise AssertionError(
            f"expected exit {scenario.expect_exit}, got {completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    if before_status != after_status:
        raise AssertionError("dry-run scenario changed repository state unexpectedly")
    scenario.validate(summary)


def clone_repo(target: Path) -> None:
    if target.exists():
        remove_tree(target, ignore_errors=True)
    clone_error: subprocess.CalledProcessError | None = None
    for attempt in range(3):
        try:
            subprocess.run(
                ["git", "--no-pager", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(target)],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            clone_error = None
            break
        except subprocess.CalledProcessError as exc:
            clone_error = exc
            if target.exists():
                remove_tree(target, ignore_errors=True)
            time.sleep(1)
    if clone_error is not None:
        stderr = (clone_error.stderr or clone_error.stdout or "").strip()
        raise RuntimeError(f"git clone failed for {target.name}: {stderr}") from clone_error
    for relative in OVERLAY_PATHS:
        source = REPO_ROOT / relative
        destination = target / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def remove_tree(path: Path, *, ignore_errors: bool = False) -> None:
    def onerror(function, failed_path, exc_info):
        try:
            os.chmod(failed_path, 0o700)
            function(failed_path)
        except Exception:
            if not ignore_errors:
                raise exc_info[1]

    shutil.rmtree(path, ignore_errors=ignore_errors, onerror=onerror)


def git_status_lines(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "--no-pager", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def parse_logs(stdout: str, stderr: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                records.append(decoded)
    return records


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def seed_empty_repo(repo_root: Path) -> None:
    return None


def seed_publish_ready_repo(repo_root: Path) -> None:
    gallery = read_json(repo_root / "data" / "gallery.json")
    room = gallery["rooms"][0]
    room["images"].append(
        {
            "id": PREVIOUS_DAY,
            "title": "Seeded Critic Piece",
            "path": f"/gallery/{PREVIOUS_DAY[:4]}/{PREVIOUS_DAY}-seeded-critic-piece.png",
            "createdAt": f"{PREVIOUS_DAY}T00:00:00+00:00",
            "artistNote": "Seeded image so the Critic path is exercised during dry-run proof.",
            "promptSummary": "A seeded image used only for deterministic proof.",
            "runDate": PREVIOUS_DAY,
            "model": "MAI-Image-2e",
            "reasoningModel": "grok-4-20-reasoning",
            "slug": "seeded-critic-piece",
            "prompt": "Seeded proof image prompt.",
        }
    )
    write_json(repo_root / "data" / "gallery.json", gallery)

    asset_path = repo_root / "public" / "gallery" / PREVIOUS_DAY[:4] / f"{PREVIOUS_DAY}-seeded-critic-piece.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(_fixture_png_bytes())


def seed_same_day_publish(repo_root: Path) -> None:
    seed_publish_ready_repo(repo_root)
    gallery = read_json(repo_root / "data" / "gallery.json")
    room = gallery["rooms"][0]
    room["images"].append(
        {
            "id": f"scheduled-{RUN_DATE}",
            "title": "Already Resolved Piece",
            "path": f"/gallery/{RUN_DATE[:4]}/{RUN_DATE}-already-resolved-piece.png",
            "createdAt": f"{RUN_DATE}T00:00:00+00:00",
            "artistNote": "Seeded same-day image for idempotent no-op proof.",
            "promptSummary": "A same-day seeded image for rerun proof.",
            "runDate": RUN_DATE,
            "runId": f"scheduled-{RUN_DATE}",
            "model": "MAI-Image-2e",
            "reasoningModel": "grok-4-20-reasoning",
            "slug": "already-resolved-piece",
            "prompt": "Seeded same-day image prompt.",
        }
    )
    write_json(repo_root / "data" / "gallery.json", gallery)


def seed_corrupted_gallery(repo_root: Path) -> None:
    (repo_root / "data" / "gallery.json").write_text("{\n  \"version\": 1,\n  \"rooms\": [\n", encoding="utf-8")


def _fixture_png_bytes() -> bytes:
    import base64

    return base64.b64decode(FIXTURE_PNG_BASE64)


def find_log(summary: dict[str, object], *, event: str, phase: str | None = None) -> dict[str, object]:
    for record in summary["logs"]:  # type: ignore[index]
        if record.get("event") == event and (phase is None or record.get("phase") == phase):
            return record
    raise AssertionError(f"missing log event={event} phase={phase}")


def assert_run_summary(summary: dict[str, object], *, outcome: str, curator: int, critic: int, artist: int, image: int) -> None:
    record = find_log(summary, event="run_summary", phase="result")
    actual = (
        record.get("outcome"),
        record.get("curatorReasoningCalls"),
        record.get("criticReasoningCalls"),
        record.get("artistReasoningCalls"),
        record.get("imageGenerationCalls"),
    )
    expected = (outcome, curator, critic, artist, image)
    if actual != expected:
        raise AssertionError(f"expected run summary {expected}, got {actual}")


def validate_publish_happy_path(summary: dict[str, object]) -> None:
    find_log(summary, event="dry_run_validated", phase="publish")
    find_log(summary, event="reviewed_prompt_proof", phase="result")
    assert_run_summary(summary, outcome="publish", curator=1, critic=1, artist=3, image=1)


def validate_generation_skip(summary: dict[str, object]) -> None:
    record = find_log(summary, event="skip_outcome_validated", phase="validation")
    if record.get("reasonCode") != "foundry_generation_failed" or record.get("skipStage") != "artist":
        raise AssertionError(f"unexpected structured skip details: {record}")
    assert_run_summary(summary, outcome="skip", curator=1, critic=1, artist=3, image=1)


def validate_malformed_curator(summary: dict[str, object]) -> None:
    record = find_log(summary, event="skip_outcome_validated", phase="validation")
    if record.get("reasonCode") != "malformed_model_output" or record.get("skipStage") != "curator":
        raise AssertionError(f"unexpected curator skip details: {record}")
    assert_run_summary(summary, outcome="skip", curator=1, critic=0, artist=0, image=0)


def validate_malformed_critic(summary: dict[str, object]) -> None:
    record = find_log(summary, event="skip_outcome_validated", phase="validation")
    if record.get("reasonCode") != "malformed_model_output" or record.get("skipStage") != "critic":
        raise AssertionError(f"unexpected critic skip details: {record}")
    assert_run_summary(summary, outcome="skip", curator=1, critic=1, artist=0, image=0)


def validate_malformed_artist_review(summary: dict[str, object]) -> None:
    record = find_log(summary, event="skip_outcome_validated", phase="validation")
    if record.get("reasonCode") != "malformed_model_output" or record.get("skipStage") != "artist":
        raise AssertionError(f"unexpected artist review skip details: {record}")
    assert_run_summary(summary, outcome="skip", curator=1, critic=1, artist=3, image=0)


def validate_artist_budget_overflow(summary: dict[str, object]) -> None:
    record = find_log(summary, event="skip_outcome_validated", phase="validation")
    if record.get("reasonCode") != "call_budget_exceeded" or record.get("skipStage") != "artist":
        raise AssertionError(f"unexpected artist budget skip details: {record}")
    assert_run_summary(summary, outcome="skip", curator=1, critic=1, artist=3, image=0)


def validate_already_resolved(summary: dict[str, object]) -> None:
    record = find_log(summary, event="already_resolved", phase="pre_run")
    if record.get("outcome") != "publish":
        raise AssertionError(f"unexpected no-op outcome details: {record}")
    assert_run_summary(summary, outcome="no-op", curator=0, critic=0, artist=0, image=0)


def validate_pre_run_hard_fail(summary: dict[str, object]) -> None:
    record = find_log(summary, event="run_failed", phase="pre_run")
    if record.get("errorCode") != "state_json_invalid":
        raise AssertionError(f"unexpected pre-run failure details: {record}")
    if any(record.get("event") == "reasoning_call_completed" for record in summary["logs"]):  # type: ignore[index]
        raise AssertionError("pre-run failure should happen before any model calls")


if __name__ == "__main__":
    raise SystemExit(main())
