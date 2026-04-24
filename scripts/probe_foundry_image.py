from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.contracts import ArtistPromptPackage, ImageModelConfig, ImageSettings
from orchestrator.integrations.foundry import FoundryImageClient, FoundryTransportError, _mai_image_endpoint
from orchestrator.integrations.identity import ContainerAppsManagedIdentityTokenProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe MAI image generation locally using the production Python client.")
    parser.add_argument(
        "--endpoint",
        action="append",
        dest="endpoints",
        help="Candidate image endpoint. Repeat to try multiple values.",
    )
    parser.add_argument(
        "--deployment",
        default=os.environ.get("FOUNDRY_IMAGE_DEPLOYMENT") or os.environ.get("FOUNDRY_DEPLOYMENT"),
        help="Image deployment name.",
    )
    parser.add_argument(
        "--api-version",
        action="append",
        dest="api_versions",
        help="Candidate api-version to try. Repeat to try multiple values.",
    )
    parser.add_argument(
        "--omit-api-version",
        action="store_true",
        help="Also try omitting the api-version query parameter.",
    )
    parser.add_argument(
        "--prompt",
        default="A watercolor study of an orange cat napping in afternoon window light.",
        help="Prompt to send to the image model.",
    )
    parser.add_argument("--title", default="Local Probe")
    parser.add_argument("--artist-note", default="Local MAI probe run.")
    parser.add_argument("--prompt-summary", default="Local MAI probe prompt.")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file path for the first successful image.",
    )
    parser.add_argument(
        "--continue-on-success",
        action="store_true",
        help="Keep testing other candidates after the first success.",
    )
    return parser.parse_args()


def default_endpoints() -> list[str]:
    configured = os.environ.get("FOUNDRY_IMAGE_ENDPOINT") or os.environ.get("FOUNDRY_ENDPOINT")
    if not configured:
        return []
    endpoints: list[str] = []
    for candidate in (configured, _mai_image_endpoint(configured)):
        normalized = candidate.rstrip("/")
        if normalized and normalized not in endpoints:
            endpoints.append(normalized)
    return endpoints


def candidate_api_versions(args: argparse.Namespace) -> list[str | None]:
    candidates: list[str | None] = []
    env_value = os.environ.get("FOUNDRY_IMAGE_API_VERSION")
    for value in args.api_versions or []:
        if value not in candidates:
            candidates.append(value)
    if env_value and env_value not in candidates:
        candidates.append(env_value)
    if args.omit_api_version or not candidates:
        candidates.append(None)
    return candidates


def prompt_package(args: argparse.Namespace) -> ArtistPromptPackage:
    return ArtistPromptPackage(
        title=args.title,
        prompt=args.prompt,
        artist_note=args.artist_note,
        prompt_summary=args.prompt_summary,
        reviewed_prompt=args.prompt,
        review_status="final-reviewed",
        generation=ImageSettings(width=args.width, height=args.height),
    )


def main() -> int:
    args = parse_args()
    endpoints = [endpoint.rstrip("/") for endpoint in (args.endpoints or default_endpoints()) if endpoint.rstrip("/")]
    if not endpoints:
        print("No endpoint provided. Pass --endpoint or set FOUNDRY_IMAGE_ENDPOINT.", file=sys.stderr)
        return 2
    if not args.deployment:
        print("No deployment provided. Pass --deployment or set FOUNDRY_IMAGE_DEPLOYMENT.", file=sys.stderr)
        return 2

    provider = ContainerAppsManagedIdentityTokenProvider()
    package = prompt_package(args)
    versions = candidate_api_versions(args)
    failures = 0

    for endpoint in endpoints:
        for api_version in versions:
            client = FoundryImageClient(
                ImageModelConfig(
                    endpoint=endpoint,
                    deployment=args.deployment,
                    api_version=api_version,
                    settings=package.generation,
                ),
                token_provider=provider,
            )
            try:
                result = client.generate_image(package)
            except FoundryTransportError as exc:
                failures += 1
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "endpoint": endpoint,
                            "effectiveEndpoint": _mai_image_endpoint(endpoint),
                            "apiVersion": api_version,
                            "code": exc.code.value,
                            "message": exc.message,
                            "statusCode": exc.status_code,
                            "body": exc.body,
                        },
                        indent=2,
                    )
                )
                continue

            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(result.image_bytes)

            safe_metadata = {
                key: value
                for key, value in result.response_metadata.items()
                if key != "response"
            }
            response_meta = result.response_metadata.get("response", {}) or {}
            safe_metadata["response"] = {
                k: v for k, v in response_meta.items() if k != "raw"
            }
            print(
                json.dumps(
                    {
                        "ok": True,
                        "endpoint": endpoint,
                        "effectiveEndpoint": _mai_image_endpoint(endpoint),
                        "apiVersion": api_version,
                        "bytes": len(result.image_bytes),
                        "mimeType": result.mime_type,
                        "model": result.model,
                        "deployment": result.deployment,
                        "metadata": safe_metadata,
                        "output": str(args.output) if args.output else None,
                    },
                    indent=2,
                )
            )
            if not args.continue_on_success:
                return 0

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())