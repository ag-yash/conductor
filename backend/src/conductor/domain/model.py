"""Model configuration and per-worker loaded-state rules."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from conductor.domain.errors import InvalidStateTransition
from conductor.domain.job import utc_now


class RuntimeKind(StrEnum):
    """Runtime adapters supported by the first M5 slice."""

    FIXTURE = "fixture"
    OLLAMA = "ollama"


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    """Trusted configuration describing what model Conductor may execute."""

    id: str
    display_name: str
    runtime_kind: RuntimeKind
    artifact: str
    supported_tasks: frozenset[str]
    expected_memory_bytes: int
    idle_timeout_seconds: int
    enabled: bool
    revision: int
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        model_id: str,
        display_name: str,
        runtime_kind: RuntimeKind,
        artifact: str,
        supported_tasks: frozenset[str],
        expected_memory_bytes: int,
        idle_timeout_seconds: int,
        now: datetime | None = None,
    ) -> Self:
        """Create the first immutable revision of trusted model configuration."""

        return cls(
            id=model_id,
            display_name=display_name,
            runtime_kind=runtime_kind,
            artifact=artifact,
            supported_tasks=supported_tasks,
            expected_memory_bytes=expected_memory_bytes,
            idle_timeout_seconds=idle_timeout_seconds,
            enabled=True,
            revision=1,
            created_at=now or utc_now(),
        )


class ResidencyStatus(StrEnum):
    """Lifecycle states for one model loaded in one worker process."""

    LOADING = "loading"
    READY = "ready"
    UNLOADING = "unloading"
    FAILED = "failed"


_RESIDENCY_TRANSITIONS: dict[ResidencyStatus, frozenset[ResidencyStatus]] = {
    ResidencyStatus.LOADING: frozenset({ResidencyStatus.READY, ResidencyStatus.FAILED}),
    ResidencyStatus.READY: frozenset({ResidencyStatus.UNLOADING, ResidencyStatus.FAILED}),
    ResidencyStatus.UNLOADING: frozenset({ResidencyStatus.FAILED}),
    ResidencyStatus.FAILED: frozenset({ResidencyStatus.LOADING}),
}


@dataclass(frozen=True, slots=True)
class ModelResidency:
    """Loaded-state history for one model in one exact worker process."""

    id: str
    model_id: str
    model_revision: int
    worker_id: str
    worker_instance_id: str
    status: ResidencyStatus
    active_execution_count: int
    measured_memory_bytes: int | None
    loaded_at: datetime | None
    last_used_at: datetime | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def start_loading(
        cls,
        *,
        residency_id: str,
        model: ModelDefinition,
        worker_id: str,
        worker_instance_id: str,
        now: datetime | None = None,
    ) -> Self:
        """Create residency state before the runtime begins loading."""

        timestamp = now or utc_now()
        return cls(
            id=residency_id,
            model_id=model.id,
            model_revision=model.revision,
            worker_id=worker_id,
            worker_instance_id=worker_instance_id,
            status=ResidencyStatus.LOADING,
            active_execution_count=0,
            measured_memory_bytes=None,
            loaded_at=None,
            last_used_at=None,
            failure_message=None,
            created_at=timestamp,
            updated_at=timestamp,
            version=0,
        )

    def mark_ready(
        self,
        *,
        measured_memory_bytes: int | None = None,
        now: datetime | None = None,
    ) -> Self:
        """Confirm that the adapter loaded the model and it may accept work."""

        timestamp = now or utc_now()
        return self._transition(
            ResidencyStatus.READY,
            now=timestamp,
            loaded_at=timestamp,
            measured_memory_bytes=measured_memory_bytes,
            failure_message=None,
        )

    def begin_execution(self, *, now: datetime | None = None) -> Self:
        """Reserve this ready model for one additional execution."""

        if self.status is not ResidencyStatus.READY:
            raise InvalidStateTransition("model residency", self.status, "executing")
        timestamp = now or utc_now()
        return replace(
            self,
            active_execution_count=self.active_execution_count + 1,
            last_used_at=timestamp,
            updated_at=timestamp,
            version=self.version + 1,
        )

    def finish_execution(self, *, now: datetime | None = None) -> Self:
        """Release one execution reservation without allowing a negative count."""

        if self.status is not ResidencyStatus.READY or self.active_execution_count == 0:
            raise InvalidStateTransition("model residency", self.status, "finish execution")
        timestamp = now or utc_now()
        return replace(
            self,
            active_execution_count=self.active_execution_count - 1,
            last_used_at=timestamp,
            updated_at=timestamp,
            version=self.version + 1,
        )

    def begin_unloading(self, *, now: datetime | None = None) -> Self:
        """Start eviction only after every active execution has released the model."""

        if self.active_execution_count != 0:
            raise InvalidStateTransition("model residency", self.status, ResidencyStatus.UNLOADING)
        return self._transition(ResidencyStatus.UNLOADING, now=now or utc_now())

    def mark_failed(self, message: str, *, now: datetime | None = None) -> Self:
        """Record a safe runtime failure for later diagnosis or bounded recovery."""

        return self._transition(
            ResidencyStatus.FAILED,
            now=now or utc_now(),
            failure_message=message,
        )

    def _transition(
        self,
        status: ResidencyStatus,
        *,
        now: datetime,
        **changes: Any,
    ) -> Self:
        if status not in _RESIDENCY_TRANSITIONS.get(self.status, frozenset()):
            raise InvalidStateTransition("model residency", self.status, status)
        return replace(
            self,
            status=status,
            updated_at=now,
            version=self.version + 1,
            **changes,
        )
