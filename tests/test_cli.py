"""Tests for the CLI's mapping of friendly commands to existing HTTP contracts."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from conductor.cli.client import CliError
from conductor.cli.main import run


class FakeApiClient:
    """Record calls so CLI tests prove intent without opening a network socket."""

    def __init__(self, response: Any | None = None, error: CliError | None = None) -> None:
        self.response = {"status": "ok"} if response is None else response
        self.error = error
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
        if self.error is not None:
            raise self.error
        return self.response


def _run(client: FakeApiClient, *arguments: str) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    code = run(arguments, client, stdout, stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_cli_checks_readiness() -> None:
    client = FakeApiClient(response={"status": "ready"})

    code, stdout, stderr = _run(client, "health")

    assert code == 0
    assert '"status": "ready"' in stdout
    assert stderr == ""
    assert client.calls == [
        {"method": "GET", "path": "health/ready", "payload": None, "headers": None}
    ]


def test_cli_submits_job_from_json_file_with_idempotency_key(tmp_path: Path) -> None:
    payload_file = tmp_path / "job.json"
    payload_file.write_text(
        '{"task": "text.generate", "model_id": "fixture-demo", "input": {"prompt": "Hi"}}',
        encoding="utf-8",
    )
    client = FakeApiClient(response={"id": "job-1"})

    code, stdout, stderr = _run(
        client,
        "jobs",
        "submit",
        "--file",
        str(payload_file),
        "--idempotency-key",
        "demo-1",
    )

    assert code == 0
    assert '"id": "job-1"' in stdout
    assert stderr == ""
    assert client.calls == [
        {
            "method": "POST",
            "path": "jobs",
            "payload": {
                "task": "text.generate",
                "model_id": "fixture-demo",
                "input": {"prompt": "Hi"},
            },
            "headers": {"Idempotency-Key": "demo-1"},
        }
    ]


def test_cli_runs_benchmark_with_worker_instance_header(tmp_path: Path) -> None:
    payload_file = tmp_path / "benchmark.json"
    payload_file.write_text(
        '{"model_id": "fixture-demo", "task": "text.generate"}', encoding="utf-8"
    )
    client = FakeApiClient(response={"measurement_iterations": 3})

    code, _, stderr = _run(
        client,
        "benchmarks",
        "run",
        "--worker-id",
        "demo-worker",
        "--instance-id",
        "process-a",
        "--file",
        str(payload_file),
    )

    assert code == 0
    assert stderr == ""
    assert client.calls[0]["path"] == "workers/demo-worker/benchmarks"
    assert client.calls[0]["headers"] == {"Worker-Instance-ID": "process-a"}


def test_cli_reports_worker_resource_snapshot_from_json_file(tmp_path: Path) -> None:
    payload_file = tmp_path / "resources.json"
    payload_file.write_text(
        '{"host_cpu_percent": 20, "host_total_memory_bytes": 8192, '
        '"host_available_memory_bytes": 4096, "process_cpu_percent": 4, '
        '"process_memory_bytes": 512}',
        encoding="utf-8",
    )
    client = FakeApiClient(response={"id": "snapshot-1"})

    code, _, stderr = _run(
        client,
        "workers",
        "report-resources",
        "--worker-id",
        "demo-worker",
        "--instance-id",
        "process-a",
        "--file",
        str(payload_file),
    )

    assert code == 0
    assert stderr == ""
    assert client.calls == [
        {
            "method": "POST",
            "path": "workers/demo-worker/resource-snapshots",
            "payload": {
                "host_cpu_percent": 20,
                "host_total_memory_bytes": 8192,
                "host_available_memory_bytes": 4096,
                "process_cpu_percent": 4,
                "process_memory_bytes": 512,
            },
            "headers": {"Worker-Instance-ID": "process-a"},
        }
    ]


def test_cli_explains_api_errors_without_traceback() -> None:
    client = FakeApiClient(error=CliError("Cannot reach Conductor."))

    code, stdout, stderr = _run(client, "health", "live")

    assert code == 1
    assert stdout == ""
    assert stderr == "error: Cannot reach Conductor.\n"


def test_cli_reports_invalid_json_payload_file(tmp_path: Path) -> None:
    payload_file = tmp_path / "broken.json"
    payload_file.write_text("not JSON", encoding="utf-8")
    client = FakeApiClient()

    code, stdout, stderr = _run(
        client,
        "models",
        "register",
        "--file",
        str(payload_file),
    )

    assert code == 1
    assert stdout == ""
    assert "Payload file is not valid JSON" in stderr
    assert client.calls == []
