"""Durable jobs API integration tests."""

from fastapi.testclient import TestClient
from httpx2 import Response

from conductor.config.settings import Settings
from conductor.main import create_app

JOB_REQUEST = {
    "task": "text.generate",
    "model_id": "qwen-demo",
    "input": {"prompt": "Explain idempotency simply."},
    "parameters": {"temperature": 0.2},
    "priority": "normal",
    "max_attempts": 3,
}


def _submit(client: TestClient, *, key: str = "demo-request-1") -> Response:
    return client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": key},
        json=JOB_REQUEST,
    )


def test_submit_get_list_and_cancel_job(client: TestClient) -> None:
    submitted = _submit(client)
    assert submitted.status_code == 201
    job = submitted.json()
    assert job["status"] == "queued"
    assert job["version"] == 0

    fetched = client.get(f"/api/v1/jobs/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job["id"]

    listed = client.get("/api/v1/jobs", params={"status": "queued"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [job["id"]]

    cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["version"] == 1

    cancelled_again = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert cancelled_again.status_code == 200
    assert cancelled_again.json()["version"] == 1


def test_identical_submission_replays_original_job(client: TestClient) -> None:
    first = _submit(client)
    replay = _submit(client)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]


def test_key_reuse_with_different_request_is_rejected(client: TestClient) -> None:
    assert _submit(client).status_code == 201
    changed_request = {**JOB_REQUEST, "model_id": "different-model"}

    response = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": "demo-request-1"},
        json=changed_request,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


def test_job_survives_application_restart(app_settings: Settings) -> None:
    with TestClient(create_app(app_settings)) as first_client:
        submitted = _submit(first_client, key="restart-demo")
        job_id = submitted.json()["id"]

    with TestClient(create_app(app_settings)) as restarted_client:
        fetched = restarted_client.get(f"/api/v1/jobs/{job_id}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == job_id


def test_missing_job_returns_stable_error(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_oversized_canonical_payload_is_rejected(app_settings: Settings) -> None:
    tiny_settings = app_settings.model_copy(update={"max_job_payload_bytes": 50})
    with TestClient(create_app(tiny_settings)) as tiny_client:
        response = _submit(tiny_client, key="large-request")

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
