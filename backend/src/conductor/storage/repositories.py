"""SQLModel repository implementations and domain-record translation."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from conductor.domain.attempt import AttemptStatus, ExecutionAttempt
from conductor.domain.job import Job, JobPriority, JobStatus
from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.domain.worker import Worker, WorkerStatus
from conductor.models.records import (
    AttemptRecord,
    JobRecord,
    ModelDefinitionRecord,
    SchedulingDecisionRecord,
    WorkerRecord,
)
from conductor.scheduler.policy import (
    CandidateExplanation,
    PlacementDecision,
    RecordedSchedulingDecision,
)
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
        result=record.result_payload,
        error_message=record.error_message,
        priority=JobPriority(record.priority),
        max_attempts=record.max_attempts,
        status=JobStatus(record.status),
        active_attempt_id=record.active_attempt_id,
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
        version=record.version,
    )


def _attempt_to_domain(record: AttemptRecord) -> ExecutionAttempt:
    return ExecutionAttempt(
        id=record.id,
        job_id=record.job_id,
        ordinal=record.ordinal,
        worker_id=record.worker_id,
        worker_instance_id=record.worker_instance_id,
        status=AttemptStatus(record.status),
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
        version=record.version,
    )


def _worker_to_domain(record: WorkerRecord) -> Worker:
    return Worker(
        id=record.id,
        instance_id=record.instance_id,
        supported_tasks=frozenset(record.supported_tasks),
        max_parallel_jobs=record.max_parallel_jobs,
        status=WorkerStatus(record.status),
        registered_at=_aware(record.registered_at),
        last_heartbeat_at=_aware(record.last_heartbeat_at),
        version=record.version,
    )


def _model_to_domain(record: ModelDefinitionRecord) -> ModelDefinition:
    """Translate the database representation into runtime-independent configuration."""

    return ModelDefinition(
        id=record.id,
        display_name=record.display_name,
        runtime_kind=RuntimeKind(record.runtime_kind),
        artifact=record.artifact,
        supported_tasks=frozenset(record.supported_tasks),
        expected_memory_bytes=record.expected_memory_bytes,
        idle_timeout_seconds=record.idle_timeout_seconds,
        enabled=record.enabled,
        revision=record.revision,
        created_at=_aware(record.created_at),
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
                result_payload=dict(job.result) if job.result is not None else None,
                error_message=job.error_message,
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
                result_payload=dict(job.result) if job.result is not None else None,
                error_message=job.error_message,
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


class SqlAttemptRepository:
    """Persist immutable attempt history and guarded state changes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, attempt: ExecutionAttempt) -> None:
        self._session.add(
            AttemptRecord(
                id=attempt.id,
                job_id=attempt.job_id,
                ordinal=attempt.ordinal,
                worker_id=attempt.worker_id,
                worker_instance_id=attempt.worker_instance_id,
                status=attempt.status.value,
                created_at=attempt.created_at,
                updated_at=attempt.updated_at,
                version=attempt.version,
            )
        )

    def get(self, attempt_id: str) -> ExecutionAttempt | None:
        record = self._session.get(AttemptRecord, attempt_id)
        return _attempt_to_domain(record) if record is not None else None

    def update(self, attempt: ExecutionAttempt, *, expected_version: int) -> None:
        statement = (
            update(AttemptRecord)
            .where(
                col(AttemptRecord.id) == attempt.id, col(AttemptRecord.version) == expected_version
            )
            .values(
                status=attempt.status.value,
                updated_at=attempt.updated_at,
                version=attempt.version,
            )
        )
        if self._session.exec(statement).rowcount != 1:
            raise ConcurrentUpdate(f"attempt {attempt.id} changed concurrently")

    def count_active_for_worker(self, worker_id: str, instance_id: str) -> int:
        # We count only leases that still consume a slot. Finished attempts remain in
        # the database as history but must not make a worker look permanently busy.
        active = (
            AttemptStatus.ASSIGNED.value,
            AttemptStatus.STARTING.value,
            AttemptStatus.RUNNING.value,
        )
        statement = select(AttemptRecord).where(
            AttemptRecord.worker_id == worker_id,
            AttemptRecord.worker_instance_id == instance_id,
            col(AttemptRecord.status).in_(active),
        )
        return len(self._session.exec(statement).all())


