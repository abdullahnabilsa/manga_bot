# File: core/concurrency/manager.py
from __future__ import annotations
import logging
from .db_store import ConcurrencyDBStore
from .locks import LockManager

logger = logging.getLogger(__name__)

class ConcurrencyManager:
    """
    The Facade that orchestrates DB checks and in-memory locks.
    JobManager and Senders will ONLY talk to this class.
    """
    def __init__(self, db_store: ConcurrencyDBStore) -> None:
        self._db_store = db_store
        self._locks = LockManager()
        self._job_manager = None  # will be injected later

    def register_job_manager(self, job_manager) -> None:
        self._job_manager = job_manager

    async def get_global_limit(self) -> int:
        return await self._db_store.get_global_limit()

    async def set_global_limit(self, limit: int) -> int:
        new_limit = await self._db_store.set_global_limit(limit)
        # --- DYNAMIC SCALING ---
        if self._job_manager:
            await self._job_manager.scale_workers(new_limit)
        return new_limit

    async def grant_permanent_access(self, user_id: int) -> None:
        await self._db_store.grant_permanent_access(user_id)

    async def revoke_access(self, user_id: int) -> None:
        await self._db_store.revoke_access(user_id)

    async def request_lease(self, user_id: int) -> bool:
        return await self._db_store.request_lease(user_id)

    async def acquire_processing_slot(self, user_id: int) -> None:
        """
        If user has parallel access, returns immediately (doesn't block other workers).
        If not, acquires a lock that blocks other workers from processing the same user's jobs.
        """
        access = await self._db_store.check_user_access(user_id)
        if access == "none":
            user_lock = await self._locks.get_user_lock(user_id)
            await user_lock.acquire()
            logger.debug(f"User {user_id} acquired sequential processing lock.")
        # If 'permanent' or 'lease', we do not acquire the lock, allowing concurrency.

    async def release_processing_slot(self, user_id: int) -> None:
        access = await self._db_store.check_user_access(user_id)
        if access == "none":
            user_lock = await self._locks.get_user_lock(user_id)
            if user_lock.locked():
                user_lock.release()

    async def acquire_chat_send_lock(self, chat_id: int) -> None:
        """Prevents Telegram API rate limits by serializing sends per chat."""
        chat_lock = await self._locks.get_chat_lock(chat_id)
        await chat_lock.acquire()

    async def release_chat_send_lock(self, chat_id: int) -> None:
        chat_lock = await self._locks.get_chat_lock(chat_id)
        if chat_lock.locked():
            chat_lock.release()

    async def acquire_tracker_lock(self, user_id: int) -> None:
        """Prevents Race Conditions when multiple workers edit the tracker simultaneously."""
        tracker_lock = await self._locks.get_tracker_lock(user_id)
        await tracker_lock.acquire()

    async def release_tracker_lock(self, user_id: int) -> None:
        tracker_lock = await self._locks.get_tracker_lock(user_id)
        if tracker_lock.locked():
            tracker_lock.release()