# File: renderer/paginator.py
from __future__ import annotations

import logging
from typing import List

from models.page_job import PageJob
from utils.template_manager import TemplateManager

logger = logging.getLogger(__name__)

class Paginator:
    """
    Assembles scenes and paginates them safely.
    Architecture is ready for future "Short Message System" (one scene per message).
    """
    MAX_LENGTH = 3500

    def __init__(self, template_manager: TemplateManager) -> None:
        self._tm = template_manager

    def _render_scene(self, scene, is_continued: bool = False) -> str:
        """Converts a single Scene object into a formatted string fragment."""
        header_template = "scene_continued.j2" if is_continued else "scene_header.j2"
        scene_str = self._tm.render_template(header_template, {
            "scene_number": scene.scene_number,
            "environment": scene.environment
        }) + "\n"

        for elem in scene.elements:
            elem_str = self._tm.render_template("element.j2", {
                "element_number": elem.element_number,
                "type": elem.type or "text",
                "speaker": elem.speaker,
                "original": elem.original,
                "translation": elem.translation,
                "alternative": elem.alternative,
                "reason": elem.reason
            })
            scene_str += elem_str + "\n"
            
        return scene_str.strip()

    async def paginate(self, job: PageJob, page_num: int = 1) -> List[str]:
        """Paginates all scenes into a list of long messages."""
        if not job.page_data or not job.page_data.scenes:
            return [self._build_empty_message(page_num)]

        messages: List[str] = []
        current_buffer = ""
        msg_num = 1
        
        footer_next = self._tm.render_template("page_footer_next.j2", {})
        footer_end = self._tm.render_template("page_footer_end.j2", {})

        for i, scene in enumerate(job.page_data.scenes):
            is_continued = bool(current_buffer) # If buffer has content, this scene is a continuation
            scene_str = self._render_scene(scene, is_continued)
            
            # Check if adding this scene exceeds the limit
            projected_length = len(self._get_header(page_num, msg_num, is_continued)) + len(current_buffer) + len(scene_str) + len(footer_next)
            
            if projected_length <= self.MAX_LENGTH:
                current_buffer += scene_str + "\n\n"
            else:
                # Finalize current message
                messages.append(self._finalize_message(page_num, msg_num, current_buffer, is_last=False))
                msg_num += 1
                # Start new message with the scene as a continuation
                current_buffer = self._render_scene(scene, is_continued=True) + "\n\n"

        # Append final message
        is_last = True
        messages.append(self._finalize_message(page_num, msg_num, current_buffer, is_last=True))

        total_msgs = str(len(messages))
        return [msg.replace("[[ TOTAL_MSGS ]]", total_msgs) for msg in messages]

    def _get_header(self, page_num: int, msg_num: int, is_continuation: bool) -> str:
        return self._tm.render_template("page_header.j2", {
            "page_num": page_num,
            "msg_num": msg_num,
            "TOTAL_MSGS": "[[ TOTAL_MSGS ]]",
            "is_continuation": is_continuation
        })

    def _finalize_message(self, page_num: int, msg_num: int, buffer: str, is_last: bool) -> str:
        header = self._get_header(page_num, msg_num, bool(msg_num > 1))
        footer = footer_end if is_last else footer_next
        # Accessing footer_next safely if not is_last
        if not is_last:
            footer = self._tm.render_template("page_footer_next.j2", {})
        else:
            footer = self._tm.render_template("page_footer_end.j2", {})
            
        return f"{header}\n\n{buffer.strip()}{footer}"

    def _build_empty_message(self, page_num: int) -> str:
        header = self._tm.render_template("page_header.j2", {
            "page_num": page_num, "msg_num": 1, "TOTAL_MSGS": "1", "is_continuation": False
        })
        footer = self._tm.render_template("page_footer_end.j2", {})
        return f"{header}\n\n⚠️ لم يتم العثور على نصوص للترجمة في هذه الصفحة.{footer}"