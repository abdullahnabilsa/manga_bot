# File: models/scene.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.element import Element


class Scene(BaseModel):
    """A logical grouping of elements on a page."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    scene_number: Optional[int] = Field(default=None, description="Sequential scene number on the page.")
    environment: Optional[str] = Field(default=None, description="Description of the scene/setting.")
    elements: List[Element] = Field(default_factory=list, description="Elements within this scene.")