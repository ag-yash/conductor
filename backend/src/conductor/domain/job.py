"""Durable user intent for one AI inference operation."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Self

from conductor.domain.errors import InvalidStateTransition


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class JobStatus(StrEnum):
    """Persisted job lifecycle states."""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(StrEnum):
    """V1 queue priority classes."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


TERMINAL_JOB_STATUSES = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})


@dataclass(frozen=True, slots=True)
class Job:
    """Immutable job aggregate changed only through guarded operations."""

    id: str
    idempotency_key: str
    request_hash: str
    task: str
    model_id: str
    input: Mapping[str, Any]
    parameters: Mapping[str, Any]
    priority: JobPriority
    max_attempts: int
    status: JobStatus
    active_attempt_id: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        idempotency_key: str,
        request_hash: str,
        task: str,
        model_id: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
        priority: JobPriority,
        max_attempts: int,
        now: datetime | None = None,
    ) -> Self:
        timestamp = now or utc_now()
        return cls(
            id=job_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            task=task,
            model_id=model_id,
            input=MappingProxyType(dict(input)),
            parameters=MappingProxyType(dict(parameters)),
            priority=priority,
            max_attempts=max_attempts,
            status=JobStatus.QUEUED,
            active_attempt_id=None,
            created_at=timestamp,
            updated_at=timestamp,
            version=0,
        )

    def assign(self, attempt_id: str, *, now: datetime | None = None) -> Self:
        if self.status is not JobStatus.QUEUED:
            raise InvalidStateTransition("job", self.status, JobStatus.ASSIGNED)
        return self._transition(
            JobStatus.ASSIGNED,
            now=now,
            active_attempt_id=attempt_id,
        )

    def start(self, *, now: datetime | None = None) -> Self:
        if self.status is not JobStatus.ASSIGNED:
            raise InvalidStateTransition("job", self.status, JobStatus.RUNNING)
        return self._transition(JobStatus.RUNNING, now=now)

    def retry(self, *, now: datetime | None = None) -> Self:
        if self.status not in {JobStatus.ASSIGNED, JobStatus.RUNNING}:
            raise InvalidStateTransition("job", self.status, JobStatus.QUEUED)
        return self._transition(JobStatus.QUEUED, now=now, active_attempt_id=None)

    def succeed(self, *, now: datetime | None = None) -> Self:
        """Mark the current running job as successfully completed."""

        if self.status is not JobStatus.RUNNING:
            raise InvalidStateTransition("job", self.status, JobStatus.SUCCEEDED)
        return self._transition(JobStatus.SUCCEEDED, now=now, active_attempt_id=None)

    def cancel(self, *, now: datetime | None = None) -> Self:
        if self.status is JobStatus.CANCELLED:
            return self
        if self.status is not JobStatus.QUEUED:
            raise InvalidStateTransition("job", self.status, JobStatus.CANCELLED)
        return self._transition(JobStatus.CANCELLED, now=now, active_attempt_id=None)

    def _transition(
        self,
        status: JobStatus,
        *,
        now: datetime | None,
        active_attempt_id: str | object | None = ...,
    ) -> Self:
        changes: dict[str, Any] = {
            "status": status,
            "updated_at": now or utc_now(),
            "version": self.version + 1,
        }
        if active_attempt_id is not ...:
            changes["active_attempt_id"] = active_attempt_id
        return replace(self, **changes)
