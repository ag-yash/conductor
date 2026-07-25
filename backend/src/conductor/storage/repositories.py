"""SQLModel repository implementations and domain-record translation."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from conductor.domain.job import Job, JobPriority, JobStatus
from conductor.models.records import JobRecord
from conductor.storage.errors import ConcurrentUpdate, DuplicateIdempotencyKey


def _aware(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)


def _to_domain(record: JobRecord) -> Job:
    return Job(
        id=record.id,
        idempotency_key=record.idempotency_key,
        request_hash=record.request_hash,
        task=record.task,
        model_id=record.model_id,
        input=record.input_payload,
        parameters=record.parameters,
        priority=JobPriority(record.priority),
        max_attempts=record.max_attempts,
        status=JobStatus(record.status),
        active_attempt_id=record.active_attempt_id,
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
        version=record.version,
    )


class SqlJobRepository:
    """Persist job aggregates inside a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> Job | None:
        record = self._session.get(JobRecord, job_id)
        return _to_domain(record) if record is not None else None

    def get_by_idempotency_key(self, key: str) -> Job | None:
        statement = select(JobRecord).where(JobRecord.idempotency_key == key)
        record = self._session.exec(statement).one_or_none()
        return _to_domain(record) if record is not None else None

    def list(
        self,
        *,
        status: JobStatus | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        statement = select(JobRecord)
        if status is not None:
            statement = statement.where(JobRecord.status == status.value)
        statement = (
            statement.order_by(col(JobRecord.created_at).desc(), col(JobRecord.id).desc())
            .offset(offset)
            .limit(limit)
        )
        return [_to_domain(record) for record in self._session.exec(statement).all()]

    def add(self, job: Job) -> None:
        self._session.add(
            JobRecord(
                id=job.id,
                idempotency_key=job.idempotency_key,
                request_hash=job.request_hash,
                task=job.task,
                model_id=job.model_id,
                input_payload=dict(job.input),
                parameters=dict(job.parameters),
                priority=job.priority.value,
                max_attempts=job.max_attempts,
                status=job.status.value,
                active_attempt_id=job.active_attempt_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
                version=job.version,
            )
        )

    def update(self, job: Job, *, expected_version: int) -> None:
        statement = (
            update(JobRecord)
            .where(
                col(JobRecord.id) == job.id,
                col(JobRecord.version) == expected_version,
            )
            .values(
                status=job.status.value,
                active_attempt_id=job.active_attempt_id,
                updated_at=job.updated_at,
                version=job.version,
            )
        )
        result = self._session.exec(statement)
        if result.rowcount != 1:
            raise ConcurrentUpdate(f"job {job.id} changed concurrently")

    def flush(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as error:
            raise DuplicateIdempotencyKey from error
