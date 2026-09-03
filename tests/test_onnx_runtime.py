"""Tests for the real ONNX adapter contract without shipping a model binary."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.runtime.base import RuntimeAdapterError
from conductor.runtime.onnx import OnnxRuntimeAdapter, OnnxSession


class FakeOnnxSession:
    """Small ONNX-session fake that records the tensor feed passed to it."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str] | None, dict[str, Any]]] = []

    def run(self, output_names: Sequence[str] | None, input_feed: Mapping[str, Any]) -> list[Any]:
        self.calls.append(
            (list(output_names) if output_names is not None else None, dict(input_feed))
        )
        return [np.asarray([[0.1, 0.9]], dtype=np.float32)]

    def get_outputs(self) -> Sequence[Any]:
        return [SimpleNamespace(name="probabilities")]

    def get_providers(self) -> Sequence[str]:
        return ["CPUExecutionProvider"]


def _model(artifact: Path) -> ModelDefinition:
    return ModelDefinition.create(
        model_id="tiny-classifier",
        display_name="Tiny local classifier",
        runtime_kind=RuntimeKind.ONNX,
        artifact=str(artifact),
        supported_tasks=frozenset({"tensor.infer"}),
        expected_memory_bytes=1,
        idle_timeout_seconds=300,
    )


def test_onnx_adapter_loads_converts_inputs_and_returns_json_safe_outputs(tmp_path: Path) -> None:
    artifact = tmp_path / "tiny.onnx"
    artifact.write_bytes(b"test model placeholder")
    session = FakeOnnxSession()
    adapter = OnnxRuntimeAdapter(session_loader=lambda _path: session)
    model = _model(artifact)

    adapter.load(model)
    result = adapter.invoke(
        model,
        task="tensor.infer",
        input={"inputs": {"features": [[1, 2, 3, 4]]}},
        parameters={},
    )

    assert np.allclose(result.output["probabilities"], [[0.1, 0.9]])
    assert result.metrics == {"output_count": 1, "provider_count": 1}
    assert session.calls[0][0] is None
    assert session.calls[0][1]["features"].dtype == np.float32


def test_onnx_adapter_unload_removes_its_process_local_session(tmp_path: Path) -> None:
    artifact = tmp_path / "tiny.onnx"
    artifact.write_bytes(b"test model placeholder")
    adapter = OnnxRuntimeAdapter(session_loader=lambda _path: FakeOnnxSession())
    model = _model(artifact)

    adapter.load(model)
    adapter.unload(model)

    with pytest.raises(RuntimeAdapterError, match="not loaded"):
        adapter.invoke(model, task="tensor.infer", input={"inputs": {"x": [1]}}, parameters={})


def test_onnx_adapter_translates_native_loader_errors(tmp_path: Path) -> None:
    artifact = tmp_path / "broken.onnx"
    artifact.write_bytes(b"not a model")
    model = _model(artifact)

    def raise_native_error(_path: str) -> OnnxSession:
        raise Exception("native session creation failed")

    adapter = OnnxRuntimeAdapter(session_loader=raise_native_error)

    with pytest.raises(RuntimeAdapterError, match="ONNX model could not be loaded"):
        adapter.load(model)


def test_onnx_adapter_translates_native_inference_errors(tmp_path: Path) -> None:
    artifact = tmp_path / "tiny.onnx"
    artifact.write_bytes(b"test model placeholder")
    model = _model(artifact)

    class FailingSession(FakeOnnxSession):
        def run(
            self, output_names: Sequence[str] | None, input_feed: Mapping[str, Any]
        ) -> list[Any]:
            raise Exception("native input shape error")

    adapter = OnnxRuntimeAdapter(session_loader=lambda _path: FailingSession())
    adapter.load(model)

    with pytest.raises(RuntimeAdapterError, match="ONNX inference failed"):
        adapter.invoke(model, task="tensor.infer", input={"inputs": {"x": [1]}}, parameters={})
