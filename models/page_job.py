# File: models/page_job.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from models.scene import Scene


class JobState(str, Enum):
    """Finite state machine for a single page-processing job."""

    WAITING = "waiting"
    PROCESSING = "processing"
    RENDERING = "rendering"
    SENDING = "sending"
    FINISHED = "finished"
    FAILED = "failed"


class MessagePayload(BaseModel):
    """
    A single renderable Telegram message. The Paginator splits Scene
    output into one or more of these, respecting Telegram's limits.
    """

    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(description="Zero-based position within the paginated set.")
    total_pages: int = Field(description="Total number of pages in this job's message set.")
    text: str = Field(description="Formatted message body (HTML or Markdown).")
    parse_mode: Optional[str] = Field(default="MarkdownV2", description="Telegram parse mode.")
    reply_markup: Optional[Any] = Field(default=None, description="Inline keyboard markup.")
    message_id: Optional[int] = Field(default=None, description="Telegram message_id once sent.")


class PageJob(BaseModel):
    """
    The central state object for a single page. Carried through the entire pipeline.
    No global state — every component receives a job_id and looks up this object.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    job_id: UUID = Field(default_factory=uuid4, description="Globally unique identifier for this page job.")
    user_id: int = Field(description="Telegram user ID of the requester.")
    chat_id: int = Field(description="Telegram chat ID where results are sent.")
    state: JobState = Field(default=JobState.WAITING, description="Current position in the processing state machine.")
    
    image_bytes: Optional[bytes] = Field(default=None, description="Raw image bytes of the submitted page.")
    scene: Optional[Scene] = Field(default=None, description="Parsed and validated Scene (populated after AI + Parser).")
    message_payloads: List[MessagePayload] = Field(default_factory=list, description="Paginated message set ready for rendering.")
    
    error: Optional[str] = Field(default=None, description="Error description if state == FAILED.")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── State-machine guard helpers (signatures only, no logic) ──
    def transition_to(self, new_state: JobState) -> None: ...
    def can_transition_to(self, new_state: JobState) -> bool: ...