# File: modules/base_persona.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import io
import os
import sys

from models.page_job import PageJob
from models.page_data import PageData


class BasePersona(ABC):
    """
    Abstract base class defining the contract for all translation personas.
    Each persona is a self-contained module (Plugin).
    """
    # يتم تعريف اسم المترجم في كل كلاس يرث من هذا الأساس
    name: str = "Base Persona"

    @property
    def module_dir(self) -> str:
        """يُرجع مسار مجلد المترجم الحالي ديناميكياً"""
        module = sys.modules[self.__class__.__module__]
        return os.path.dirname(os.path.abspath(module.__file__))

    @property
    def prompt(self) -> str:
        """يقرأ ملف البرومبت (prompt.txt) من داخل مجلد المترجم تلقائياً"""
        prompt_path = os.path.join(self.module_dir, "prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    @abstractmethod
    async def validate_and_update_job(self, job: PageJob, raw_json: Dict[str, Any]) -> PageJob:
        """Parse and validate the raw JSON from AI, updating the PageJob."""
        pass

    @abstractmethod
    async def paginate(self, job: PageJob, mode: str = "scene_split") -> List[str]:
        """Generate formatted message strings ready for Telegram."""
        pass

    @abstractmethod
    def generate_txt(self, pages: List[PageData]) -> io.BytesIO:
        """Generate a TXT file in memory from a list of page data."""
        pass

    @abstractmethod
    def generate_docx(self, pages: List[PageData]) -> io.BytesIO:
        """Generate a DOCX file in memory from a list of page data."""
        pass