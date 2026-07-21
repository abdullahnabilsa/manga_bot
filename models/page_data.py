# File: models/page_data.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.scene import Scene


class Metadata(BaseModel):
    """Metadata about the AI generation."""
    model_config = ConfigDict(extra="forbid")
    model: Optional[str] = Field(default=None, description="AI model used.")
    page: Optional[int] = Field(default=None, description="Current page number.")
    total_pages: Optional[int] = Field(default=None, description="Total pages in the chapter/book.")
    scene_count: Optional[int] = Field(default=None, description="Total scenes on this page.")


class PageData(BaseModel):
    """The complete structured data for a single page."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    metadata: Optional[Metadata] = Field(default=None, description="Generation metadata.")
    scenes: List[Scene] = Field(default_factory=list, description="Scenes extracted from the page.")