"""Transaction boundary for SQLite repositories."""

from types import TracebackType

from sqlmodel import Session

from conductor.services.ports import AttemptRepository, JobRepository, WorkerRepository
from conductor.storage.database import Database
from conductor.storage.repositories import SqlAttemptRepository, SqlJobRepository, SqlWorkerRepository


class SqlUnitOfWork:
    """Create one session and repository set per application use case."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._session: Session | None = None
        self.jobs: JobRepository
        self.attempts: AttemptRepository
        self.workers: WorkerRepository

    def __enter__(self) -> "SqlUnitOfWork":
        self._session = self._database.session()
        self.jobs = SqlJobRepository(self._session)
        self.attempts = SqlAttemptRepository(self._session)
        self.workers = SqlWorkerRepository(self._session)
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
