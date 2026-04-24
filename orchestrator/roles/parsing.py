from __future__ import annotations

from typing import Any

from ..contracts import FailureCode, ImageSettings
from ..validation import ContractValidationError, validate_image_settings


def _raise(role: str, step: str, code: str, message: str, **details: Any) -> None:
    raise ContractValidationError(
        category="role_output",
        code=f"{role}_{step}_{code}",
        message=message,
        details={"reasonCode": FailureCode.MALFORMED_OUTPUT.value, **details},
    )


def require_object(value: Any, *, role: str, step: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise(role, step, f"{label}_type_invalid", f"{label} must be an object.", actual_type=type(value).__name__)
    return value


def optional_object(payload: dict[str, Any], field: str, *, role: str, step: str) -> dict[str, Any]:
    value = payload.get(field)
    if value is None:
        return {}
    return require_object(value, role=role, step=step, label=field)


def require_string(payload: dict[str, Any], field: str, *, role: str, step: str) -> str:
    value = payload.get(field)
    if value is None:
        _raise(role, step, f"{field}_missing", f"{field} is required.")
    if not isinstance(value, str):
        _raise(role, step, f"{field}_type_invalid", f"{field} must be a string.", actual_type=type(value).__name__)
    if not value.strip():
        _raise(role, step, f"{field}_blank", f"{field} cannot be blank.")
    return value.strip()


def optional_string(payload: dict[str, Any], field: str, *, role: str, step: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        _raise(role, step, f"{field}_type_invalid", f"{field} must be a string or null.", actual_type=type(value).__name__)
    if not value.strip():
        _raise(role, step, f"{field}_blank", f"{field} cannot be blank when present.")
    return value.strip()


def require_string_list(payload: dict[str, Any], field: str, *, role: str, step: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list):
        _raise(role, step, f"{field}_type_invalid", f"{field} must be a list of strings.", actual_type=type(value).__name__)
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            _raise(role, step, f"{field}_item_type_invalid", f"{field}[{index}] must be a string.", actual_type=type(item).__name__)
        if not item.strip():
            _raise(role, step, f"{field}_item_blank", f"{field}[{index}] cannot be blank.")
        normalized.append(item.strip())
    return normalized


def optional_string_list(payload: dict[str, Any], field: str, *, role: str, step: str) -> list[str]:
    value = payload.get(field)
    if value is None:
        return []
    return require_string_list(payload, field, role=role, step=step)


def require_integer(payload: dict[str, Any], field: str, *, role: str, step: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        _raise(role, step, f"{field}_type_invalid", f"{field} must be an integer.", actual_type=type(value).__name__)
    return value


def parse_generation_settings(payload: dict[str, Any], *, role: str, step: str) -> ImageSettings:
    generation = require_object(payload.get("generation"), role=role, step=step, label="generation")
    settings = ImageSettings(
        width=require_integer(generation, "width", role=role, step=step),
        height=require_integer(generation, "height", role=role, step=step),
    )
    validate_image_settings(settings, category="role_output", code_prefix="artist_generation")
    return settings
