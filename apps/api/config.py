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
    openai_api_key: str = Field(...)
    voyage_api_key: str = Field(...)
    cohere_api_key: str = Field(...)

    # App
    log_level: str = "INFO"
    env: str = "development"

    # Security / cost controls
    # Comma-separated list of accepted API keys. If empty/unset, API-key auth
    # is DISABLED (no-op pass-through) so local dev and tests work with zero
    # config. Set in production to require an X-API-Key header (or
    # Authorization: Bearer <key>) on the expensive analyze/retrieve endpoints.
    api_key: str = ""

    # Process-wide cap on concurrent expensive analyses (each fans out to 5
    # agents -> embeddings + reranks + LLM calls). Excess concurrent requests
    # receive HTTP 429 rather than queueing unboundedly. Default kept small.
    max_concurrent_analyses: int = 4

    # CORS allowed origins (comma-separated). Defaults to local Next.js dev.
    # Never set to "*".
    cors_allow_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    @property
    def api_keys(self) -> list[str]:
        """Configured API keys, parsed from the comma-separated `api_key`."""
        return [k.strip() for k in self.api_key.split(",") if k.strip()]

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS allow-origins list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
