"""Unit tests for model definition and residency lifecycle rules."""

from datetime import UTC, datetime

import pytest

from conductor.domain.errors import InvalidStateTransition
from conductor.domain.model import ModelDefinition, ModelResidency, ResidencyStatus, RuntimeKind

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _model(runtime_kind: RuntimeKind = RuntimeKind.FIXTURE) -> ModelDefinition:
    return ModelDefinition.create(
        model_id="demo-model",
        display_name="Demo model",
        runtime_kind=runtime_kind,
        artifact="demo-artifact",
        supported_tasks=frozenset({"text.generate"}),
        expected_memory_bytes=1_000_000,
        idle_timeout_seconds=300,
        now=NOW,
    )


def test_residency_load_execute_and_unload_path() -> None:
    loading = ModelResidency.start_loading(
        residency_id="residency-1",
        model=_model(),
        worker_id="worker-a",
        worker_instance_id="process-a",
        now=NOW,
    )
    assert loading.status is ResidencyStatus.LOADING

    ready = loading.mark_ready(measured_memory_bytes=900_000, now=NOW)
    executing = ready.begin_execution(now=NOW)
    idle = executing.finish_execution(now=NOW)
    unloading = idle.begin_unloading(now=NOW)

    assert ready.loaded_at == NOW
    assert executing.active_execution_count == 1
    assert idle.active_execution_count == 0
    assert unloading.status is ResidencyStatus.UNLOADING
    assert unloading.version == 4


def test_active_residency_cannot_unload() -> None:
    residency = (
        ModelResidency.start_loading(
            residency_id="residency-1",
            model=_model(),
            worker_id="worker-a",
            worker_instance_id="process-a",
            now=NOW,
        )
        .mark_ready(now=NOW)
        .begin_execution(now=NOW)
    )

    with pytest.raises(InvalidStateTransition):
        residency.begin_unloading(now=NOW)


def test_model_definition_is_immutable_configuration() -> None:
    model = _model(RuntimeKind.OLLAMA)

    assert model.runtime_kind is RuntimeKind.OLLAMA
    assert model.revision == 1
    with pytest.raises(AttributeError):
        model.artifact = "changed"  # type: ignore[misc]
