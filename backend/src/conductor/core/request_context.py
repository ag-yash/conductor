"""Request correlation that is safe across concurrent async tasks."""

import logging
import re
import time
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

RequestId = str

REQUEST_ID_HEADER = b"x-request-id"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_request_id: ContextVar[RequestId | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("conductor.http")


def get_request_id() -> RequestId | None:
    """Return the correlation ID for the current async context."""

    return _request_id.get()


def _request_id_from_scope(scope: Scope) -> RequestId:
    candidate = Headers(scope=scope).get(REQUEST_ID_HEADER.decode("ascii"))
    if candidate is not None and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


class RequestContextMiddleware:
    """Attach a safe request ID and emit one completion log per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_from_scope(scope)
        token = _request_id.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            logger.info(
                "request_completed",
                extra={
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            _request_id.reset(token)
