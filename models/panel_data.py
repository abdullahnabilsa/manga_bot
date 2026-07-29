# File: models/panel_data.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TranslationMetadata(BaseModel):
    """Metadata specific to the panel-based translation schema."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    source_language: Optional[str] = Field(default=None, description="Source language of the text.")
    target_language: Optional[str] = Field(default=None, description="Target language for translation.")
    style: Optional[str] = Field(default=None, description="Translation style applied.")


class PanelElement(BaseModel):
    """A single translation unit within a panel."""
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    type: Optional[str] = Field(default=None, description="Type of text (e.g., speech_bubble, sfx, thought_bubble, narrative_box).")
    character: Optional[str] = Field(default=None, description="Character name or speaker label.")
    original_text: Optional[str] = Field(default=None, description="Original untranslated text.")
    translated_text: Optional[str] = Field(default=None, description="Arabic translation.")
    description: Optional[str] = Field(default=None, description="Additional context or description (e.g., for SFX).")


class Panel(BaseModel):
    """A logical panel grouping on a page."""
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    panel_index: Optional[int] = Field(default=None, description="Sequential panel number on the page.")
    elements: List[PanelElement] = Field(default_factory=list, description="Elements within this panel.")


class PanelPageData(BaseModel):
    """The complete structured data for a single page using the Panel schema."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    translation_metadata: Optional[TranslationMetadata] = Field(default=None, description="Translation metadata.")
    panels: List[Panel] = Field(default_factory=list, description="Panels extracted from the page.")
    file_name: Optional[str] = Field(default=None, description="Original file name of the image source.")