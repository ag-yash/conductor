"""Durable job application use cases."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import Job, JobPriority, JobStatus
from conductor.services.errors import (
    IdempotencyConflict,
    JobConflict,
    JobNotFound,
    PayloadTooLarge,
)
from conductor.services.ports import UnitOfWork
from conductor.storage.errors import ConcurrentUpdate, DuplicateIdempotencyKey


@dataclass(frozen=True, slots=True)
class SubmitJobCommand:
    """Validated intent passed from the API boundary."""

    idempotency_key: str
    task: str
    model_id: str
    input: Mapping[str, Any]
    parameters: Mapping[str, Any]
    priority: JobPriority
    max_attempts: int


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    """A job plus whether it came from an earlier identical submission."""

    job: Job
    replayed: bool


class JobService:
    """Coordinate job use cases against transaction and repository ports."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        max_payload_bytes: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._max_payload_bytes = max_payload_bytes

    def submit(self, command: SubmitJobCommand) -> SubmissionResult:
        canonical = self._canonical_request(command)
        if len(canonical) > self._max_payload_bytes:
            raise PayloadTooLarge(f"canonical job request exceeds {self._max_payload_bytes} bytes")
        request_hash = hashlib.sha256(canonical).hexdigest()

        with self._uow_factory() as uow:
            existing = uow.jobs.get_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return self._replay_or_conflict(existing, request_hash)

            job = Job.create(
                job_id=str(uuid4()),
                idempotency_key=command.idempotency_key,
                request_hash=request_hash,
                task=command.task,
                model_id=command.model_id,
                input=command.input,
                parameters=command.parameters,
                priority=command.priority,
                max_attempts=command.max_attempts,
            )
            uow.jobs.add(job)
            try:
                uow.jobs.flush()
                uow.commit()
            except DuplicateIdempotencyKey:
                uow.rollback()
                return self._resolve_concurrent_submission(command.idempotency_key, request_hash)
            return SubmissionResult(job=job, replayed=False)

    def get(self, job_id: str) -> Job:
        with self._uow_factory() as uow:
            job = uow.jobs.get(job_id)
            if job is None:
                raise JobNotFound(f"job {job_id} was not found")
            return job

    def list(self, *, status: JobStatus | None, limit: int, offset: int) -> list[Job]:
        with self._uow_factory() as uow:
            return uow.jobs.list(status=status, limit=limit, offset=offset)

    def cancel(self, job_id: str) -> Job:
        with self._uow_factory() as uow:
            job = uow.jobs.get(job_id)
            if job is None:
                raise JobNotFound(f"job {job_id} was not found")
            previous_version = job.version
            try:
                cancelled = job.cancel()
            except InvalidStateTransition as error:
                raise JobConflict(str(error)) from error

            if cancelled is job:
                return job
            try:
                uow.jobs.update(cancelled, expected_version=previous_version)
                uow.commit()
            except ConcurrentUpdate as error:
                raise JobConflict("job changed while cancellation was being processed") from error
            return cancelled

    def _resolve_concurrent_submission(self, key: str, request_hash: str) -> SubmissionResult:
        with self._uow_factory() as retry_uow:
            existing = retry_uow.jobs.get_by_idempotency_key(key)
            if existing is None:
                raise JobConflict("concurrent submission could not be resolved")
            return self._replay_or_conflict(existing, request_hash)

    @staticmethod
    def _replay_or_conflict(existing: Job, request_hash: str) -> SubmissionResult:
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "idempotency key is already associated with a different request"
            )
        return SubmissionResult(job=existing, replayed=True)

    @staticmethod
    def _canonical_request(command: SubmitJobCommand) -> bytes:
        value = {
            "input": command.input,
            "max_attempts": command.max_attempts,
            "model_id": command.model_id,
            "parameters": command.parameters,
            "priority": command.priority.value,
            "task": command.task,
        }
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
