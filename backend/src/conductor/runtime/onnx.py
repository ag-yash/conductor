"""Local tensor inference through ONNX Runtime's Python session API."""

from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.runtime.base import RuntimeAdapterError, RuntimeResult


class OnnxSession(Protocol):
    """Only the small ONNX Runtime surface Conductor needs to exercise."""

    def run(
        self, output_names: Sequence[str] | None, input_feed: Mapping[str, Any]
    ) -> list[Any]: ...

    def get_outputs(self) -> Sequence[Any]: ...

    def get_providers(self) -> Sequence[str]: ...


SessionLoader = Callable[[str], OnnxSession]


class OnnxRuntimeAdapter:
    """Run trusted local `.onnx` artifacts for the `tensor.infer` job contract."""

    def __init__(self, session_loader: SessionLoader | None = None) -> None:
        self._session_loader = session_loader or self._load_session
        self._sessions: dict[str, OnnxSession] = {}

    def load(self, model: ModelDefinition) -> None:
        self._require_onnx(model)
        if model.id in self._sessions:
            return
        artifact = Path(model.artifact)
        if not artifact.is_file():
            raise RuntimeAdapterError(f"ONNX artifact does not exist: {artifact}")
        try:
            self._sessions[model.id] = self._session_loader(str(artifact))
        # Native inference bindings can raise package-specific exception classes
        # (not always a built-in RuntimeError) while reading a model artifact.
        # Translate ordinary adapter failures into Conductor's stable error type,
        # but do not catch BaseException: interrupts must still stop work.
        except Exception as error:
            raise RuntimeAdapterError(f"ONNX model could not be loaded: {error}") from error

    def invoke(
        self,
        model: ModelDefinition,
        *,
        task: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> RuntimeResult:
        self._require_onnx(model)
        if task != "tensor.infer" or task not in model.supported_tasks:
            raise RuntimeAdapterError("ONNX adapter currently supports tensor.infer only")
        session = self._sessions.get(model.id)
        if session is None:
            raise RuntimeAdapterError(f"model {model.id} is not loaded")
        raw_inputs = input.get("inputs")
        if not isinstance(raw_inputs, Mapping) or not raw_inputs:
            raise RuntimeAdapterError("tensor.infer requires a non-empty inputs object")
        output_names = parameters.get("output_names")
        if output_names is not None and (
            not isinstance(output_names, list)
            or not all(isinstance(name, str) for name in output_names)
        ):
            raise RuntimeAdapterError("output_names must be a list of output-name strings")
        try:
            feed = {name: np.asarray(value, dtype=np.float32) for name, value in raw_inputs.items()}
            outputs = session.run(cast(list[str] | None, output_names), feed)
        # Input-shape and type failures can come from NumPy or from ONNX
        # Runtime's native extension. Both become one safe worker-facing error.
        except Exception as error:
            raise RuntimeAdapterError(f"ONNX inference failed: {error}") from error
        names = (
            cast(list[str], output_names)
            if output_names is not None
            else [str(output.name) for output in session.get_outputs()]
        )
        if len(names) != len(outputs):
            raise RuntimeAdapterError("ONNX Runtime returned an unexpected number of outputs")
        providers = list(session.get_providers())
        return RuntimeResult(
            output={name: value.tolist() for name, value in zip(names, outputs, strict=True)},
            metrics={"output_count": len(outputs), "provider_count": len(providers)},
        )

    def unload(self, model: ModelDefinition) -> None:
        self._require_onnx(model)
        self._sessions.pop(model.id, None)

    @staticmethod
    def _load_session(artifact: str) -> OnnxSession:
        """Import the optional native binding only when an ONNX model is used."""

        try:
            runtime = import_module("onnxruntime")
            session_class = runtime.InferenceSession
            available = set(cast(list[str], runtime.get_available_providers()))
            # Apple Silicon wheels can expose CoreML. Keep CPU as the portable
            # fallback, and let ONNX Runtime use the first provider it supports.
            providers = [
                provider
                for provider in ("CoreMLExecutionProvider", "CPUExecutionProvider")
                if provider in available
            ]
            return cast(OnnxSession, session_class(artifact, providers=providers))
        except Exception as error:
            raise RuntimeAdapterError(f"ONNX Runtime is unavailable: {error}") from error

    @staticmethod
    def _require_onnx(model: ModelDefinition) -> None:
        if model.runtime_kind is not RuntimeKind.ONNX:
            raise RuntimeAdapterError(f"model {model.id} is not configured for ONNX Runtime")
