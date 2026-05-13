from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(...)

    # LLM providers
    anthropic_api_key: str = Field(...)
    voyage_api_key: str = Field(...)
    cohere_api_key: str = Field(...)

    # App
    log_level: str = "INFO"
    env: str = "development"

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
