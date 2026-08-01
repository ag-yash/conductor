"""HTTP contract for trusted model definitions."""

from datetime import datetime

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.services.models import ModelService, RegisterModelCommand

router = APIRouter(prefix="/models", tags=["models"])


class RegisterModelRequest(BaseModel):
    """Bounded trusted configuration; this does not upload a model binary."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    runtime_kind: RuntimeKind
    artifact: str = Field(min_length=1, max_length=300)
    supported_tasks: list[str] = Field(min_length=1, max_length=20)
    expected_memory_bytes: int = Field(ge=0, le=137_438_953_472)
    idle_timeout_seconds: int = Field(default=300, ge=0, le=86_400)


class ModelResponse(BaseModel):
    """Public model configuration returned to operators and workers."""

    id: str
    display_name: str
    runtime_kind: RuntimeKind
    artifact: str
    supported_tasks: list[str]
    expected_memory_bytes: int
    idle_timeout_seconds: int
    enabled: bool
    revision: int
    created_at: datetime

    @classmethod
    def from_domain(cls, model: ModelDefinition) -> "ModelResponse":
        return cls(
            id=model.id,
            display_name=model.display_name,
            runtime_kind=model.runtime_kind,
            artifact=model.artifact,
            supported_tasks=sorted(model.supported_tasks),
            expected_memory_bytes=model.expected_memory_bytes,
            idle_timeout_seconds=model.idle_timeout_seconds,
            enabled=model.enabled,
            revision=model.revision,
            created_at=model.created_at,
        )


def _service(request: Request) -> ModelService:
    service: ModelService = request.app.state.model_service
    return service


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def register_model(payload: RegisterModelRequest, request: Request) -> ModelResponse:
    # The API validates external JSON; ModelService owns identity and persistence rules.
    model = _service(request).register(
        RegisterModelCommand(
            model_id=payload.id,
            display_name=payload.display_name,
            runtime_kind=payload.runtime_kind,
            artifact=payload.artifact,
            supported_tasks=frozenset(payload.supported_tasks),
            expected_memory_bytes=payload.expected_memory_bytes,
            idle_timeout_seconds=payload.idle_timeout_seconds,
        )
    )
    return ModelResponse.from_domain(model)


@router.get("", response_model=list[ModelResponse])
def list_models(request: Request) -> list[ModelResponse]:
    return [ModelResponse.from_domain(model) for model in _service(request).list()]


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(model_id: str, request: Request) -> ModelResponse:
    return ModelResponse.from_domain(_service(request).get(model_id))
