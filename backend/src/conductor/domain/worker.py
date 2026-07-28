"""Rules for a worker process that connects to the control plane."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self

from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import utc_now


class WorkerStatus(StrEnum):
    """The small V1 lifecycle for a registered worker."""

    READY = "ready"
    DRAINING = "draining"


@dataclass(frozen=True, slots=True)
class Worker:
    """One logical worker and the particular process currently running it."""

    id: str
    instance_id: str
    supported_tasks: frozenset[str]
    max_parallel_jobs: int
    status: WorkerStatus
    registered_at: datetime
    last_heartbeat_at: datetime
    version: int

    @classmethod
    def register(
        cls,
        *,
        worker_id: str,
        instance_id: str,
        supported_tasks: Iterable[str],
        max_parallel_jobs: int,
        now: datetime | None = None,
    ) -> Self:
        timestamp = now or utc_now()
        return cls(
            id=worker_id,
            instance_id=instance_id,
            supported_tasks=frozenset(supported_tasks),
            max_parallel_jobs=max_parallel_jobs,
            status=WorkerStatus.READY,
            registered_at=timestamp,
            last_heartbeat_at=timestamp,
            version=0,
        )

    def heartbeat(self, instance_id: str, *, now: datetime | None = None) -> Self:
        """Record liveness only for the process that currently owns this worker."""

        self._require_current_instance(instance_id)
        return replace(
            self,
            last_heartbeat_at=now or utc_now(),
            version=self.version + 1,
        )

    def drain(self, instance_id: str, *, now: datetime | None = None) -> Self:
        """Stop this worker from receiving new leases."""

        self._require_current_instance(instance_id)
        if self.status is WorkerStatus.DRAINING:
            return self
        if self.status is not WorkerStatus.READY:
            raise InvalidStateTransition("worker", self.status, WorkerStatus.DRAINING)
        return replace(
            self,
            status=WorkerStatus.DRAINING,
            last_heartbeat_at=now or utc_now(),
            version=self.version + 1,
        )

    def _require_current_instance(self, instance_id: str) -> None:
        if self.instance_id != instance_id:
            raise ValueError("worker_instance_id does not match the current worker process")
