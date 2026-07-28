"""Runtime-independent interfaces used by local AI workers."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from conductor.domain.model import ModelDefinition


class RuntimeAdapterError(Exception):
    """Safe adapter failure that a worker can categorize and report."""


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """Runtime-neutral output and measurements from one inference call."""

    output: Mapping[str, Any]
    metrics: Mapping[str, int | float]


class RuntimeAdapter(Protocol):
    """Common model lifecycle and inference operations required from every runtime."""

    def load(self, model: ModelDefinition) -> None: ...

    def invoke(
        self,
        model: ModelDefinition,
        *,
        task: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> RuntimeResult: ...

    def unload(self, model: ModelDefinition) -> None: ...
