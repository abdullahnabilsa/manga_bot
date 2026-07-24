# File: config/settings.py
from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MANGA_BOT_",
        extra="ignore",
    )

    telegram_bot_token: str
    admin_id: Optional[int] = None  # 🆕 معرف تيليجرام للمشرف (للأوامر الحساسة)

    ai_provider: str = "gemini"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 60.0

    queue_max_size: int = 100
    post_job_delay_seconds: int = 10

    telegram_text_limit: int = 4096
    telegram_send_delay_seconds: float = 0.3

    message_max_length: int = 3500
    log_level: str = "INFO"