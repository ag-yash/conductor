"""Small HTTP client used by the Conductor command-line interface.

Keeping HTTP details here lets the command parser stay focused on user input.
It also makes CLI behaviour easy to test without starting a real web server.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CliError(Exception):
    """An expected operator-facing CLI error, safe to print to stderr."""


class HttpApiClient:
    """Call one already-running Conductor API over HTTP.

    The CLI intentionally uses Python's standard library instead of adding a
    second HTTP dependency. Conductor's production API does not need a richer
    client for this small, JSON-only control-plane interface.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Send a JSON request and decode the API's JSON response."""

        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request_headers = {"Accept": "application/json"}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if headers is not None:
            request_headers.update(headers)
        request = Request(
            url=f"{self._base_url}/{path.lstrip('/')}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=10) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as error:
            raise CliError(self._api_error(error)) from error
        except URLError as error:
            raise CliError(
                f"Cannot reach Conductor at {self._base_url}. "
                "Start it with 'conductor-api', then try again. "
                f"Network detail: {error.reason}"
            ) from error
        if not raw_body:
            return None
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise CliError("Conductor returned a response that was not valid JSON.") from error

    @staticmethod
    def _api_error(error: HTTPError) -> str:
        """Turn the API's structured error body into a short useful message."""

        raw_body = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return f"Conductor returned HTTP {error.code}: {raw_body or error.reason}"
        if isinstance(payload, dict):
            structured_error = payload.get("error")
            if isinstance(structured_error, dict):
                code = structured_error.get("code", "api_error")
                message = structured_error.get("message", error.reason)
                return f"Conductor rejected the request (HTTP {error.code}, {code}): {message}"
            detail = payload.get("detail")
            if detail is not None:
                return f"Conductor rejected the request (HTTP {error.code}): {detail}"
        return f"Conductor returned HTTP {error.code}: {raw_body or error.reason}"
