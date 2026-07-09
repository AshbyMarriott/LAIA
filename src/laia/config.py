"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    laia_api_key: str = "dev-api-key-change-me"
    database_url: str = "postgresql+asyncpg://laia:laia@localhost:5432/laia"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"
    laia_timezone: str = "America/Chicago"
    conversation_ttl_minutes: int = 15
    log_level: str = "INFO"
    default_event_duration_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
