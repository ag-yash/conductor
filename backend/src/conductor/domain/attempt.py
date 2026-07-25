"""One immutable execution attempt in a job's history."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self

from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import utc_now


class AttemptStatus(StrEnum):
    """Execution-attempt lifecycle states."""

    ASSIGNED = "assigned"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOST = "lost"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS: dict[AttemptStatus, frozenset[AttemptStatus]] = {
    AttemptStatus.ASSIGNED: frozenset(
        {AttemptStatus.STARTING, AttemptStatus.CANCELLING, AttemptStatus.LOST}
    ),
    AttemptStatus.STARTING: frozenset(
        {
            AttemptStatus.RUNNING,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLING,
            AttemptStatus.LOST,
        }
    ),
    AttemptStatus.RUNNING: frozenset(
        {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLING,
            AttemptStatus.LOST,
        }
    ),
    AttemptStatus.CANCELLING: frozenset({AttemptStatus.CANCELLED, AttemptStatus.LOST}),
}


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    """An assignment to one specific worker-process instance."""

    id: str
    job_id: str
    ordinal: int
    worker_id: str
    worker_instance_id: str
    status: AttemptStatus
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        attempt_id: str,
        job_id: str,
        ordinal: int,
        worker_id: str,
        worker_instance_id: str,
        now: datetime | None = None,
    ) -> Self:
        timestamp = now or utc_now()
        return cls(
            id=attempt_id,
            job_id=job_id,
            ordinal=ordinal,
            worker_id=worker_id,
            worker_instance_id=worker_instance_id,
            status=AttemptStatus.ASSIGNED,
            created_at=timestamp,
            updated_at=timestamp,
            version=0,
        )

    def transition(self, status: AttemptStatus, *, now: datetime | None = None) -> Self:
        if status not in _ALLOWED_TRANSITIONS.get(self.status, frozenset()):
            raise InvalidStateTransition("attempt", self.status, status)
        return replace(
            self,
            status=status,
            updated_at=now or utc_now(),
            version=self.version + 1,
        )
