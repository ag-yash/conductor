"""Integration tests for deterministic, explainable M4 placement."""

from typing import cast

from fastapi.testclient import TestClient

from tests.test_jobs_api import JOB_REQUEST


def _register(client: TestClient, worker_id: str, max_parallel_jobs: int = 1) -> None:
    response = client.post(
        "/api/v1/workers/register",
        json={
            "worker_id": worker_id,
            "worker_instance_id": f"{worker_id}-process",
            "supported_tasks": ["text.generate"],
            "max_parallel_jobs": max_parallel_jobs,
        },
    )
    assert response.status_code == 201


def _headers(worker_id: str) -> dict[str, str]:
    return {"Worker-Instance-ID": f"{worker_id}-process"}


def _submit(client: TestClient, key: str) -> dict[str, object]:
    response = client.post("/api/v1/jobs", headers={"Idempotency-Key": key}, json=JOB_REQUEST)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _report_ready_residency(client: TestClient, worker_id: str) -> None:
    response = client.post(
        f"/api/v1/workers/{worker_id}/residencies",
        headers=_headers(worker_id),
        json={
            "id": f"{worker_id}:{worker_id}-process:qwen-demo",
            "model_id": "qwen-demo",
            "model_revision": 1,
            "status": "ready",
            "active_execution_count": 0,
            "measured_memory_bytes": None,
            "loaded_at": "2026-08-30T00:00:00Z",
            "last_used_at": "2026-08-30T00:00:00Z",
            "failure_message": None,
            "created_at": "2026-08-30T00:00:00Z",
            "updated_at": "2026-08-30T00:00:00Z",
            "version": 1,
        },
    )
    assert response.status_code == 200


def test_scheduler_prefers_capacity_and_records_its_reason(client: TestClient) -> None:
    _register(client, "worker-a")
    _register(client, "worker-b", max_parallel_jobs=2)

    _submit(client, "first-job")
    first_lease = client.post("/api/v1/workers/worker-a/leases/next", headers=_headers("worker-a"))
    assert first_lease.status_code == 200
    first_attempt_id = first_lease.json()["attempt"]["id"]
    started = client.post(
        f"/api/v1/workers/worker-a/attempts/{first_attempt_id}/start",
        headers=_headers("worker-a"),
    )
    assert started.status_code == 200

    second_job = _submit(client, "second-job")
    waiting = client.post("/api/v1/workers/worker-a/leases/next", headers=_headers("worker-a"))
    assert waiting.status_code == 204

    assigned = client.post("/api/v1/workers/worker-b/leases/next", headers=_headers("worker-b"))
    assert assigned.status_code == 200
    assert assigned.json()["job"]["id"] == second_job["id"]

    decisions = client.get(f"/api/v1/jobs/{second_job['id']}/scheduling-decisions")
    assert decisions.status_code == 200
    body = decisions.json()
    assert body[0]["outcome"] == "selected_other_worker"
    candidates = {candidate["worker_id"]: candidate for candidate in body[0]["candidates"]}
    assert candidates["worker-a"]["reason"] == "no_free_slots"
    assert candidates["worker-b"]["reason"] == "eligible"


def test_scheduler_prefers_an_eligible_worker_with_a_warm_model(client: TestClient) -> None:
    _register(client, "worker-a")
    _register(client, "worker-b")
    _report_ready_residency(client, "worker-b")
    job = _submit(client, "resident-model-job")

    not_selected = client.post("/api/v1/workers/worker-a/leases/next", headers=_headers("worker-a"))
    assert not_selected.status_code == 204

    selected = client.post("/api/v1/workers/worker-b/leases/next", headers=_headers("worker-b"))
    assert selected.status_code == 200
    assert selected.json()["job"]["id"] == job["id"]

    decisions = client.get(f"/api/v1/jobs/{job['id']}/scheduling-decisions").json()
    assert decisions[0]["reason"] == "resident_model_preferred"
    candidates = {candidate["worker_id"]: candidate for candidate in decisions[0]["candidates"]}
    assert candidates["worker-a"]["model_is_resident"] is False
    assert candidates["worker-b"]["model_is_resident"] is True
