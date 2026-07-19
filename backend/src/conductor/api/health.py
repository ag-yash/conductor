"""Liveness and readiness endpoints.

Liveness answers whether the API process can serve requests. Readiness answers
whether the application has completed startup and may receive normal traffic.
"""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from conductor.config.settings import Settings

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    """Public liveness response."""

    status: Literal["ok"]
    service: str
    version: str


class ReadyResponse(BaseModel):
    """Public readiness response."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ready", "not_ready"]]


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/live", response_model=LiveResponse)
async def live(request: Request) -> LiveResponse:
    """Report that the API process is alive."""

    settings = _settings(request)
    return LiveResponse(status="ok", service=settings.service_name, version=settings.version)


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> ReadyResponse:
    """Report whether application startup has completed."""

    is_ready = bool(request.app.state.ready and request.app.state.database_ready)
    state: Literal["ready", "not_ready"] = "ready" if is_ready else "not_ready"
    application_state: Literal["ready", "not_ready"] = (
        "ready" if request.app.state.ready else "not_ready"
    )
    database_state: Literal["ready", "not_ready"] = (
        "ready" if request.app.state.database_ready else "not_ready"
    )
    return ReadyResponse(
        status=state,
        checks={"application": application_state, "database": database_state},
    )
