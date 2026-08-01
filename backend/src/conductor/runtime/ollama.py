"""Ollama-compatible text generation behind Conductor's runtime contract."""

import json
from collections.abc import Mapping
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from conductor.domain.model import ModelDefinition, RuntimeKind
from conductor.runtime.base import RuntimeAdapterError, RuntimeResult


class JsonTransport(Protocol):
    """Minimal HTTP dependency that tests can replace without a live Ollama server."""

    def post(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class UrllibJsonTransport:
    """Standard-library JSON transport for a local Ollama-compatible endpoint."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self._base_url = base_url.rstrip("/")

    def post(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                return cast(dict[str, Any], json.loads(response.read()))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeAdapterError(f"Ollama request failed: {error}") from error


class OllamaRuntimeAdapter:
    """Translate Conductor text jobs into Ollama's generate API."""

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self._transport = transport or UrllibJsonTransport()

    def load(self, model: ModelDefinition) -> None:
        self._require_ollama(model)
        # Ollama documents an empty prompt plus negative keep_alive as a preload.
        self._transport.post(
            "/api/generate",
            {"model": model.artifact, "prompt": "", "stream": False, "keep_alive": -1},
        )

    def invoke(
        self,
        model: ModelDefinition,
        *,
        task: str,
        input: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> RuntimeResult:
        self._require_ollama(model)
        if task != "text.generate" or task not in model.supported_tasks:
            raise RuntimeAdapterError("Ollama adapter currently supports text.generate only")
        prompt = input.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise RuntimeAdapterError("text.generate requires a non-empty string prompt")

        response = self._transport.post(
            "/api/generate",
            {
                "model": model.artifact,
                "prompt": prompt,
                "options": dict(parameters),
                "stream": False,
                "keep_alive": -1,
            },
        )
        generated = response.get("response")
        if not isinstance(generated, str):
            raise RuntimeAdapterError("Ollama response did not contain generated text")
        metric_names = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        )
        metrics = {
            name: value
            for name in metric_names
            if isinstance((value := response.get(name)), (int, float))
        }
        return RuntimeResult(output={"text": generated}, metrics=metrics)

    def unload(self, model: ModelDefinition) -> None:
        self._require_ollama(model)
        # keep_alive zero tells Ollama to release the model immediately.
        self._transport.post(
            "/api/generate",
            {"model": model.artifact, "prompt": "", "stream": False, "keep_alive": 0},
        )

    @staticmethod
    def _require_ollama(model: ModelDefinition) -> None:
        if model.runtime_kind is not RuntimeKind.OLLAMA:
            raise RuntimeAdapterError(f"model {model.id} is not configured for Ollama")
