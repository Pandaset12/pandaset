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
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175,"
        "http://localhost:5176,http://127.0.0.1:5176"
    )
    storage_path: Path = Path(__file__).parent / "data" / "portfoliolens.sqlite3"
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=120)
    event_lab_enabled: bool = False
    event_lab_public_enabled: bool = False
    event_lab_probability_enabled: bool = False
    event_lab_allowed_user_ids: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_signing_mode: Literal["asymmetric", "legacy", "auto"] = "asymmetric"
    mongo_uri: SecretStr | None = None
    mongo_database: str = "portfoliolens"
    twelve_data_api_key: SecretStr | None = None
    twelve_data_display_rights_confirmed: bool = False
    twelve_data_cache_rights_confirmed: bool = False
    fred_api_key: SecretStr | None = None
    approved_news_domains: str = ""
    event_max_active_jobs_per_user: int = Field(default=3, ge=1, le=20)
    event_max_messages_per_run: int = Field(default=100, ge=1, le=1000)

    @property
    def event_lab_ready(self) -> bool:
        return bool(
            self.event_lab_enabled
            and self.supabase_url
            and self.supabase_publishable_key
            and self.mongo_uri
            and self.twelve_data_api_key
            and self.has_gemini_key
        )

    @property
    def event_lab_public_ready(self) -> bool:
        return bool(
            self.event_lab_ready
            and self.event_lab_public_enabled
            and self.twelve_data_display_rights_confirmed
            and self.twelve_data_cache_rights_confirmed
            and self.approved_news_domains.strip()
            and self.fred_api_key
        )

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
