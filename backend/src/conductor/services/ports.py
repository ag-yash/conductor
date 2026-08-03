"""Persistence interfaces required by application services."""

from types import TracebackType
from typing import Protocol, Self

from conductor.domain.attempt import ExecutionAttempt
from conductor.domain.benchmark import BenchmarkSummary
from conductor.domain.job import Job, JobStatus
from conductor.domain.model import ModelDefinition, ModelResidency
from conductor.domain.worker import Worker
from conductor.scheduler.policy import PlacementDecision, RecordedSchedulingDecision


class JobRepository(Protocol):
    """Operations the job service requires from persistence."""

    def get(self, job_id: str) -> Job | None: ...

    def get_by_idempotency_key(self, key: str) -> Job | None: ...

    def list(self, *, status: JobStatus | None, limit: int, offset: int) -> list[Job]: ...

    def add(self, job: Job) -> None: ...

    def update(self, job: Job, *, expected_version: int) -> None: ...

    def flush(self) -> None: ...


class AttemptRepository(Protocol):
    """Attempt persistence needed by the worker-lease service."""

    def add(self, attempt: ExecutionAttempt) -> None: ...

    def get(self, attempt_id: str) -> ExecutionAttempt | None: ...

    def update(self, attempt: ExecutionAttempt, *, expected_version: int) -> None: ...

    def count_active_for_worker(self, worker_id: str, instance_id: str) -> int: ...


class WorkerRepository(Protocol):
    """Worker registration persistence needed by worker operations."""

    def get(self, worker_id: str) -> Worker | None: ...

    def add(self, worker: Worker) -> None: ...

    def update(self, worker: Worker, *, expected_version: int) -> None: ...

    def list(self) -> list[Worker]: ...


class SchedulingDecisionRepository(Protocol):
    """Append-only records that explain scheduler outcomes."""

    def add(
        self,
        *,
        decision_id: str,
        job_id: str,
        decision: PlacementDecision,
        outcome: str,
    ) -> None: ...

    def list_for_job(self, job_id: str) -> list[RecordedSchedulingDecision]: ...


class ModelDefinitionRepository(Protocol):
    """Trusted model-configuration persistence required by the model service."""

    def add(self, model: ModelDefinition) -> None: ...

    def get(self, model_id: str) -> ModelDefinition | None: ...

    def list(self) -> list[ModelDefinition]: ...


class ModelResidencyRepository(Protocol):
    """Persistence operations for short-lived loaded-model snapshots."""

    def upsert(self, residency: ModelResidency) -> None: ...

    def list_for_worker(self, worker_id: str, instance_id: str) -> list[ModelResidency]: ...

    def delete(self, residency_id: str) -> None: ...


class BenchmarkSummaryRepository(Protocol):
    """Persistence operations for completed, comparable runtime benchmarks."""

    def add(self, summary: BenchmarkSummary) -> None: ...

    def list_for_worker(
        self, worker_id: str, instance_id: str, limit: int
    ) -> list[BenchmarkSummary]: ...


class UnitOfWork(Protocol):
    """One atomic application transaction."""

    jobs: JobRepository
    attempts: AttemptRepository
    workers: WorkerRepository
    scheduling_decisions: SchedulingDecisionRepository
    model_definitions: ModelDefinitionRepository
    model_residencies: ModelResidencyRepository
    benchmark_summaries: BenchmarkSummaryRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Creates independent unit-of-work instances."""

    def __call__(self) -> UnitOfWork: ...
