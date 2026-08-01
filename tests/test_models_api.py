"""Integration tests for durable trusted model definitions."""

from fastapi.testclient import TestClient

from conductor.config.settings import Settings
from conductor.main import create_app

MODEL_REQUEST = {
    "id": "qwen-small",
    "display_name": "Qwen Small",
    "runtime_kind": "ollama",
    "artifact": "qwen2.5:1.5b",
    "supported_tasks": ["text.generate"],
    "expected_memory_bytes": 2_000_000_000,
    "idle_timeout_seconds": 300,
}


def test_register_get_and_list_model_definition(client: TestClient) -> None:
    registered = client.post("/api/v1/models", json=MODEL_REQUEST)
    assert registered.status_code == 201
    assert registered.json()["revision"] == 1
    assert registered.json()["runtime_kind"] == "ollama"

    fetched = client.get("/api/v1/models/qwen-small")
    assert fetched.status_code == 200
    assert fetched.json()["artifact"] == "qwen2.5:1.5b"

    listed = client.get("/api/v1/models")
    assert listed.status_code == 200
    assert [model["id"] for model in listed.json()] == ["qwen-small"]


def test_duplicate_model_identity_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/models", json=MODEL_REQUEST).status_code == 201

    duplicate = client.post("/api/v1/models", json=MODEL_REQUEST)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "model_conflict"


def test_missing_model_returns_stable_error(client: TestClient) -> None:
    response = client.get("/api/v1/models/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_model_definition_survives_restart(app_settings: Settings) -> None:
    with TestClient(create_app(app_settings)) as first_client:
        registered = first_client.post("/api/v1/models", json=MODEL_REQUEST)
        assert registered.status_code == 201

    with TestClient(create_app(app_settings)) as restarted_client:
        fetched = restarted_client.get("/api/v1/models/qwen-small")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == "qwen-small"
