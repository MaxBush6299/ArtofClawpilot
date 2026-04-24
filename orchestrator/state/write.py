from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_gallery_state(repo_root: Path, state) -> None:
    _write_json(repo_root / "data" / "gallery.json", state.to_dict())


def write_critiques_state(repo_root: Path, state) -> None:
    _write_json(repo_root / "data" / "critiques.json", state.to_dict())


def write_next_brief(repo_root: Path, brief) -> None:
    _write_json(repo_root / "data" / "next-brief.json", brief.to_dict())
