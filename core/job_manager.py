# File: core/job_manager.py
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Callable, Awaitable, Dict, List, Optional
from uuid import UUID

from core.queue_manager import AsyncSingleWorkerQueue
from core.concurrency.manager import ConcurrencyManager
from utils.logger import job_logger
from models.page_job import PageJob, JobState

logger = logging.getLogger(__name__)

class JobSubmissionResult(Enum):
    SUCCESS = 1
    QUEUE_FULL = 2

class JobManager:
    def __init__(self, queue_manager: AsyncSingleWorkerQueue, concurrency_manager: ConcurrencyManager, max_running_jobs: int = 1, post_job_delay: int = 0) -> None:
        self._queue = queue_manager
        self._concurrency_manager = concurrency_manager
        self._registry: Dict[UUID, PageJob] = {}
        self._lock = asyncio.Lock()
        self._worker_tasks: List[asyncio.Task] = []
        self.max_running_jobs = max_running_jobs
        self.POST_JOB_DELAY_SECONDS = post_job_delay

        self._processing_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None
        self._rendering_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None
        self._sending_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None
        self._error_notifier: Optional[Callable[[PageJob, Exception], Awaitable[None]]] = None

    def register_pipeline_steps(
        self,
        processing_step: Callable[[PageJob], Awaitable[PageJob]],
        rendering_step: Callable[[PageJob], Awaitable[PageJob]],
        sending_step: Callable[[PageJob], Awaitable[PageJob]]
    ) -> None:
        self._processing_step = processing_step
        self._rendering_step = rendering_step
        self._sending_step = sending_step

    def register_error_notifier(self, notifier: Callable[[PageJob, Exception], Awaitable[None]]) -> None:
        self._error_notifier = notifier

    async def submit_job(self, job: PageJob) -> JobSubmissionResult:
        async with self._lock:
            if self._queue.is_full():
                return JobSubmissionResult.QUEUE_FULL
            self._registry[job.job_id] = job
        
        job_logger.log_received(job.job_id, job.user_id)
        
        try:
            self._queue.enqueue_nowait(job.job_id)
        except asyncio.QueueFull:
            async with self._lock:
                del self._registry[job.job_id]
            return JobSubmissionResult.QUEUE_FULL

        return JobSubmissionResult.SUCCESS

    async def get_job(self, job_id: UUID) -> Optional[PageJob]:
        async with self._lock:
            return self._registry.get(job_id)

    async def start(self) -> None:
        if not self._worker_tasks:
            for i in range(self.max_running_jobs):
                task = asyncio.create_task(self._worker_loop(i + 1))
                self._worker_tasks.append(task)

    async def scale_workers(self, target_count: int) -> None:
        """Dynamically scales the number of active worker tasks."""
        async with self._lock:
            current_count = len(self._worker_tasks)
            if target_count > current_count:
                for i in range(current_count, target_count):
                    task = asyncio.create_task(self._worker_loop(i + 1))
                    self._worker_tasks.append(task)
                logger.info(f"Scaled UP workers: {current_count} -> {target_count}")
            elif target_count < current_count:
                tasks_to_cancel = self._worker_tasks[target_count:]
                self._worker_tasks = self._worker_tasks[:target_count]
                for task in tasks_to_cancel:
                    task.cancel()
                logger.info(f"Scaled DOWN workers: {current_count} -> {target_count}")

    async def stop(self) -> None:
        for task in self._worker_tasks:
            task.cancel()
        for task in self._worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks.clear()

    async def _worker_loop(self, worker_id: int) -> None:
        try:
            while True:
                job_id = await self._queue.dequeue()
                job = await self.get_job(job_id)

                if not job or not all([self._processing_step, self._rendering_step, self._sending_step]):
                    job_logger.log_error(job_id, RuntimeError("Job missing or pipeline steps not registered"))
                    await self._queue.task_done()
                    continue

                job_logger.log_started(job_id)
                
                try:
                    # --- CONCURRENCY CONTROL ---
                    await self._concurrency_manager.acquire_processing_slot(job.user_id)
                    
                    await self._transition_state(job, JobState.PROCESSING)
                    job = await self._processing_step(job)

                    await self._transition_state(job, JobState.RENDERING)
                    job = await self._rendering_step(job)

                    await self._transition_state(job, JobState.SENDING)
                    job = await self._sending_step(job)

                    await self._transition_state(job, JobState.FINISHED)
                    
                    scene_count = len(job.page_data.scenes) if job.page_data else 0
                    element_count = sum(len(s.elements) for s in job.page_data.scenes) if job.page_data else 0
                    job_logger.log_completed(job_id, scene_count, element_count)

                except Exception as e:
                    job_logger.log_error(job_id, e)
                    await self._transition_state(job, JobState.FAILED)
                    if self._error_notifier:
                        try:
                            await self._error_notifier(job, e)
                        except Exception as notify_err:
                            logger.error(f"Failed to send error notification: {notify_err}")

                finally:
                    # --- RELEASE CONCURRENCY SLOT ---
                    await self._concurrency_manager.release_processing_slot(job.user_id)
                    await self._queue.task_done()
                    async with self._lock:
                        self._registry.pop(job.job_id, None)
                    await asyncio.sleep(self.POST_JOB_DELAY_SECONDS)
        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} gracefully shut down.")
            return

    async def _transition_state(self, job: PageJob, new_state: JobState) -> None:
        async with self._lock:
            job.state = new_state
            self._registry[job.job_id] = job