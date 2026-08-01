"""Contract tests for deterministic and Ollama-compatible runtime adapters."""

from collections.abc import Mapping
from typing import Any

import pytest

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.runtime.base import RuntimeAdapterError
from conductor.runtime.fixture import FixtureRuntimeAdapter
from conductor.runtime.ollama import OllamaRuntimeAdapter


def _model(runtime_kind: RuntimeKind) -> ModelDefinition:
    return ModelDefinition.create(
        model_id="qwen-small",
        display_name="Qwen Small",
        runtime_kind=runtime_kind,
        artifact="qwen2.5:1.5b",
        supported_tasks=frozenset({"text.generate"}),
        expected_memory_bytes=2_000_000_000,
        idle_timeout_seconds=300,
    )


class FakeTransport:
    """Record Ollama requests and return a response without network access."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def post(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((path, payload))
        return {
            "response": "A deterministic generated answer.",
            "total_duration": 10,
            "eval_count": 4,
        }


def test_fixture_runtime_requires_load_and_is_deterministic() -> None:
    model = _model(RuntimeKind.FIXTURE)
    adapter = FixtureRuntimeAdapter()

    with pytest.raises(RuntimeAdapterError):
        adapter.invoke(
            model,
            task="text.generate",
            input={"prompt": "hello"},
            parameters={"temperature": 0.2},
        )

    adapter.load(model)
    first = adapter.invoke(
        model,
        task="text.generate",
        input={"prompt": "hello"},
        parameters={"temperature": 0.2},
    )
    second = adapter.invoke(
        model,
        task="text.generate",
        input={"prompt": "hello"},
        parameters={"temperature": 0.2},
    )

    assert first == second
    adapter.unload(model)


def test_ollama_adapter_translates_load_invoke_and_unload() -> None:
    transport = FakeTransport()
    adapter = OllamaRuntimeAdapter(transport)
    model = _model(RuntimeKind.OLLAMA)

    adapter.load(model)
    result = adapter.invoke(
        model,
        task="text.generate",
        input={"prompt": "Explain model residency."},
        parameters={"temperature": 0.1},
    )
    adapter.unload(model)

    assert result.output == {"text": "A deterministic generated answer."}
    assert result.metrics == {"total_duration": 10, "eval_count": 4}
    assert transport.calls[0][1]["keep_alive"] == -1
    assert transport.calls[1][1]["stream"] is False
    assert transport.calls[2][1]["keep_alive"] == 0


def test_ollama_adapter_rejects_invalid_prompt() -> None:
    adapter = OllamaRuntimeAdapter(FakeTransport())

    with pytest.raises(RuntimeAdapterError):
        adapter.invoke(
            _model(RuntimeKind.OLLAMA),
            task="text.generate",
            input={"prompt": ""},
            parameters={},
        )
