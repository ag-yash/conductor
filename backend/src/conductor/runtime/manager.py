"""Process-local model loading and invocation coordination.

The control plane currently hosts the worker-facing execution path in one Python
process. This manager keeps the loaded-model cache separate from the database:
the database describes what a model *can* be, while this cache describes what is
currently present in this process's memory.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

from conductor.domain.model import ModelDefinition, ModelResidency, ResidencyStatus, RuntimeKind
from conductor.runtime.base import RuntimeAdapter, RuntimeAdapterError, RuntimeResult
from conductor.runtime.fixture import FixtureRuntimeAdapter
from conductor.runtime.ollama import OllamaRuntimeAdapter


class RuntimeManager:
    """Load, reuse, and invoke model adapters for one worker process."""

    def __init__(self, adapters: Mapping[RuntimeKind, RuntimeAdapter]) -> None:
        self._adapters = dict(adapters)
        self._residencies: dict[tuple[str, str, str], ModelResidency] = {}
        self._models: dict[tuple[str, str, str], ModelDefinition] = {}
        # A request may arrive from multiple web-server threads. The lock makes
        # “check whether loaded, then load once” one atomic operation locally.
        self._lock = RLock()

    @classmethod
    def default(cls) -> "RuntimeManager":
        """Build the V1 manager with the deterministic runtime available by default."""

        return cls(
            {
                RuntimeKind.FIXTURE: FixtureRuntimeAdapter(),
                # The adapter uses Ollama only when an Ollama model is registered
                # and executed. Keeping it in the registry makes the integration
                # available without requiring Ollama for fixture-only development.
                RuntimeKind.OLLAMA: OllamaRuntimeAdapter(),
            }
        )

    def execute(
        self,
        *,
        model: ModelDefinition,
        worker_id: str,
        worker_instance_id: str,
        task: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> RuntimeResult:
        """Run one request, loading the model only when this worker needs it."""

        if not model.enabled:
            raise RuntimeAdapterError(f"model {model.id} is disabled")
        adapter = self._adapters.get(model.runtime_kind)
        if adapter is None:
            raise RuntimeAdapterError(f"runtime {model.runtime_kind} is not configured")

        key = (worker_id, worker_instance_id, model.id)
        with self._lock:
            self._models[key] = model
            residency = self._residencies.get(key)
            if residency is None or residency.status is ResidencyStatus.FAILED:
                residency = ModelResidency.start_loading(
                    residency_id=f"{worker_id}:{worker_instance_id}:{model.id}",
                    model=model,
                    worker_id=worker_id,
                    worker_instance_id=worker_instance_id,
                )
                self._residencies[key] = residency
                try:
                    adapter.load(model)
                    residency = residency.mark_ready()
                except RuntimeAdapterError as error:
                    self._residencies[key] = residency.mark_failed(str(error))
                    raise

            residency = residency.begin_execution()
            self._residencies[key] = residency
            try:
                result = adapter.invoke(
                    model,
                    task=task,
                    input=input,
                    parameters=parameters,
                )
            except RuntimeAdapterError as error:
                self._residencies[key] = residency.finish_execution().mark_failed(str(error))
                raise
            self._residencies[key] = residency.finish_execution()
            return result

    def evict_idle(
        self,
        *,
        worker_id: str,
        worker_instance_id: str,
        now: datetime | None = None,
    ) -> tuple[ModelResidency, ...]:
        """Unload models that have been idle for their configured timeout."""

        timestamp = now or datetime.now(UTC)
        evicted: list[ModelResidency] = []
        with self._lock:
            for key, residency in list(self._residencies.items()):
                if key[:2] != (worker_id, worker_instance_id):
                    continue
                model = self._models[key]
                if not self._is_idle(residency, model, timestamp):
                    continue
                adapter = self._adapters[model.runtime_kind]
                unloading = residency.begin_unloading(now=timestamp)
                try:
                    adapter.unload(model)
                except RuntimeAdapterError as error:
                    self._residencies[key] = unloading.mark_failed(str(error), now=timestamp)
                    raise
                evicted.append(unloading)
                del self._residencies[key]
                del self._models[key]
        return tuple(evicted)

    @staticmethod
    def _is_idle(
        residency: ModelResidency,
        model: ModelDefinition,
        now: datetime,
    ) -> bool:
        if residency.status is not ResidencyStatus.READY:
            return False
        if residency.active_execution_count != 0 or residency.last_used_at is None:
            return False
        deadline = residency.last_used_at + timedelta(seconds=model.idle_timeout_seconds)
        return now >= deadline

    def residency(
        self, *, worker_id: str, worker_instance_id: str, model_id: str
    ) -> ModelResidency | None:
        """Return a read-only snapshot for tests and future operator endpoints."""

        with self._lock:
            return self._residencies.get((worker_id, worker_instance_id, model_id))
