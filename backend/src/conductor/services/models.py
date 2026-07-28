"""Application use cases for trusted model configuration."""

from collections.abc import Callable
from dataclasses import dataclass

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.services.errors import ModelConflict, ModelNotFound
from conductor.services.ports import UnitOfWork


@dataclass(frozen=True, slots=True)
class RegisterModelCommand:
    """Validated model configuration passed from the API boundary."""

    model_id: str
    display_name: str
    runtime_kind: RuntimeKind
    artifact: str
    supported_tasks: frozenset[str]
    expected_memory_bytes: int
    idle_timeout_seconds: int


class ModelService:
    """Register and inspect the trusted models Conductor may execute."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def register(self, command: RegisterModelCommand) -> ModelDefinition:
        with self._uow_factory() as uow:
            if uow.model_definitions.get(command.model_id) is not None:
                raise ModelConflict(f"model {command.model_id} is already registered")
            model = ModelDefinition.create(
                model_id=command.model_id,
                display_name=command.display_name,
                runtime_kind=command.runtime_kind,
                artifact=command.artifact,
                supported_tasks=command.supported_tasks,
                expected_memory_bytes=command.expected_memory_bytes,
                idle_timeout_seconds=command.idle_timeout_seconds,
            )
            uow.model_definitions.add(model)
            uow.commit()
            return model

    def get(self, model_id: str) -> ModelDefinition:
        with self._uow_factory() as uow:
            model = uow.model_definitions.get(model_id)
            if model is None:
                raise ModelNotFound(f"model {model_id} was not found")
            return model

    def list(self) -> list[ModelDefinition]:
        with self._uow_factory() as uow:
            return uow.model_definitions.list()
