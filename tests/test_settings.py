"""Typed settings tests."""

from pydantic import ValidationError
from pytest import MonkeyPatch, raises

from conductor.config.settings import Environment, Settings


def test_settings_read_prefixed_environment_variables(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CONDUCTOR_ENVIRONMENT", "test")
    monkeypatch.setenv("CONDUCTOR_PORT", "9090")

    settings = Settings()

    assert settings.environment is Environment.TEST
    assert settings.port == 9090


def test_settings_reject_invalid_port() -> None:
    with raises(ValidationError):
        Settings(port=70_000)
