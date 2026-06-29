"""Typed application settings.

All configuration — including every secret — is read from environment variables
(or a local ``.env`` file in development). Secrets are stored as ``SecretStr`` so they
are never accidentally printed or logged. Nothing here hardcodes a credential.

The settings object intentionally declares fields for the *entire* build, not just
Phase 0, so later phases can rely on a stable config contract. Most fields are optional
and default to ``None`` until the human operator supplies them.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# ID allowlists are supplied as comma-separated strings. NoDecode stops
# pydantic-settings from trying to JSON-decode them from env/.env so our
# ``_parse_id_list`` validator can split the raw string itself.
TelegramIdList = Annotated[tuple[int, ...], NoDecode]


class Environment(StrEnum):
    """Runtime environment selector."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class RunMode(StrEnum):
    """How the Telegram bot receives updates."""

    POLLING = "polling"
    WEBHOOK = "webhook"


class Settings(BaseSettings):
    """Application settings sourced from the environment.

    Field names map to ``UPPER_SNAKE_CASE`` env vars (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core runtime ---------------------------------------------------------
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = True
    health_host: str = "0.0.0.0"
    health_port: int = 8080

    # --- Telegram -------------------------------------------------------------
    telegram_bot_token: SecretStr | None = None
    # Two-tier role model: owners (operator/superadmin) are implicitly admins too.
    owner_telegram_ids: TelegramIdList = Field(default_factory=tuple)
    admin_telegram_ids: TelegramIdList = Field(default_factory=tuple)
    run_mode: RunMode = RunMode.POLLING
    webhook_url: str | None = None
    webhook_listen_host: str = "0.0.0.0"
    webhook_listen_port: int = 8443

    # --- Google (Drive + Gmail), populated in later phases --------------------
    google_sa_json: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_refresh_token: SecretStr | None = None
    google_api_key: SecretStr | None = None
    course_drive_folder_id: str | None = None
    # The single Drive write path (admin upload filing) is off unless explicitly enabled.
    drive_write_enabled: bool = False

    # --- Notifications / worker ----------------------------------------------
    broadcast_rate_per_sec: float = 25.0
    drive_poll_minutes: int = 15
    # Single-process mode (default): run the scheduler jobs inside the bot's event loop.
    run_scheduler_in_bot: bool = True
    course_website_url: str = "https://oz-ve-ruach-journey.lovable.app/"
    schedule_refresh_hours: int = 168
    precompute_hour: int = 3
    # Per-user cooldown (seconds) for heavy ops (deep summary, transcription, web search).
    heavy_op_cooldown_sec: float = 30.0

    # --- Homework email routing ----------------------------------------------
    hw_to_email: str | None = None
    hw_cc_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: SecretStr | None = None

    # --- LLM providers --------------------------------------------------------
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # --- Model registry overrides (role -> "provider:model"); defaults in code -
    model_router: str | None = None
    model_conversational: str | None = None
    model_summarizer: str | None = None
    model_email_writer: str | None = None
    model_recommendations: str | None = None
    asr_model: str = "gpt-4o-mini-transcribe"

    # --- RAG / recommendations (Phase 6) -------------------------------------
    embeddings_model: str = "text-embedding-3-small"
    web_search_enabled: bool = False
    rag_top_k: int = 4

    def has_any_llm_provider(self) -> bool:
        """True if at least one chat-LLM provider key is configured."""
        return any(
            (self.anthropic_api_key, self.openai_api_key, self.google_api_key)
        )

    # --- Datastore / vector store --------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/oz_veruach.db"
    supabase_db_url: SecretStr | None = None

    @field_validator("owner_telegram_ids", "admin_telegram_ids", mode="before")
    @classmethod
    def _parse_id_list(cls, value: object) -> object:
        """Accept a comma-separated string or an iterable of ints for ID allowlists."""
        if value is None or value == "":
            return ()
        if isinstance(value, str):
            return tuple(int(part) for part in value.split(",") if part.strip())
        return value

    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.environment is Environment.PRODUCTION

    def require_telegram_token(self) -> str:
        """Return the bot token, raising a clear error if it is missing.

        Used at process startup so the bot fails fast with an actionable message
        instead of deep inside the Telegram client.
        """
        if self.telegram_bot_token is None:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
            )
        return self.telegram_bot_token.get_secret_value()

    def is_owner(self, telegram_user_id: int) -> bool:
        """Return True if the given Telegram user id is an owner (superadmin)."""
        return telegram_user_id in self.owner_telegram_ids

    def is_admin(self, telegram_user_id: int) -> bool:
        """Return True if the user is an admin. Owners are implicitly admins."""
        return (
            telegram_user_id in self.admin_telegram_ids
            or telegram_user_id in self.owner_telegram_ids
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so the environment is parsed once per process. Tests can call
    ``get_settings.cache_clear()`` after monkeypatching the environment.
    """
    return Settings()
