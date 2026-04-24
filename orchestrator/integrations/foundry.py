from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

from ..contracts import (
    ArtistPromptPackage,
    FailureCode,
    ImageGenerationResult,
    ImageModelConfig,
    ReasoningModelConfig,
    ReasoningUsage,
)

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
AI_FOUNDRY_SCOPE = "https://ai.azure.com/.default"


class BearerTokenProvider(Protocol):
    def get_token(self, scope: str) -> str:
        ...


class ReasoningClient(Protocol):
    def complete_json(self, step: "ReasoningStepRequest") -> tuple[dict[str, Any], ReasoningUsage]:
        ...


class ImageClient(Protocol):
    def generate_image(self, prompt_package: ArtistPromptPackage) -> ImageGenerationResult:
        ...


@dataclass(slots=True)
class ReasoningStepRequest:
    role: str
    stage: str
    system_prompt: str
    input_payload: dict[str, Any]
    response_contract: dict[str, Any]


@dataclass(slots=True)
class FoundryTransportError(RuntimeError):
    code: FailureCode
    message: str
    status_code: int | None = None
    body: str | None = None

    def __str__(self) -> str:
        return self.message


def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    fragments.append(text)
        return "\n".join(fragments)
    raise ValueError("Chat completion message content was not a string or text fragment array.")


def _decode_json_payload(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise FoundryTransportError(
            code=FailureCode.MALFORMED_OUTPUT,
            message="Reasoning response was not valid JSON.",
            body=content,
        ) from exc


def _load_json_response(payload: str, *, operation: str) -> dict[str, Any]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FoundryTransportError(
            code=FailureCode.RESPONSE_SHAPE,
            message=f"{operation} returned a non-JSON response body.",
            body=payload,
        ) from exc
    if not isinstance(decoded, dict):
        raise FoundryTransportError(
            code=FailureCode.RESPONSE_SHAPE,
            message=f"{operation} returned a JSON payload that was not an object.",
            body=payload,
        )
    return decoded


def _try_load_json(payload: str) -> Any | None:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _extract_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            for key in ("message", "code", "target"):
                value = error_payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        for key in ("message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _contains_content_filter_signal(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = key.replace("_", "").lower()
            if normalized in {"contentfilterresult", "contentfilter", "contentfiltered"}:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    lowered = value.lower()
                    if any(token in lowered for token in ("filtered", "blocked", "reject", "unsafe")):
                        return True
                if _contains_content_filter_signal(value):
                    return True
            if normalized in {"filtered", "blocked", "isfiltered", "isblocked"} and value is True:
                return True
            if _contains_content_filter_signal(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_contains_content_filter_signal(item) for item in payload)
    if isinstance(payload, str):
        lowered = payload.lower()
        return "content filter" in lowered or "content_filter" in lowered
    return False


def _find_content_filter_details(payload: dict[str, Any]) -> Any | None:
    for key in ("content_filter_result", "contentFilterResult"):
        if key in payload:
            return payload[key]
    for value in payload.values():
        if isinstance(value, dict):
            nested = _find_content_filter_details(value)
            if nested is not None:
                return nested
    return None


def _base_headers(
    token_provider: BearerTokenProvider | None,
    *,
    scope: str = COGNITIVE_SCOPE,
) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token_provider is not None:
        headers["Authorization"] = f"Bearer {token_provider.get_token(scope)}"
    return headers


def _classify_http_error(status_code: int, body: str, *, operation: str) -> tuple[FailureCode, str]:
    parsed = _try_load_json(body)
    detail = _extract_error_message(parsed) or body.strip() or f"HTTP {status_code}"
    lowered = detail.lower()
    if status_code in {401, 403}:
        return FailureCode.AUTH, f"{operation} authentication failed (HTTP {status_code})."
    if status_code == 404 or "deployment" in lowered:
        return FailureCode.DEPLOYMENT, f"{operation} deployment or endpoint was not found (HTTP {status_code})."
    if _contains_content_filter_signal(parsed) or ("content" in lowered and "filter" in lowered):
        return FailureCode.CONTENT_FILTERED, f"{operation} was content filtered."
    return FailureCode.API, f"{operation} request failed with HTTP {status_code}: {detail}"


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], *, operation: str) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req) as response:
            return _load_json_response(response.read().decode("utf-8"), operation=operation)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        code, message = _classify_http_error(exc.code, body, operation=operation)
        raise FoundryTransportError(
            code=code,
            message=message,
            status_code=exc.code,
            body=body,
        ) from exc
    except error.URLError as exc:
        raise FoundryTransportError(
            code=FailureCode.API,
            message=f"{operation} failed before a response was received: {exc.reason}",
        ) from exc


