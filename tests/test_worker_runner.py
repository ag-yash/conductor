"""Tests for the standalone worker's protocol and timing behaviour."""

from __future__ import annotations

from collections import deque
from typing import Any

from conductor.workers.runner import WorkerProcessConfig, WorkerRunner


class FakeWorkerApi:
    """Record protocol calls without needing an API server or a real process."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = deque(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        self.calls.append({"method": method, "path": path, "payload": payload, "headers": headers})
        return self._responses.popleft() if self._responses else {"status": "ok"}


class FakeSampler:
    def sample(self) -> dict[str, float | int]:
        return {
            "host_cpu_percent": 25.0,
            "host_total_memory_bytes": 8_000,
            "host_available_memory_bytes": 5_000,
            "process_cpu_percent": 5.0,
            "process_memory_bytes": 500,
        }


def _config() -> WorkerProcessConfig:
    return WorkerProcessConfig(
        worker_id="demo-worker",
        instance_id="process-a",
        supported_tasks=("text.generate",),
        max_parallel_jobs=1,
        heartbeat_seconds=5,
        resource_report_seconds=5,
        poll_seconds=1,
    )


def test_worker_registers_reports_resources_and_executes_one_lease() -> None:
    clock = [0.0]
    client = FakeWorkerApi(
        [
            {"status": "ready"},  # registration
            {"status": "ready"},  # heartbeat
            {"id": "snapshot-1"},  # resource report
            {"job": {"id": "job-1"}, "attempt": {"id": "attempt-1"}},
            {"status": "running"},
            {"status": "succeeded"},
        ]
    )
    runner = WorkerRunner(_config(), client, FakeSampler(), clock=lambda: clock[0])

    runner.register()
    did_work = runner.run_once()

    assert did_work is True
    assert [call["path"] for call in client.calls] == [
        "workers/register",
        "workers/demo-worker/heartbeat",
        "workers/demo-worker/resource-snapshots",
        "workers/demo-worker/leases/next",
        "workers/demo-worker/attempts/attempt-1/start",
        "workers/demo-worker/attempts/attempt-1/execute",
    ]
    assert client.calls[2]["payload"] == FakeSampler().sample()
    assert client.calls[3]["headers"] == {"Worker-Instance-ID": "process-a"}


def test_worker_does_not_repeat_due_reports_before_their_intervals() -> None:
    clock = [0.0]
    client = FakeWorkerApi([{"status": "ready"}, {"id": "snapshot-1"}, None, None])
    runner = WorkerRunner(_config(), client, FakeSampler(), clock=lambda: clock[0])

    assert runner.run_once() is False
    clock[0] = 1.0
    assert runner.run_once() is False

    assert [call["path"] for call in client.calls] == [
        "workers/demo-worker/heartbeat",
        "workers/demo-worker/resource-snapshots",
        "workers/demo-worker/leases/next",
        "workers/demo-worker/leases/next",
    ]


def test_worker_drains_after_a_stop_request() -> None:
    client = FakeWorkerApi(
        [
            {"status": "ready"},  # registration
            {"status": "ready"},  # heartbeat
            {"id": "snapshot-1"},  # resource report
            None,  # no lease, so the loop sleeps
            {"status": "draining"},
        ]
    )
    runner: WorkerRunner

    def stop_during_first_sleep(_seconds: float) -> None:
        runner.request_stop()

    runner = WorkerRunner(_config(), client, FakeSampler(), sleep=stop_during_first_sleep)
    runner.run_forever()

    assert [call["path"] for call in client.calls] == [
        "workers/register",
        "workers/demo-worker/heartbeat",
        "workers/demo-worker/resource-snapshots",
        "workers/demo-worker/leases/next",
        "workers/demo-worker/drain",
    ]
    assert client.calls[-1] == {
        "method": "POST",
        "path": "workers/demo-worker/drain",
        "payload": None,
        "headers": {"Worker-Instance-ID": "process-a"},
    }


def test_worker_rejects_parallel_capacity_it_cannot_execute() -> None:
    config = _config()

    try:
        WorkerProcessConfig(
            worker_id=config.worker_id,
            instance_id=config.instance_id,
            supported_tasks=config.supported_tasks,
            max_parallel_jobs=2,
            heartbeat_seconds=config.heartbeat_seconds,
            resource_report_seconds=config.resource_report_seconds,
            poll_seconds=config.poll_seconds,
        )
    except ValueError as error:
        assert "exactly one" in str(error)
    else:
        raise AssertionError("expected unsupported parallel worker capacity to be rejected")
