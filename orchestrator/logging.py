from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    if isinstance(value, bytes):
        return {"byteLength": len(value)}
    return value


class StructuredLogger:
    def __init__(self, **defaults: Any):
        self._defaults = {key: value for key, value in defaults.items() if value is not None}

    def bind(self, **defaults: Any) -> "StructuredLogger":
        merged = dict(self._defaults)
        merged.update({key: value for key, value in defaults.items() if value is not None})
        return StructuredLogger(**merged)

    def info(self, phase: str, event: str, message: str, **fields: Any) -> None:
        self._emit(sys.stdout, "INFO", phase, event, message, **fields)

    def error(self, phase: str, event: str, message: str, **fields: Any) -> None:
        self._emit(sys.stderr, "ERROR", phase, event, message, **fields)

    def _emit(
        self,
        stream: TextIO,
        level: str,
        phase: str,
        event: str,
        message: str,
        **fields: Any,
    ) -> None:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "phase": phase,
            "event": event,
            "message": message,
            **self._defaults,
            **{key: value for key, value in fields.items() if value is not None},
        }
        print(json.dumps(_serialize(payload), sort_keys=True), file=stream)
