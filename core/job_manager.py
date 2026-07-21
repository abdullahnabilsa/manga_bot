# File: core/job_manager.py
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable, Dict, Optional
from uuid import UUID

from core.queue_manager import AsyncSingleWorkerQueue
from utils.logger import job_logger
from models.page_job import PageJob, JobState


class JobManager:
    """
    Manages the PageJob lifecycle, enforces the state machine, 
    and executes jobs serially with a strict 10-second delay between completions.
    
    State Machine: waiting -> processing -> rendering -> sending -> finished
    """
    MAX_RUNNING_JOBS = 1
    POST_JOB_DELAY_SECONDS = 10

    def __init__(self, queue_manager: AsyncSingleWorkerQueue, post_job_delay: int = 10) -> None:
        self._queue = queue_manager
        self._registry: Dict[UUID, PageJob] = {}
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self.POST_JOB_DELAY_SECONDS = post_job_delay

        # Pipeline step executors (injected later)
        self._processing_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None
        self._rendering_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None
        self._sending_step: Optional[Callable[[PageJob], Awaitable[PageJob]]] = None

    def register_pipeline_steps(
        self,
        processing_step: Callable[[PageJob], Awaitable[PageJob]],
        rendering_step: Callable[[PageJob], Awaitable[PageJob]],
        sending_step: Callable[[PageJob], Awaitable[PageJob]]
    ) -> None:
        """Inject the asynchronous pipeline step executors."""
        self._processing_step = processing_step
        self._rendering_step = rendering_step
        self._sending_step = sending_step

    async def submit_job(self, job: PageJob) -> None:
        """Register a new job and enqueue its ID."""
        async with self._lock:
            self._registry[job.job_id] = job
        job_logger.log_received(job.job_id, job.user_id)
        await self._queue.enqueue(job.job_id)

    async def get_job(self, job_id: UUID) -> Optional[PageJob]:
        """Retrieve a job from the registry by ID."""
        async with self._lock:
            return self._registry.get(job_id)

    async def start(self) -> None:
        """Start the background worker loop."""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Cancel the background worker loop gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def _worker_loop(self) -> None:
        """The main serial worker loop. Processes exactly one job at a time."""
        while True:
            job_id = await self._queue.dequeue()
            job = await self.get_job(job_id)

            if not job or not all([self._processing_step, self._rendering_step, self._sending_step]):
                job_logger.log_error(job_id, RuntimeError("Job missing or pipeline steps not registered"))
                await self._queue.complete_active_job()
                continue

            job_logger.log_started(job_id)
            
            try:
                # Execute State Machine
                await self._transition_state(job, JobState.PROCESSING)
                job = await self._processing_step(job) # type: ignore

                await self._transition_state(job, JobState.RENDERING)
                job = await self._rendering_step(job) # type: ignore

                await self._transition_state(job, JobState.SENDING)
                job = await self._sending_step(job) # type: ignore

                await self._transition_state(job, JobState.FINISHED)
                
                # Calculate metrics
                scene_count = 1 if job.scene else 0
                element_count = len(job.scene.elements) if job.scene else 0
                
                job_logger.log_completed(job_id, scene_count, element_count)

            except Exception as e:
                job_logger.log_error(job_id, e)
                await self._transition_state(job, JobState.FAILED)

            finally:
                await self._queue.complete_active_job()
                # STRICT RULE: 10-second delay before pulling next job
                await asyncio.sleep(self.POST_JOB_DELAY_SECONDS)

    async def _transition_state(self, job: PageJob, new_state: JobState) -> None:
        """Safely transition the job state and update the registry."""
        async with self._lock:
            job.state = new_state
            self._registry[job.job_id] = job