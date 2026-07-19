"""Shared test configuration with an isolated SQLite database per test."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conductor.config.settings import Environment, Settings
from conductor.main import create_app


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url=f"sqlite:///{tmp_path / 'conductor.db'}",
        version="test-version",
    )


@pytest.fixture
def client(app_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(app_settings)) as test_client:
        yield test_client
