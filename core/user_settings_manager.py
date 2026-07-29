# File: core/user_settings_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class UserSettingsManager:
    def __init__(self, file_path: str = "users_data.json") -> None:
        self._file_path = file_path
        self._lock = asyncio.Lock()
        self._settings: Dict[int, Dict[str, any]] = {}
        self._load_settings()

    def _load_settings(self) -> None:
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, str):
                            self._settings[int(k)] = {
                                "persona": v, 
                                "mode": "scene_split", 
                                "output_method": "files_only", 
                                "file_format": "docx"
                            }
                        elif isinstance(v, dict):
                            self._settings[int(k)] = {
                                "persona": v.get("persona", "Default Translator"),
                                "mode": v.get("mode", "scene_split"),
                                "output_method": v.get("output_method", "files_only"),
                                "file_format": v.get("file_format", "docx")
                            }
            except Exception as e:
                logger.error(f"Failed to load user settings: {e}")
                self._settings = {}
        else:
            self._settings = {}

    async def _save_settings(self) -> None:
        async with self._lock:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=4)

    async def get_user_settings(self, user_id: int) -> Dict[str, any]:
        async with self._lock:
            return self._settings.get(user_id, {
                "persona": "Default Translator", 
                "mode": "scene_split", 
                "output_method": "files_only", 
                "file_format": "docx"
            })

    async def get_persona(self, user_id: int) -> Optional[str]:
        async with self._lock:
            return self._settings.get(user_id, {}).get("persona")

    async def set_persona(self, user_id: int, persona_name: str) -> None:
        async with self._lock:
            if user_id not in self._settings: self._settings[user_id] = {}
            self._settings[user_id]["persona"] = persona_name
        await self._save_settings()

    async def get_delivery_mode(self, user_id: int) -> str:
        async with self._lock:
            return self._settings.get(user_id, {}).get("mode", "scene_split")

    async def set_delivery_mode(self, user_id: int, mode: str) -> None:
        async with self._lock:
            if user_id not in self._settings: self._settings[user_id] = {}
            self._settings[user_id]["mode"] = mode
        await self._save_settings()

    async def get_output_method(self, user_id: int) -> str:
        async with self._lock:
            return self._settings.get(user_id, {}).get("output_method", "files_only")

    async def set_output_method(self, user_id: int, method: str) -> None:
        async with self._lock:
            if user_id not in self._settings: self._settings[user_id] = {}
            self._settings[user_id]["output_method"] = method
        await self._save_settings()

    async def get_file_format(self, user_id: int) -> str:
        async with self._lock:
            return self._settings.get(user_id, {}).get("file_format", "docx")

    async def set_file_format(self, user_id: int, fmt: str) -> None:
        async with self._lock:
            if user_id not in self._settings: self._settings[user_id] = {}
            self._settings[user_id]["file_format"] = fmt
        await self._save_settings()