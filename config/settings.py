# File: config/settings.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration loaded at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MANGA_BOT_",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str

    # AI Engine
    ai_provider: str = "gemini"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 60.0

    # Queue & Job Manager
    queue_max_size: int = 100
    post_job_delay_seconds: int = 10

    # Telegram rendering limits
    telegram_text_limit: int = 4096
    telegram_send_delay_seconds: float = 0.3

    # Pagination
    message_max_length: int = 3500

    # Logging
    log_level: str = "INFO"