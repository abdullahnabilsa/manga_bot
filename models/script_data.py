# File: models/script_data.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScriptPageData(BaseModel):
    """Data model for the NABIL persona (Raw Text Script)."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    script: str = Field(default="", description="The raw translated script text.")
    file_name: str = Field(default=None, description="Original file name of the image source.")