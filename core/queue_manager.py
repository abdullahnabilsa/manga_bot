# File: core/queue_manager.py
from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

from utils.logger import job_logger


class AsyncSingleWorkerQueue:
    """
    An asynchronous queue implementation enforcing strict serial execution.
    Designed to hold only Job IDs (UUIDs) to maintain a stateless architecture.
    """
    def __init__(self, max_size: int = 100) -> None:
        self._queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=max_size)
        self._lock = asyncio.Lock()
        self._active_job: Optional[UUID] = None

    async def enqueue(self, job_id: UUID) -> None:
        """Add a Job ID to the back of the queue."""
        await self._queue.put(job_id)
        job_logger._logger.info(f"JobID={job_id} | Event=ENQUEUED | QueueSize={self._queue.qsize()}")

    async def dequeue(self) -> UUID:
        """
        Block until a Job ID is available.
        Tracks the active job to enforce single-worker constraints.
        """
        async with self._lock:
            job_id = await self._queue.get()
            self._active_job = job_id
            return job_id

    async def complete_active_job(self) -> None:
        """Mark the currently active job as complete and clear the active slot."""
        async with self._lock:
            self._active_job = None
            self._queue.task_done()

    async def size(self) -> int:
        """Return the current number of waiting jobs."""
        return self._queue.qsize()

    async def get_active_job(self) -> Optional[UUID]:
        """Return the Job ID currently being processed, if any."""
        async with self._lock:
            return self._active_job