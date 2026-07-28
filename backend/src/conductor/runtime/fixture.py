"""Small deterministic runtime for tests and failure demonstrations."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from conductor.domain.model import ModelDefinition
from conductor.runtime.base import RuntimeAdapterError, RuntimeResult


class FixtureRuntimeAdapter:
    """Execute predictable local work without downloading an AI model."""

    def __init__(self) -> None:
        self._loaded_models: set[str] = set()

    def load(self, model: ModelDefinition) -> None:
        self._loaded_models.add(model.id)

    def invoke(
        self,
        model: ModelDefinition,
        *,
        task: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> RuntimeResult:
        if model.id not in self._loaded_models:
            raise RuntimeAdapterError(f"model {model.id} is not loaded")
        if task not in model.supported_tasks:
            raise RuntimeAdapterError(f"model {model.id} does not support task {task}")

        # Hashing canonical input gives tests a stable “inference” output. It lets us
        # exercise scheduling and lifecycle behavior without pretending this is AI.
        canonical = json.dumps(
            {"input": input, "parameters": parameters, "task": task},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        return RuntimeResult(
            output={"fixture_digest": digest},
            metrics={"input_bytes": len(canonical)},
        )

    def unload(self, model: ModelDefinition) -> None:
        self._loaded_models.discard(model.id)
