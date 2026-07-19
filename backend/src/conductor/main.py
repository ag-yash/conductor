"""FastAPI application factory and local server entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from conductor.api.health import router as health_router
from conductor.config.settings import Settings, get_settings
from conductor.core.logging import configure_logging
from conductor.core.request_context import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated application instance for production or tests."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.ready = True
        try:
            yield
        finally:
            application.state.ready = False

    application = FastAPI(
        title="Conductor Control Plane",
        description="Local-first AI workload orchestration API.",
        version=resolved_settings.version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.ready = False
    application.add_middleware(RequestContextMiddleware)
    application.include_router(health_router, prefix=resolved_settings.api_prefix)
    return application


app = create_app()


def run() -> None:
    """Run the local development server using validated settings."""

    settings = get_settings()
    uvicorn.run(
        "conductor.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        factory=False,
    )
