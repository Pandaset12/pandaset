from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    analyst_mode: Literal["demo", "gemini"] = "demo"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    storage_path: Path = Path(__file__).parent / "data" / "portfoliolens.sqlite3"
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=120)

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
