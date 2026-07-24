# File: renderer/message_builder.py
from __future__ import annotations

from models.element import Element
from models.scene import Scene
from utils.template_manager import TemplateManager


class MessageBuilder:
    MAX_LENGTH = 3500

    def __init__(self, template_manager: TemplateManager, page_num: int, msg_num: int, is_continuation: bool) -> None:
        self._tm = template_manager
        self.page_num = page_num
        self.msg_num = msg_num
        self.is_continuation = is_continuation
        self._buffer = ""
        self._current_scene_header = ""
        
        # Pre-render footers for length calculations
        self._footer_next = self._tm.render_template("footer_next.j2", {})
        self._footer_end = self._tm.render_template("footer_end.j2", {})

    def _get_header(self) -> str:
        return self._tm.render_template("page_header.j2", {
            "page_num": self.page_num,
            "msg_num": self.msg_num,
            "TOTAL_MSGS": "{TOTAL_MSGS}", # Placeholder for later replacement
            "is_continuation": self.is_continuation
        })

    def format_scene_header(self, scene: Scene) -> str:
        if not scene.scene_number and not scene.environment:
            return ""
        return self._tm.render_template("scene_header.j2", {
            "scene_number": scene.scene_number,
            "environment": scene.environment
        }) + "\n" # Extra newline to separate header from elements

    def format_element(self, elem: Element) -> str:
        return self._tm.render_template("element.j2", {
            "speaker": elem.speaker,
            "original": elem.original,
            "translation": elem.translation,
            "alternative": elem.alternative,
            "reason": elem.reason,
            "type": elem.type,
            "element_number": elem.element_number
        }) + "\n" # Extra newline to separate elements

    def can_fit_scene_header(self, scene: Scene) -> bool:
        header = self.format_scene_header(scene)
        if not header: return True
        projected_length = len(self._get_header()) + len(self._buffer) + len(header) + len(self._footer_next)
        return projected_length <= self.MAX_LENGTH

    def can_fit_element(self, elem: Element) -> bool:
        formatted_elem = self.format_element(elem)
        if not formatted_elem: return True
        projected_length = len(self._get_header()) + len(self._buffer) + len(self._current_scene_header) + len(formatted_elem) + len(self._footer_next)
        return projected_length <= self.MAX_LENGTH

    def add_scene_header(self, scene: Scene) -> None:
        header = self.format_scene_header(scene)
        if header:
            self._buffer += header
            self._current_scene_header = ""

    def add_element(self, elem: Element) -> None:
        formatted = self.format_element(elem)
        if formatted:
            self._buffer += self._current_scene_header + formatted
            self._current_scene_header = ""

    def build(self, is_last_message: bool) -> str:
        header = self._get_header()
        footer = self._footer_end if is_last_message else self._footer_next
        return f"{header}{self._buffer}{footer}"