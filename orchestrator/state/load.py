from __future__ import annotations

import json
from pathlib import Path

from ..contracts import CritiquesState, GalleryState, NextBrief
from ..validation import ContractValidationError


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractValidationError(
            category="pre_run",
            code="state_file_missing",
            message=f"Required state file is missing: {path.name}",
            details={"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise ContractValidationError(
            category="pre_run",
            code="state_json_invalid",
            message=f"{path.name} is not valid JSON.",
            details={"path": str(path), "line": exc.lineno, "column": exc.colno},
        ) from exc


def load_gallery_state(repo_root: Path) -> GalleryState:
    return GalleryState.from_dict(_load_json(repo_root / "data" / "gallery.json"))


def load_critiques_state(repo_root: Path) -> CritiquesState:
    return CritiquesState.from_dict(_load_json(repo_root / "data" / "critiques.json"))


def load_next_brief(repo_root: Path) -> NextBrief:
    return NextBrief.from_dict(_load_json(repo_root / "data" / "next-brief.json"))
