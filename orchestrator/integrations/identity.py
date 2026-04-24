from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from urllib import error
from urllib import parse, request

from ..contracts import FailureCode
from .foundry import FoundryTransportError


@dataclass(slots=True)
class ContainerAppsManagedIdentityTokenProvider:
    client_id: str | None = os.environ.get("AZURE_CLIENT_ID")

    def get_token(self, scope: str) -> str:
        endpoint = os.environ.get("IDENTITY_ENDPOINT")
        header = os.environ.get("IDENTITY_HEADER")
        resource = scope.removesuffix("/.default")
        if endpoint and header:
            query = {
                "resource": resource,
                "api-version": "2019-08-01",
            }
            if self.client_id:
                query["client_id"] = self.client_id
            token_url = f"{endpoint}?{parse.urlencode(query)}"
            req = request.Request(token_url, headers={"X-IDENTITY-HEADER": header}, method="GET")
            try:
                with request.urlopen(req) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except error.URLError as exc:
                raise FoundryTransportError(
                    code=FailureCode.AUTH,
                    message=f"Managed identity token request failed: {exc.reason}",
                ) from exc
            token = payload.get("access_token")
            if token:
                return token
        fallback = os.environ.get("AZURE_ACCESS_TOKEN")
        if fallback:
            return fallback
        azure_cli = shutil.which("az") or shutil.which("az.cmd")
        try:
            completed = subprocess.run(
                [
                    azure_cli or "az",
                    "account",
                    "get-access-token",
                    "--resource",
                    resource,
                    "--query",
                    "accessToken",
                    "-o",
                    "tsv",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise FoundryTransportError(
                code=FailureCode.AUTH,
                message="Managed identity token endpoint is not available.",
            ) from exc
        token = completed.stdout.strip()
        if token:
            return token
        raise FoundryTransportError(
            code=FailureCode.AUTH,
            message="Managed identity token endpoint is not available.",
        )
