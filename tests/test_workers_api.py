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


def _register_fixture_model(client: TestClient, *, idle_timeout_seconds: int = 300) -> None:
    response = client.post(
        "/api/v1/models",
        json={
            "id": "qwen-demo",
            "display_name": "Deterministic demo model",
            "runtime_kind": "fixture",
            "artifact": "fixture://qwen-demo",
            "supported_tasks": ["text.generate"],
            "expected_memory_bytes": 1,
            "idle_timeout_seconds": idle_timeout_seconds,
        },
    )
    assert response.status_code == 201


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


def test_worker_executes_fixture_runtime_and_persists_result(client: TestClient) -> None:
    _register_fixture_model(client)
    _register(client)
    _submit(client, key="runtime-demo")
    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    attempt_id = lease.json()["attempt"]["id"]

    started = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/start",
        headers=_headers(),
    )
    assert started.status_code == 200

    executed = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/execute",
        headers=_headers(),
    )
    assert executed.status_code == 200
    body = executed.json()
    assert body["status"] == "succeeded"
    assert body["result"]["fixture_digest"]
    assert body["error_message"] is None

    fetched = client.get(f"/api/v1/jobs/{body['id']}")
    assert fetched.json()["result"] == body["result"]


def test_runtime_failure_marks_attempt_and_job_failed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/models",
        json={
            "id": "ollama-demo",
            "display_name": "Unavailable Ollama demo",
            "runtime_kind": "ollama",
            "artifact": "qwen3:0.6b",
            "supported_tasks": ["text.generate"],
            "expected_memory_bytes": 1,
            "idle_timeout_seconds": 300,
        },
    )
    assert response.status_code == 201
    _register(client)
    job_request = {**JOB_REQUEST, "model_id": "ollama-demo"}
    response = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": "runtime-failure"},
        json=job_request,
    )
    assert response.status_code == 201
    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    attempt_id = lease.json()["attempt"]["id"]
    client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/start",
        headers=_headers(),
    )

    executed = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/execute",
        headers=_headers(),
    )
    assert executed.status_code == 502
    fetched = client.get(f"/api/v1/jobs/{response.json()['id']}")
    assert fetched.json()["status"] == "failed"
    assert "Ollama request failed" in fetched.json()["error_message"]


def test_worker_persists_and_evicts_idle_fixture_residency(client: TestClient) -> None:
    _register_fixture_model(client, idle_timeout_seconds=0)
    _register(client)
    _submit(client, key="eviction-demo")
    lease = client.post("/api/v1/workers/demo-worker/leases/next", headers=_headers())
    attempt_id = lease.json()["attempt"]["id"]
    client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/start",
        headers=_headers(),
    )
    executed = client.post(
        f"/api/v1/workers/demo-worker/attempts/{attempt_id}/execute",
        headers=_headers(),
    )
    assert executed.status_code == 200

    residencies = client.get("/api/v1/workers/demo-worker/residencies", headers=_headers())
    assert residencies.status_code == 200
    assert residencies.json()[0]["status"] == "ready"
    assert residencies.json()[0]["active_execution_count"] == 0

    evicted = client.post("/api/v1/workers/demo-worker/evict-idle", headers=_headers())
    assert evicted.status_code == 200
    assert [item["status"] for item in evicted.json()] == ["unloading"]

    after_eviction = client.get("/api/v1/workers/demo-worker/residencies", headers=_headers())
    assert after_eviction.status_code == 200
    assert after_eviction.json() == []


def test_worker_benchmark_records_warm_runtime_summary(client: TestClient) -> None:
    _register_fixture_model(client)
    _register(client)

    benchmark = client.post(
        "/api/v1/workers/demo-worker/benchmarks",
        headers=_headers(),
        json={
            "model_id": "qwen-demo",
            "task": "text.generate",
            "input": {"prompt": "Explain a warm model."},
            "parameters": {"temperature": 0.2},
            "warmup_iterations": 1,
            "measurement_iterations": 2,
        },
    )

    assert benchmark.status_code == 200
    summary = benchmark.json()
    assert summary["warmup_iterations"] == 1
    assert summary["measurement_iterations"] == 2
    assert summary["mean_wall_time_ms"] >= 0
    assert summary["min_wall_time_ms"] <= summary["max_wall_time_ms"]
    assert summary["mean_runtime_metrics"]["input_bytes"] > 0

    history = client.get("/api/v1/workers/demo-worker/benchmarks", headers=_headers())
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [summary["id"]]

    residencies = client.get("/api/v1/workers/demo-worker/residencies", headers=_headers())
    assert residencies.json()[0]["status"] == "ready"
