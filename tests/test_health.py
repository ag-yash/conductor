"""Control-plane health contract tests."""

import re

from fastapi.testclient import TestClient

from conductor.config.settings import Settings


def test_liveness_returns_service_identity(client: TestClient, app_settings: Settings) -> None:
    response = client.get(f"{app_settings.api_prefix}/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "conductor-control-plane",
        "version": "test-version",
    }


def test_readiness_reports_ready_after_startup(client: TestClient, app_settings: Settings) -> None:
    response = client.get(f"{app_settings.api_prefix}/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"application": "ready", "database": "ready"},
    }


def test_valid_request_id_is_preserved(client: TestClient, app_settings: Settings) -> None:
    response = client.get(
        f"{app_settings.api_prefix}/health/live",
        headers={"X-Request-ID": "demo-request-42"},
    )

    assert response.headers["X-Request-ID"] == "demo-request-42"


def test_unsafe_request_id_is_replaced(client: TestClient, app_settings: Settings) -> None:
    response = client.get(
        f"{app_settings.api_prefix}/health/live",
        headers={"X-Request-ID": "contains spaces"},
    )

    generated_request_id = response.headers["X-Request-ID"]
    assert generated_request_id != "contains spaces"
    assert re.fullmatch(r"[0-9a-f-]{36}", generated_request_id)
