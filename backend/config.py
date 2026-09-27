from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    storage_path: Path = Path.home() / ".pandaset" / "portfolios.sqlite3"
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=120)
    event_lab_enabled: bool = False
    event_lab_public_enabled: bool = False
    event_lab_probability_enabled: bool = False
    event_lab_allowed_user_ids: str = ""
    supabase_url: str = ""
    supabase_anon_key: SecretStr | None = None
    supabase_publishable_key: str = ""
    supabase_signing_mode: Literal["asymmetric", "legacy", "auto"] = "asymmetric"

    @field_validator("supabase_signing_mode", mode="before")
    @classmethod
    def normalize_supabase_signing_mode(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    market_data_provider: Literal["sample", "alpaca"] = "sample"
    alpaca_api_key: SecretStr | None = None
    alpaca_api_secret: SecretStr | None = None
    alpaca_history_feed: Literal["iex", "sip"] | None = None
    alpaca_assets_base_url: Literal[
        "https://paper-api.alpaca.markets", "https://api.alpaca.markets"
    ] = "https://paper-api.alpaca.markets"
    market_data_timeout_seconds: float = Field(default=15, gt=0, le=60)
    mongo_uri: SecretStr | None = None
    mongo_database: str = "portfoliolens"
    alpaca_display_rights_confirmed: bool = False
    alpaca_cache_rights_confirmed: bool = False
    fred_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-flash"
    approved_news_domains: str = ""
    event_max_active_jobs_per_user: int = Field(default=3, ge=1, le=20)
    event_max_messages_per_run: int = Field(default=100, ge=1, le=1000)

    @field_validator("storage_path")
    @classmethod
    def resolve_storage_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def event_lab_ready(self) -> bool:
        return bool(
            self.event_lab_enabled
            and self.supabase_url.strip()
            and self.supabase_publishable_key.strip()
            and self.mongo_uri and self.mongo_uri.get_secret_value().strip()
            and self.has_alpaca_history
            and self.alpaca_cache_rights_confirmed
            and self.has_gemini_key
            and self.has_tavily_key
            and self.has_deepseek_key
        )

    @property
    def event_lab_public_ready(self) -> bool:
        return bool(
            self.event_lab_ready
            and self.event_lab_public_enabled
            and self.alpaca_display_rights_confirmed
            and self.alpaca_cache_rights_confirmed
            and self.approved_news_domains.strip()
            and self.fred_api_key and self.fred_api_key.get_secret_value().strip()
        )

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.get_secret_value().strip())

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.tavily_api_key and self.tavily_api_key.get_secret_value().strip())

    @property
    def has_deepseek_key(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.get_secret_value().strip())

    @property
    def has_alpaca_history(self) -> bool:
        return bool(self.has_alpaca_keys and self.alpaca_history_feed)

    @property
    def has_alpaca_keys(self) -> bool:
        return bool(
            self.alpaca_api_key and self.alpaca_api_key.get_secret_value().strip()
            and self.alpaca_api_secret and self.alpaca_api_secret.get_secret_value().strip()
        )

    @property
    def supabase_auth_api_key(self) -> str:
        """Prefer an explicit legacy anon key; otherwise use the project publishable key."""
        anon_key = self.supabase_anon_key.get_secret_value() if self.supabase_anon_key else ""
        return anon_key.strip() or self.supabase_publishable_key.strip()

    @property
    def authentication_enabled(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_auth_api_key)

    @property
    def storage_path_source(self) -> str:
        return "override" if "storage_path" in self.model_fields_set else "default"


@lru_cache
def get_settings() -> Settings:
    return Settings()
