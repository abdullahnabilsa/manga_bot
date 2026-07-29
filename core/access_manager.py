# File: core/access_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

class AccessManager:
    """Manages access control hierarchy and join requests."""
    
    def __init__(self, file_path: str = "access_control.json", super_admin_id: str = "7203463194") -> None:
        self._file_path = file_path
        self._super_admin_id = str(super_admin_id)
        self._lock = asyncio.Lock()
        self._data = {
            "admins": [],
            "users": [],
            "join_requests_open": False
        }
        self._load_data()

    def _load_data(self) -> None:
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data["admins"] = loaded.get("admins", [])
                    self._data["users"] = loaded.get("users", [])
                    self._data["join_requests_open"] = loaded.get("join_requests_open", False)
            except Exception as e:
                logger.error(f"Failed to load access control: {e}")
        self._save_data_sync()

    def _save_data_sync(self) -> None:
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4)

    def is_super_admin(self, user_id: int) -> bool:
        return str(user_id) == self._super_admin_id

    def is_admin(self, user_id: int) -> bool:
        return self.is_super_admin(user_id) or str(user_id) in self._data["admins"]

    def is_authorized(self, user_id: int) -> bool:
        return self.is_admin(user_id) or str(user_id) in self._data["users"]

    def is_join_requests_open(self) -> bool:
        return self._data.get("join_requests_open", False)

    async def set_join_requests(self, status: bool) -> None:
        async with self._lock:
            self._data["join_requests_open"] = status
            self._save_data_sync()

    async def add_user(self, user_id: int) -> bool:
        async with self._lock:
            uid = str(user_id)
            if uid not in self._data["users"] and not self.is_admin(user_id):
                self._data["users"].append(uid)
                self._save_data_sync()
                return True
            return False

    async def remove_user(self, user_id: int) -> bool:
        async with self._lock:
            uid = str(user_id)
            if uid in self._data["users"]:
                self._data["users"].remove(uid)
                self._save_data_sync()
                return True
            return False

    async def add_admin(self, user_id: int) -> bool:
        async with self._lock:
            uid = str(user_id)
            if uid != self._super_admin_id and uid not in self._data["admins"]:
                self._data["admins"].append(uid)
                if uid in self._data["users"]: self._data["users"].remove(uid)
                self._save_data_sync()
                return True
            return False

    async def remove_admin(self, user_id: int) -> bool:
        async with self._lock:
            uid = str(user_id)
            if uid == self._super_admin_id:
                return False
            if uid in self._data["admins"]:
                self._data["admins"].remove(uid)
                self._save_data_sync()
                return True
            return False

    def get_admins(self) -> List[str]:
        return [self._super_admin_id] + self._data["admins"]

    def get_users(self) -> List[str]:
        return self._data["users"]