class FoundryReasoningClient:
    def __init__(self, config: ReasoningModelConfig, token_provider: BearerTokenProvider | None = None):
        self._config = config
        self._token_provider = token_provider

    def complete_json(self, step: ReasoningStepRequest) -> tuple[dict[str, Any], ReasoningUsage]:
        url = (
            f"{self._config.endpoint.rstrip('/')}/openai/deployments/"
            f"{self._config.deployment}/chat/completions?api-version={self._config.api_version}"
        )
        payload = {
            "messages": [
                {"role": "system", "content": step.system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "input": step.input_payload,
                            "responseContract": step.response_contract,
                        },
                        indent=2,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": self._config.max_completion_tokens,
            "reasoning_effort": self._config.reasoning_effort,
        }
        raw = _post_json(url, payload, _base_headers(self._token_provider), operation="Foundry reasoning")
        choices = raw.get("choices") or []
        if not choices:
            raise FoundryTransportError(code=FailureCode.RESPONSE_SHAPE, message="Reasoning response did not contain choices.", body=json.dumps(raw))
        message = choices[0].get("message") or {}
        if "content" not in message:
            raise FoundryTransportError(
                code=FailureCode.RESPONSE_SHAPE,
                message="Reasoning response did not contain message content.",
                body=json.dumps(raw),
            )
        try:
            content = _extract_message_text(message.get("content"))
        except ValueError as exc:
            raise FoundryTransportError(
                code=FailureCode.RESPONSE_SHAPE,
                message="Reasoning response message content was not a supported text shape.",
                body=json.dumps(raw),
            ) from exc
        decoded = _decode_json_payload(content)
        if not isinstance(decoded, dict):
            raise FoundryTransportError(
                code=FailureCode.RESPONSE_SHAPE,
                message="Reasoning response JSON payload was not an object.",
                body=content,
            )
        usage = raw.get("usage") or {}
        return decoded, ReasoningUsage(
            role=step.role,
            stage=step.stage,
            deployment=self._config.deployment,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            finish_reason=choices[0].get("finish_reason"),
            response_id=raw.get("id"),
            provider_model=raw.get("model"),
            created=raw.get("created"),
            system_fingerprint=raw.get("system_fingerprint"),
        )


def _extract_base64_image(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("image"), str):
        return payload["image"]
    if isinstance(payload.get("output"), list):
        for item in payload["output"]:
            if isinstance(item, dict):
                if isinstance(item.get("result"), str):
                    return item["result"]
                if isinstance(item.get("image"), str):
                    return item["image"]
    if isinstance(payload.get("images"), list):
        for item in payload["images"]:
            if isinstance(item, dict):
                if isinstance(item.get("base64"), str):
                    return item["base64"]
                if isinstance(item.get("imageBase64"), str):
                    return item["imageBase64"]
    if isinstance(payload.get("data"), list):
        for item in payload["data"]:
            if isinstance(item, dict) and isinstance(item.get("b64_json"), str):
                return item["b64_json"]
    raise FoundryTransportError(code=FailureCode.RESPONSE_SHAPE, message="Image generation response did not contain a recognizable base64 payload.", body=json.dumps(payload))


def _output_item_count(payload: dict[str, Any]) -> int | None:
    for key in ("data", "images", "output"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    return None


def _mai_image_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint.rstrip("/"))
    path = parsed.path or ""
    if path.startswith("/api/projects/"):
        path = ""
    elif path.endswith("/mai/v1/images/generations"):
        path = path[: -len("/mai/v1/images/generations")]
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


class FoundryImageClient:
    def __init__(self, config: ImageModelConfig, token_provider: BearerTokenProvider | None = None):
        self._config = config
        self._token_provider = token_provider

    def generate_image(self, prompt_package: ArtistPromptPackage) -> ImageGenerationResult:
        endpoint = _mai_image_endpoint(self._config.endpoint)
        url = f"{endpoint}/mai/v1/images/generations"
        if self._config.api_version:
            url = f"{url}?api-version={self._config.api_version}"
        prompt = (prompt_package.reviewed_prompt or "").strip()
        if prompt_package.review_status != "final-reviewed" or not prompt:
            raise FoundryTransportError(
                code=FailureCode.RESPONSE_SHAPE,
                message="Image generation requires a final reviewed prompt package.",
            )
        payload = {
            "model": self._config.deployment,
            "prompt": prompt,
            "width": prompt_package.generation.width,
            "height": prompt_package.generation.height,
        }
        raw = _post_json(
            url,
            payload,
            _base_headers(self._token_provider, scope=AI_FOUNDRY_SCOPE),
            operation="MAI image generation",
        )
        if _contains_content_filter_signal(raw):
            raise FoundryTransportError(
                code=FailureCode.CONTENT_FILTERED,
                message="MAI image generation response was content filtered.",
                body=json.dumps(raw),
            )
        encoded = _extract_base64_image(raw)
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FoundryTransportError(
                code=FailureCode.RESPONSE_SHAPE,
                message="Image generation response returned invalid base64 image data.",
                body=json.dumps(raw),
            ) from exc
        return ImageGenerationResult(
            image_bytes=image_bytes,
            mime_type="image/png",
            model=str(raw.get("model") or self._config.deployment),
            deployment=self._config.deployment,
            response_metadata={
                "operation": "mai_image_generation",
                "endpoint": endpoint,
                "deployment": self._config.deployment,
                "providerModel": raw.get("model") or self._config.deployment,
                "request": {
                    "promptChars": len(prompt),
                    "width": prompt_package.generation.width,
                    "height": prompt_package.generation.height,
                    "reviewStatus": prompt_package.review_status,
                },
                "response": {
                    "responseId": raw.get("id"),
                    "created": raw.get("created"),
                    "outputItemCount": _output_item_count(raw),
                    "contentFilterResult": _find_content_filter_details(raw),
                    "raw": raw,
                },
            },
        )
