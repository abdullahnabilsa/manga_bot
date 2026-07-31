# File: core/access_manager.py
from __future__ import annotations

import logging
from typing import List
from core.database import Database

logger = logging.getLogger(__name__)

class AccessManager:
    """Manages access control hierarchy and join requests via SQLite."""
    
    def __init__(self, db: Database, super_admin_ids: str = "") -> None:
        self._db = db
        # تقسيم النص إلى قائمة IDs وتنظيف المسافات
        self._super_admin_ids = [uid.strip() for uid in super_admin_ids.split(",") if uid.strip()]

    def is_super_admin(self, user_id: int) -> bool:
        return str(user_id) in self._super_admin_ids

    async def is_admin(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return True
        row = await self._db.fetchone("SELECT 1 FROM users_access WHERE user_id = ? AND role = 'admin'", (user_id,))
        return row is not None

    async def is_authorized(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return True
        row = await self._db.fetchone("SELECT 1 FROM users_access WHERE user_id = ?", (user_id,))
        return row is not None

    async def is_join_requests_open(self) -> bool:
        row = await self._db.fetchone("SELECT value FROM meta WHERE key = 'join_requests_open'")
        return row is not None and row[0] == 'true'

    async def set_join_requests(self, status: bool) -> None:
        val = 'true' if status else 'false'
        await self._db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('join_requests_open', ?)", (val,))

    async def add_user(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return False
        existing = await self._db.fetchone("SELECT role FROM users_access WHERE user_id = ?", (user_id,))
        if existing: return False
        await self._db.execute("INSERT INTO users_access (user_id, role) VALUES (?, 'user')", (user_id,))
        return True

    async def remove_user(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return False
        existing = await self._db.fetchone("SELECT 1 FROM users_access WHERE user_id = ? AND role = 'user'", (user_id,))
        if not existing: return False
        await self._db.execute("DELETE FROM users_access WHERE user_id = ? AND role = 'user'", (user_id,))
        return True

    async def add_admin(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return False
        await self._db.execute("INSERT OR REPLACE INTO users_access (user_id, role) VALUES (?, 'admin')", (user_id,))
        return True

    async def remove_admin(self, user_id: int) -> bool:
        if self.is_super_admin(user_id): return False
        existing = await self._db.fetchone("SELECT 1 FROM users_access WHERE user_id = ? AND role = 'admin'", (user_id,))
        if not existing: return False
        await self._db.execute("DELETE FROM users_access WHERE user_id = ? AND role = 'admin'", (user_id,))
        return True

    async def get_admins(self) -> List[str]:
        rows = await self._db.fetchall("SELECT user_id FROM users_access WHERE role = 'admin'")
        db_admins = [str(row[0]) for row in rows]
        # دمج السوبر أدمنز مع أدمنز القاعدة وإزالة التكرار
        all_admins = list(set(self._super_admin_ids + db_admins))
        return all_admins

    async def get_users(self) -> List[str]:
        rows = await self._db.fetchall("SELECT user_id FROM users_access WHERE role = 'user'")
        return [str(row[0]) for row in rows]