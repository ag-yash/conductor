"""Application settings loaded from the environment."""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from conductor import __version__


class Environment(StrEnum):
    """Supported runtime environments for the local-first V1."""

    LOCAL = "local"
    TEST = "test"


class Settings(BaseSettings):
    """Immutable, validated process configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CONDUCTOR_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    service_name: str = "conductor-control-plane"
    environment: Environment = Environment.LOCAL
    api_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    version: str = __version__


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings instance for the process."""

    return Settings()
