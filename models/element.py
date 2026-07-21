# File: models/element.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Element(BaseModel):
    """
    A single translation unit extracted from a manga/manhwa panel.
    All fields default to None so that partial AI output never crashes
    the pipeline — the Validator stage handles missing fields gracefully.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    environment: Optional[str] = Field(
        default=None,
        description="Scene/setting context where the dialogue occurs.",
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Character name, narrator label, or SFX identifier.",
    )
    original: Optional[str] = Field(
        default=None,
        description="Original untranslated text as it appears in the panel.",
    )
    translation: Optional[str] = Field(
        default=None,
        description="Arabic translation of the original text.",
    )
    alternative: Optional[str] = Field(
        default=None,
        description="Alternative translation, footnote, or clarification.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="AI justification for translation or omission choices.",
    )