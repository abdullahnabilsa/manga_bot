# File: core/user_settings_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class UserSettingsManager:
    """
    Manages persistent user settings using a JSON file.
    Stores the selected translation persona per user ID.
    """

    def __init__(self, file_path: str = "users_data.json") -> None:
        self._file_path = file_path
        self._lock = asyncio.Lock()
        self._settings: Dict[int, str] = {}
        self._load_settings()

    def _load_settings(self) -> None:
        """Loads settings from the JSON file at startup."""
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    # JSON keys are strings, convert back to int for user_id
                    data = json.load(f)
                    self._settings = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded settings for {len(self._settings)} users.")
            except Exception as e:
                logger.error(f"Failed to load user settings: {e}")
                self._settings = {}
        else:
            self._settings = {}

    async def _save_settings(self) -> None:
        """Saves current settings to the JSON file."""
        async with self._lock:
            try:
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(self._settings, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"Failed to save user settings: {e}")

    async def get_persona(self, user_id: int) -> Optional[str]:
        """Gets the saved persona for a user, or None if not set."""
        async with self._lock:
            return self._settings.get(user_id)

    async def set_persona(self, user_id: int, persona_name: str) -> None:
        """Sets and persists the persona for a user."""
        async with self._lock:
            self._settings[user_id] = persona_name
        await self._save_settings()
        logger.info(f"UserID={user_id} set persona to: {persona_name}")