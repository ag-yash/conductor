"""Transaction boundary for SQLite repositories."""

from types import TracebackType

from sqlmodel import Session

from conductor.services.ports import (
    AttemptRepository,
    BenchmarkSummaryRepository,
    JobRepository,
    ModelDefinitionRepository,
    ModelResidencyRepository,
    SchedulingDecisionRepository,
    WorkerRepository,
    WorkerResourceSnapshotRepository,
)
from conductor.storage.database import Database
from conductor.storage.repositories import (
    SqlAttemptRepository,
    SqlBenchmarkSummaryRepository,
    SqlJobRepository,
    SqlModelDefinitionRepository,
    SqlModelResidencyRepository,
    SqlSchedulingDecisionRepository,
    SqlWorkerRepository,
    SqlWorkerResourceSnapshotRepository,
)


class SqlUnitOfWork:
    """Create one session and repository set per application use case."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._session: Session | None = None
        self.jobs: JobRepository
        self.attempts: AttemptRepository
        self.workers: WorkerRepository
        self.scheduling_decisions: SchedulingDecisionRepository
        self.model_definitions: ModelDefinitionRepository
        self.model_residencies: ModelResidencyRepository
        self.benchmark_summaries: BenchmarkSummaryRepository
        self.worker_resource_snapshots: WorkerResourceSnapshotRepository

    def __enter__(self) -> "SqlUnitOfWork":
        # Every repository below shares one SQLite session. That gives a service one
        # all-or-nothing transaction boundary across jobs, attempts, and decisions.
        self._session = self._database.session()
        self.jobs = SqlJobRepository(self._session)
        self.attempts = SqlAttemptRepository(self._session)
        self.workers = SqlWorkerRepository(self._session)
        self.scheduling_decisions = SqlSchedulingDecisionRepository(self._session)
        self.model_definitions = SqlModelDefinitionRepository(self._session)
        self.model_residencies = SqlModelResidencyRepository(self._session)
        self.benchmark_summaries = SqlBenchmarkSummaryRepository(self._session)
        self.worker_resource_snapshots = SqlWorkerResourceSnapshotRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        self._session.rollback()
