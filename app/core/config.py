from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    KB_URL: AnyHttpUrl
    KB_TIMEOUT_SECONDS: int = 15
    KB_CACHE_TTL_SECONDS: int = 60

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 400
    LLM_TIMEOUT_SECONDS: int = 30

    CONTEXT_TOP_K: int = Field(default=3, ge=1, le=10)
    CONTEXT_MIN_SCORE: int = Field(default=2, ge=1)

    MEMORY_ENABLED: bool = True
    MEMORY_TTL_SECONDS: int = 900
    MEMORY_MAX_TURNS: int = Field(default=6, ge=2, le=20)
    MEMORY_STORE: str = ""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