class SqlWorkerRepository:
    """Persist the one current process instance for every worker identity."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, worker_id: str) -> Worker | None:
        record = self._session.get(WorkerRecord, worker_id)
        return _worker_to_domain(record) if record is not None else None

    def add(self, worker: Worker) -> None:
        self._session.add(
            WorkerRecord(
                id=worker.id,
                instance_id=worker.instance_id,
                supported_tasks=sorted(worker.supported_tasks),
                max_parallel_jobs=worker.max_parallel_jobs,
                status=worker.status.value,
                registered_at=worker.registered_at,
                last_heartbeat_at=worker.last_heartbeat_at,
                version=worker.version,
            )
        )

    def list(self) -> list[Worker]:
        return [
            _worker_to_domain(record) for record in self._session.exec(select(WorkerRecord)).all()
        ]

    def update(self, worker: Worker, *, expected_version: int) -> None:
        statement = (
            update(WorkerRecord)
            .where(col(WorkerRecord.id) == worker.id, col(WorkerRecord.version) == expected_version)
            .values(
                instance_id=worker.instance_id,
                supported_tasks=sorted(worker.supported_tasks),
                max_parallel_jobs=worker.max_parallel_jobs,
                status=worker.status.value,
                last_heartbeat_at=worker.last_heartbeat_at,
                version=worker.version,
            )
        )
        if self._session.exec(statement).rowcount != 1:
            raise ConcurrentUpdate(f"worker {worker.id} changed concurrently")


class SqlSchedulingDecisionRepository:
    """Persist append-only scheduling explanations for operators and tests."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        decision_id: str,
        job_id: str,
        decision: PlacementDecision,
        outcome: str,
    ) -> None:
        # Store a JSON snapshot, not live Worker objects. Later heartbeats must not
        # rewrite the explanation for a decision that already happened.
        self._session.add(
            SchedulingDecisionRecord(
                id=decision_id,
                job_id=job_id,
                selected_worker_id=decision.selected_worker_id,
                outcome=outcome,
                reason=decision.reason,
                candidates=[
                    {
                        "worker_id": candidate.worker_id,
                        "eligible": candidate.eligible,
                        "reason": candidate.reason,
                        "active_slots": candidate.active_slots,
                        "max_parallel_jobs": candidate.max_parallel_jobs,
                    }
                    for candidate in decision.candidates
                ],
                created_at=datetime.now(UTC),
            )
        )

    def list_for_job(self, job_id: str) -> list[RecordedSchedulingDecision]:
        statement = (
            select(SchedulingDecisionRecord)
            .where(SchedulingDecisionRecord.job_id == job_id)
            .order_by(col(SchedulingDecisionRecord.created_at).asc())
        )
        return [
            RecordedSchedulingDecision(
                id=record.id,
                job_id=record.job_id,
                selected_worker_id=record.selected_worker_id,
                outcome=record.outcome,
                reason=record.reason,
                candidates=tuple(
                    CandidateExplanation(
                        worker_id=candidate["worker_id"],
                        eligible=candidate["eligible"],
                        reason=candidate["reason"],
                        active_slots=candidate["active_slots"],
                        max_parallel_jobs=candidate["max_parallel_jobs"],
                    )
                    for candidate in record.candidates
                ),
                created_at=_aware(record.created_at),
            )
            for record in self._session.exec(statement).all()
        ]


class SqlModelDefinitionRepository:
    """Persist trusted model definitions independently from loaded state."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, model: ModelDefinition) -> None:
        self._session.add(
            ModelDefinitionRecord(
                id=model.id,
                display_name=model.display_name,
                runtime_kind=model.runtime_kind.value,
                artifact=model.artifact,
                supported_tasks=sorted(model.supported_tasks),
                expected_memory_bytes=model.expected_memory_bytes,
                idle_timeout_seconds=model.idle_timeout_seconds,
                enabled=model.enabled,
                revision=model.revision,
                created_at=model.created_at,
            )
        )

    def get(self, model_id: str) -> ModelDefinition | None:
        record = self._session.get(ModelDefinitionRecord, model_id)
        return _model_to_domain(record) if record is not None else None

    def list(self) -> list[ModelDefinition]:
        statement = select(ModelDefinitionRecord).order_by(col(ModelDefinitionRecord.id).asc())
        return [_model_to_domain(record) for record in self._session.exec(statement).all()]
