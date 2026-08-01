"""FastAPI application factory and local server entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from conductor.api.errors import register_error_handlers
from conductor.api.health import router as health_router
from conductor.api.jobs import router as jobs_router
from conductor.api.models import router as models_router
from conductor.api.workers import router as workers_router
from conductor.config.settings import Settings, get_settings
from conductor.core.logging import configure_logging
from conductor.core.request_context import RequestContextMiddleware
from conductor.runtime.manager import RuntimeManager
from conductor.services.jobs import JobService
from conductor.services.models import ModelService
from conductor.services.workers import WorkerService
from conductor.storage.database import Database
from conductor.storage.migrations import run_migrations
from conductor.storage.unit_of_work import SqlUnitOfWork


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an isolated application instance for production or tests."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    database = Database(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        run_migrations(resolved_settings.database_url)
        database.check_connection()
        application.state.database_ready = True
        application.state.ready = True
        try:
            yield
        finally:
            application.state.ready = False
            application.state.database_ready = False
            database.dispose()

    application = FastAPI(
        title="Conductor Control Plane",
        description="Local-first AI workload orchestration API.",
        version=resolved_settings.version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.ready = False
    application.state.database_ready = False
    application.state.job_service = JobService(
        lambda: SqlUnitOfWork(database),
        max_payload_bytes=resolved_settings.max_job_payload_bytes,
    )
    application.state.worker_service = WorkerService(
        lambda: SqlUnitOfWork(database),
        runtime_manager=RuntimeManager.default(),
    )
    application.state.model_service = ModelService(lambda: SqlUnitOfWork(database))
    application.add_middleware(RequestContextMiddleware)
    register_error_handlers(application)
    application.include_router(health_router, prefix=resolved_settings.api_prefix)
    application.include_router(jobs_router, prefix=resolved_settings.api_prefix)
    application.include_router(workers_router, prefix=resolved_settings.api_prefix)
    application.include_router(models_router, prefix=resolved_settings.api_prefix)
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
