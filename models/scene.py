# File: models/scene.py
from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from models.element import Element


class Scene(BaseModel):
    """
    An ordered collection of Element objects representing one full page.
    Ordering MUST follow Arabic reading convention: Top-to-Bottom, Right-to-Left.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    elements: List[Element] = Field(
        default_factory=list,
        description="Elements in Arabic reading order (RTL, top-to-bottom).",
    )