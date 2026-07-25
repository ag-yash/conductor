"""End-to-end tests for the M3 worker control-plane contract."""

from typing import cast

from fastapi.testclient import TestClient

from tests.test_jobs_api import JOB_REQUEST

WORKER = {
    "worker_id": "demo-worker",
    "worker_instance_id": "process-a",
    "supported_tasks": ["text.generate"],
    "max_parallel_jobs": 1,
}


def _register(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/workers/register", json=WORKER)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _submit(client: TestClient, key: str = "worker-demo") -> dict[str, object]:
    response = client.post("/api/v1/jobs", headers={"Idempotency-Key": key}, json=JOB_REQUEST)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _headers(instance_id: str = "process-a") -> dict[str, str]:
    return {"Worker-Instance-ID": instance_id}


def test_worker_registers_heartbeats_and_replaces_a_restarted_process(client: TestClient) -> None:
    registered = _register(client)
    assert registered["status"] == "ready"
    assert registered["version"] == 0

    heartbeat = client.post("/api/v1/workers/demo-worker/heartbeat", headers=_headers())
    assert heartbeat.status_code == 200
    assert heartbeat.json()["version"] == 1

    restarted = client.post(
        "/api/v1/workers/register",
        json={**WORKER, "worker_instance_id": "process-b"},
    )
    assert restarted.status_code == 201
    assert restarted.json()["instance_id"] == "process-b"
    assert restarted.json()["version"] == 2

    stale = client.post("/api/v1/workers/demo-worker/heartbeat", headers=_headers())
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "worker_conflict"


def test_worker_polls_starts_and_completes_a_deterministic_job(client: TestClient) -> None:
    _register(client)
    job = _submit(client)

    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    assert lease.status_code == 200
    lease_body = lease.json()
    assert lease_body["job"]["id"] == job["id"]
    assert lease_body["job"]["status"] == "assigned"
    attempt_id = lease_body["attempt"]["id"]

    started = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/start",
        headers=_headers(),
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    completed = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/complete",
        headers=_headers(),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    assert completed.json()["active_attempt_id"] is None

    no_more_work = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    assert no_more_work.status_code == 204


def test_draining_worker_receives_no_new_work(client: TestClient) -> None:
    _register(client)
    _submit(client)

    drained = client.post("/api/v1/workers/demo-worker/drain", headers=_headers())
    assert drained.status_code == 200
    assert drained.json()["status"] == "draining"

    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    assert lease.status_code == 204


def test_worker_cannot_start_another_process_attempt(client: TestClient) -> None:
    _register(client)
    _submit(client)
    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    attempt_id = lease.json()["attempt"]["id"]

    rejected = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/start",
        headers=_headers("a-different-process"),
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "worker_conflict"
