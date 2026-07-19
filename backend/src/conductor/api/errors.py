"""Translate safe application failures into consistent HTTP responses."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from conductor.services.errors import (
    IdempotencyConflict,
    JobConflict,
    JobNotFound,
    PayloadTooLarge,
    ServiceError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Register expected service-error mappings in one place."""

    @app.exception_handler(JobNotFound)
    async def job_not_found(_request: Request, error: JobNotFound) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, "job_not_found", str(error))

    @app.exception_handler(IdempotencyConflict)
    async def idempotency_conflict(_request: Request, error: IdempotencyConflict) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "idempotency_conflict", str(error))

    @app.exception_handler(JobConflict)
    async def job_conflict(_request: Request, error: JobConflict) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "job_conflict", str(error))

    @app.exception_handler(PayloadTooLarge)
    async def payload_too_large(_request: Request, error: PayloadTooLarge) -> JSONResponse:
        return _error_response(status.HTTP_413_CONTENT_TOO_LARGE, "payload_too_large", str(error))

    @app.exception_handler(ServiceError)
    async def unexpected_service_error(_request: Request, error: ServiceError) -> JSONResponse:
        return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "service_error", str(error))


def _error_response(http_status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message}},
    )
