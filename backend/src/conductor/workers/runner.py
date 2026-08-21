"""A small, long-running local process that drives the worker HTTP protocol."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

import psutil

from conductor.cli.client import CliError, HttpApiClient
from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.runtime.base import RuntimeAdapterError
from conductor.runtime.manager import RuntimeManager

DEFAULT_API_URL = "http://127.0.0.1:8080/api/v1"


class WorkerApiClient(Protocol):
    """The small API surface the process needs, kept easy to fake in tests."""

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...


class ResourceSampler(Protocol):
    """Reports measurements for the host and the process running this worker."""

    def sample(self) -> dict[str, float | int]: ...


class PsutilResourceSampler:
    """Collect local measurements without exposing host paths or process lists."""

    def __init__(self) -> None:
        self._process = psutil.Process()
        # Prime psutil's non-blocking process CPU calculation. The first reading
        # is intentionally discarded because it represents no time interval.
        self._process.cpu_percent(interval=None)

    def sample(self) -> dict[str, float | int]:
        memory = psutil.virtual_memory()
        return {
            "host_cpu_percent": psutil.cpu_percent(interval=0.1),
            "host_total_memory_bytes": memory.total,
            "host_available_memory_bytes": memory.available,
            "process_cpu_percent": self._process.cpu_percent(interval=None),
            "process_memory_bytes": self._process.memory_info().rss,
        }


@dataclass(frozen=True, slots=True)
class WorkerProcessConfig:
    """Configuration owned by one worker process, not by the control plane."""

    worker_id: str
    instance_id: str
    supported_tasks: tuple[str, ...]
    max_parallel_jobs: int
    heartbeat_seconds: float
    resource_report_seconds: float
    poll_seconds: float

    def __post_init__(self) -> None:
        if not self.worker_id or not self.instance_id or not self.supported_tasks:
            raise ValueError("worker ID, instance ID, and at least one task are required")
        # This first process intentionally executes one lease at a time. The
        # control plane can represent more slots, but advertising them before
        # the process can run work concurrently would make scheduling lie.
        if self.max_parallel_jobs != 1:
            raise ValueError("the standalone worker currently supports exactly one parallel job")
        if min(self.heartbeat_seconds, self.resource_report_seconds, self.poll_seconds) <= 0:
            raise ValueError("worker intervals must be positive")


class WorkerRunner:
    """Turn an API protocol into an interruptible, observable worker loop.

    The runner intentionally uses one short request per state transition. The
    API remains the authority for job state, while this process owns its local
    liveness and CPU/RAM observations.
    """

    def __init__(
        self,
        config: WorkerProcessConfig,
        client: WorkerApiClient,
        sampler: ResourceSampler,
        runtime_manager: RuntimeManager | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._client = client
        self._sampler = sampler
        # This cache belongs to this OS process. When the worker exits, its
        # models leave memory too; the database only retains an observation.
        self._runtime_manager = runtime_manager or RuntimeManager.default()
        self._clock = clock
        self._sleep = sleep
        self._running = True
        self._next_heartbeat_at = 0.0
        self._next_resource_report_at = 0.0

    @property
    def _headers(self) -> dict[str, str]:
        return {"Worker-Instance-ID": self._config.instance_id}

    @property
    def _worker_path(self) -> str:
        return f"workers/{self._config.worker_id}"

    def register(self) -> None:
        """Claim the configured logical worker identity for this process."""

        self._client.request(
            "POST",
            "workers/register",
            payload={
                "worker_id": self._config.worker_id,
                "worker_instance_id": self._config.instance_id,
                "supported_tasks": list(self._config.supported_tasks),
                "max_parallel_jobs": self._config.max_parallel_jobs,
            },
        )

    def run_once(self) -> bool:
        """Report due observations, then claim and execute at most one job.

        Returning whether work was found lets the loop use a quiet poll delay
        while tests can verify a single iteration without sleeping.
        """

        now = self._clock()
        if now >= self._next_heartbeat_at:
            self._client.request("POST", f"{self._worker_path}/heartbeat", headers=self._headers)
            self._next_heartbeat_at = now + self._config.heartbeat_seconds
        if now >= self._next_resource_report_at:
            self._client.request(
                "POST",
                f"{self._worker_path}/resource-snapshots",
                payload=self._sampler.sample(),
                headers=self._headers,
            )
            self._next_resource_report_at = now + self._config.resource_report_seconds

        # Idle eviction must run in the same OS process that owns loaded model
        # memory. The API can persist the observation, but it cannot free this
        # worker's memory from another process.
        self._evict_idle_models()

        lease = self._client.request(
            "POST", f"{self._worker_path}/leases/next", headers=self._headers
        )
        if lease is None:
            return False

        # The server returns a complete lease object. Treat malformed data as a
        # process error instead of sending an accidental request to a wrong path.
        if not isinstance(lease, dict) or not isinstance(lease.get("attempt"), dict):
            raise CliError("Conductor returned a malformed worker lease.")
        attempt_id = lease["attempt"].get("id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise CliError("Conductor returned a worker lease without an attempt ID.")
        attempt_path = f"{self._worker_path}/attempts/{attempt_id}"
        self._client.request("POST", f"{attempt_path}/start", headers=self._headers)
        model = self._model_from_lease(lease)
        try:
            result = self._runtime_manager.execute(
                model=model,
                worker_id=self._config.worker_id,
                worker_instance_id=self._config.instance_id,
                task=str(lease["job"]["task"]),
                input=self._mapping(lease["job"].get("input"), "job input"),
                parameters=self._mapping(lease["job"].get("parameters"), "job parameters"),
            )
        except RuntimeAdapterError as error:
            self._report_residency(model)
            self._client.request(
                "POST",
                f"{attempt_path}/fail",
                payload={"error_message": str(error)},
                headers=self._headers,
            )
            return True

        self._report_residency(model)
        self._client.request(
            "POST",
            f"{attempt_path}/complete",
            payload={"result": dict(result.output)},
            headers=self._headers,
        )
        return True

    def _report_residency(self, model: ModelDefinition) -> None:
        """Send the worker-local loaded-model state to the durable API view."""

        residency = self._runtime_manager.residency(
            worker_id=self._config.worker_id,
            worker_instance_id=self._config.instance_id,
            model_id=model.id,
        )
        if residency is None:
            return
        self._client.request(
            "POST",
            f"{self._worker_path}/residencies",
            payload={
                "id": residency.id,
                "model_id": residency.model_id,
                "model_revision": residency.model_revision,
                "status": residency.status.value,
                "active_execution_count": residency.active_execution_count,
                "measured_memory_bytes": residency.measured_memory_bytes,
                "loaded_at": self._timestamp(residency.loaded_at),
                "last_used_at": self._timestamp(residency.last_used_at),
                "failure_message": residency.failure_message,
                "created_at": self._timestamp(residency.created_at),
                "updated_at": self._timestamp(residency.updated_at),
                "version": residency.version,
            },
            headers=self._headers,
        )

    def _evict_idle_models(self) -> None:
        """Unload this process's idle models and remove their durable snapshots."""

        evicted = self._runtime_manager.evict_idle(
            worker_id=self._config.worker_id,
            worker_instance_id=self._config.instance_id,
        )
        for residency in evicted:
            self._client.request(
                "DELETE",
                f"{self._worker_path}/residencies/{residency.model_id}",
                headers=self._headers,
            )

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _mapping(value: Any, description: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise CliError(f"Conductor returned malformed {description} in a worker lease.")
        return value

    def _model_from_lease(self, lease: dict[str, Any]) -> ModelDefinition:
        """Rebuild trusted model configuration sent with the leased job."""

        raw_model = lease.get("model")
        if not isinstance(raw_model, dict):
            raise CliError("Conductor returned a worker lease without model configuration.")
        try:
            return ModelDefinition(
                id=str(raw_model["id"]),
                display_name=str(raw_model["display_name"]),
                runtime_kind=RuntimeKind(str(raw_model["runtime_kind"])),
                artifact=str(raw_model["artifact"]),
                supported_tasks=frozenset(str(item) for item in raw_model["supported_tasks"]),
                expected_memory_bytes=int(raw_model["expected_memory_bytes"]),
                idle_timeout_seconds=int(raw_model["idle_timeout_seconds"]),
                enabled=bool(raw_model["enabled"]),
                revision=int(raw_model["revision"]),
                created_at=datetime.fromisoformat(str(raw_model["created_at"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise CliError(
                "Conductor returned malformed model configuration in a worker lease."
            ) from error

    def run_forever(self) -> None:
        """Run until a signal requests graceful draining and shutdown."""

        self.register()
        try:
            while self._running:
                worked = self.run_once()
                if not worked:
                    self._sleep(self._config.poll_seconds)
        finally:
            # Signal handlers should only request a stop. The normal loop is
            # responsible for this network call so shutdown stays predictable.
            self._client.request("POST", f"{self._worker_path}/drain", headers=self._headers)

    def request_stop(self) -> None:
        """Ask the loop to stop claiming work at its next safe boundary."""

        self._running = False


def build_parser() -> argparse.ArgumentParser:
    """Build a focused grammar for the worker process executable."""

    parser = argparse.ArgumentParser(
        prog="conductor-worker",
        description="Run one local Conductor worker process.",
    )
    parser.add_argument("--api-url", default=os.getenv("CONDUCTOR_API_URL", DEFAULT_API_URL))
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--instance-id", default=f"process-{uuid4()}")
    parser.add_argument("--task", action="append", dest="tasks", required=True)
    parser.add_argument("--max-parallel-jobs", type=int, default=1)
    parser.add_argument("--heartbeat-seconds", type=float, default=5.0)
    parser.add_argument("--resource-report-seconds", type=float, default=5.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start a worker and translate expected shutdown/errors into exit codes."""

    args = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        config = WorkerProcessConfig(
            worker_id=args.worker_id,
            instance_id=args.instance_id,
            supported_tasks=tuple(args.tasks),
            max_parallel_jobs=args.max_parallel_jobs,
            heartbeat_seconds=args.heartbeat_seconds,
            resource_report_seconds=args.resource_report_seconds,
            poll_seconds=args.poll_seconds,
        )
    except ValueError as error:
        build_parser().error(str(error))
    runner = WorkerRunner(config, HttpApiClient(args.api_url), PsutilResourceSampler())

    def request_stop(_signum: int, _frame: Any) -> None:
        runner.request_stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        runner.run_forever()
    except CliError as error:
        print(f"worker error: {error}", file=sys.stderr)
        return 1
    return 0
