# File: modules/default_translator/persona.py
from __future__ import annotations

import io
from typing import Any, Dict, List

from modules.base_persona import BasePersona
from models.page_job import PageJob
from models.page_data import PageData
from parser.validator import Validator
from renderer.paginator import Paginator
from utils.file_generator import FileGenerator


class DefaultPersona(BasePersona):
    """
    The default translation persona using the 'Scenes' JSON schema.
    """
    name = "Default Translator"

    def __init__(self) -> None:
        self._validator = Validator()
        self._paginator = Paginator()

    async def validate_and_update_job(self, job: PageJob, raw_json: Dict[str, Any]) -> PageJob:
        return await self._validator.validate_and_update_job(job, raw_json)

    async def paginate(self, job: PageJob, mode: str = "scene_split") -> List[str]:
        return await self._paginator.paginate(job, page_num=1, mode=mode)

    def generate_txt(self, pages: List[PageData]) -> io.BytesIO:
        return FileGenerator.generate_txt(pages)

    def generate_docx(self, pages: List[PageData]) -> io.BytesIO:
        return FileGenerator.generate_docx(pages)