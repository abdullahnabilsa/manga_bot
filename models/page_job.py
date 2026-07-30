# File: models/page_job.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from models.page_data import PageData


class JobState(str, Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    RENDERING = "rendering"
    SENDING = "sending"
    FINISHED = "finished"
    FAILED = "failed"

class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_index: int
    total_pages: int
    text: str
    parse_mode: Optional[str] = "MarkdownV2"
    reply_markup: Optional[Any] = None
    message_id: Optional[int] = None

class PageJob(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    job_id: UUID = Field(default_factory=uuid4)
    user_id: int
    chat_id: int
    state: JobState = JobState.WAITING
    
    image_file_id: Optional[str] = None  # <--- جديد: معرف الصورة للاستجابة الفورية
    image_bytes: Optional[bytes] = None   # سيتم تعبئته لاحقاً أثناء المعالجة
    file_name: Optional[str] = None
    page_data: Optional[PageData] = None
    message_payloads: List[MessagePayload] = Field(default_factory=list)
    
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # --- UX Enhancements Fields ---
    photo_message_id: Optional[int] = None  # ID of the user's photo message
    status_message_id: Optional[int] = None # ID of the bot's "Processing..." message