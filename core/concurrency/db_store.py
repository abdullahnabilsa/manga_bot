# File: core/concurrency/db_store.py
from __future__ import annotations
import time
import logging
from typing import Optional
from core.database import Database

logger = logging.getLogger(__name__)

class ConcurrencyDBStore:
    """Handles all database operations for the concurrency system."""
    
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_global_limit(self) -> int:
        row = await self._db.fetchone("SELECT value FROM meta WHERE key = 'global_concurrency_limit'")
        return int(row[0]) if row else 1

    async def set_global_limit(self, limit: int) -> int:
        limit = max(1, min(5, limit))  # Hardcoded boundaries: 1 to 5
        await self._db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('global_concurrency_limit', ?)", 
            (str(limit),)
        )
        return limit

    async def grant_permanent_access(self, user_id: int) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO concurrency_access (user_id, access_type, expires_at) VALUES (?, 'permanent', NULL)",
            (user_id,)
        )

    async def revoke_access(self, user_id: int) -> None:
        await self._db.execute("DELETE FROM concurrency_access WHERE user_id = ?", (user_id,))

    async def check_user_access(self, user_id: int) -> str:
        """Returns 'permanent', 'lease', or 'none'."""
        row = await self._db.fetchone(
            "SELECT access_type, expires_at FROM concurrency_access WHERE user_id = ?", 
            (user_id,)
        )
        if not row:
            return "none"
        
        access_type, expires_at = row
        if access_type == 'permanent':
            return "permanent"
        
        if access_type == 'lease':
            if expires_at and time.time() < expires_at:
                return "lease"
            else:
                # Lease expired, clean it up
                await self._db.execute("DELETE FROM concurrency_access WHERE user_id = ?", (user_id,))
                return "none"
        
        return "none"

    async def count_active_concurrent_users(self) -> int:
        """Counts how many users currently have parallel access."""
        row = await self._db.fetchone(
            "SELECT COUNT(*) FROM concurrency_access WHERE access_type = 'permanent' OR (access_type = 'lease' AND expires_at > ?)",
            (time.time(),)
        )
        return row[0] if row else 0

    async def request_lease(self, user_id: int, duration_minutes: int = 10) -> bool:
        """Grants a temporary lease if global slots are available."""
        limit = await self.get_global_limit()
        active_count = await self.count_active_concurrent_users()
        
        # If active users with parallel access is less than global limit, we can grant a lease
        if active_count < limit:
            expires_at = time.time() + (duration_minutes * 60)
            await self._db.execute(
                "INSERT OR REPLACE INTO concurrency_access (user_id, access_type, expires_at) VALUES (?, 'lease', ?)",
                (user_id, expires_at)
            )
            logger.info(f"User {user_id} granted 10-minute concurrency lease.")
            return True
        return False