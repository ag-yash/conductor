"""Control-plane health contract tests."""

import re

from fastapi.testclient import TestClient

from conductor.config.settings import Environment, Settings
from conductor.main import create_app


def test_liveness_returns_service_identity() -> None:
    settings = Settings(environment=Environment.TEST, version="test-version")

    with TestClient(create_app(settings)) as client:
        response = client.get(f"{settings.api_prefix}/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "conductor-control-plane",
        "version": "test-version",
    }


def test_readiness_reports_ready_after_startup() -> None:
    settings = Settings(environment=Environment.TEST)

    with TestClient(create_app(settings)) as client:
        response = client.get(f"{settings.api_prefix}/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"application": "ready"},
    }


def test_valid_request_id_is_preserved() -> None:
    settings = Settings(environment=Environment.TEST)

    with TestClient(create_app(settings)) as client:
        response = client.get(
            f"{settings.api_prefix}/health/live",
            headers={"X-Request-ID": "demo-request-42"},
        )

    assert response.headers["X-Request-ID"] == "demo-request-42"


def test_unsafe_request_id_is_replaced() -> None:
    settings = Settings(environment=Environment.TEST)

    with TestClient(create_app(settings)) as client:
        response = client.get(
            f"{settings.api_prefix}/health/live",
            headers={"X-Request-ID": "contains spaces"},
        )

    generated_request_id = response.headers["X-Request-ID"]
    assert generated_request_id != "contains spaces"
    assert re.fullmatch(r"[0-9a-f-]{36}", generated_request_id)
