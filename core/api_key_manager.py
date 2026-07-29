# File: core/api_key_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Manages public and user-specific API keys securely."""
    
    def __init__(self, file_path: str = "api_keys.json") -> None:
        self._file_path = file_path
        self._lock = asyncio.Lock()
        self._data = {
            "public_keys": [],
            "user_keys": {}
        }
        self._load_keys()

    def _load_keys(self) -> None:
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    self._data["public_keys"] = loaded_data.get("public_keys", [])
                    self._data["user_keys"] = loaded_data.get("user_keys", {})
                    logger.info(f"APIKeyManager loaded {len(self._data['public_keys'])} public keys and {len(self._data['user_keys'])} user keys.")
            except Exception as e:
                logger.error(f"Failed to load API keys: {e}")
        else:
            self._save_keys_sync()

    def _save_keys_sync(self) -> None:
        """Synchronous save to be called safely inside the async lock."""
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4)

    async def add_public_key(self, key: str) -> bool:
        async with self._lock:
            if key not in self._data["public_keys"]:
                self._data["public_keys"].append(key)
                self._save_keys_sync()
                return True
            return False

    async def remove_public_key(self, key: str) -> bool:
        async with self._lock:
            if key in self._data["public_keys"]:
                self._data["public_keys"].remove(key)
                self._save_keys_sync()
                return True
            return False

    def get_public_keys(self) -> List[str]:
        return list(self._data["public_keys"])

    async def set_user_key(self, user_id: int, key: str) -> None:
        async with self._lock:
            self._data["user_keys"][str(user_id)] = key
            self._save_keys_sync()

    async def remove_user_key(self, user_id: int) -> bool:
        async with self._lock:
            if str(user_id) in self._data["user_keys"]:
                del self._data["user_keys"][str(user_id)]
                self._save_keys_sync()
                return True
            return False

    def get_user_key(self, user_id: int) -> Optional[str]:
        return self._data["user_keys"].get(str(user_id))

    def get_keys_for_user(self, user_id: int) -> List[str]:
        """
        Returns the list of API keys to use for a specific user.
        If the user has a custom key, it takes precedence.
        Otherwise, falls back to public keys.
        """
        user_key = self.get_user_key(user_id)
        if user_key:
            return [user_key]
        return self.get_public_keys()