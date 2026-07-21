# File: models/element.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Element(BaseModel):
    """A single translation unit within a scene."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    element_number: Optional[int] = Field(default=None, description="Sequential number within the scene.")
    type: Optional[str] = Field(default=None, description="Type of text (e.g., speech_bubble, sfx, narration).")
    speaker: Optional[str] = Field(default=None, description="Character name or narrator label.")
    original: Optional[str] = Field(default=None, description="Original untranslated text.")
    translation: Optional[str] = Field(default=None, description="Arabic translation.")
    alternative: Optional[str] = Field(default=None, description="Alternative translation or footnote.")
    reason: Optional[str] = Field(default=None, description="AI justification for translation choices.")