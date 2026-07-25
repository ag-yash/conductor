"""Persistence interfaces required by application services."""

from types import TracebackType
from typing import Protocol, Self

from conductor.domain.attempt import ExecutionAttempt
from conductor.domain.job import Job, JobStatus
from conductor.domain.worker import Worker


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


class WorkerRepository(Protocol):
    """Worker registration persistence needed by worker operations."""

    def get(self, worker_id: str) -> Worker | None: ...

    def add(self, worker: Worker) -> None: ...

    def update(self, worker: Worker, *, expected_version: int) -> None: ...


class UnitOfWork(Protocol):
    """One atomic application transaction."""

    jobs: JobRepository
    attempts: AttemptRepository
    workers: WorkerRepository

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
