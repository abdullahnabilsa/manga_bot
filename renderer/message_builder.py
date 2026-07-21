# File: renderer/message_builder.py
from __future__ import annotations

from models.element import Element
from models.scene import Scene


class MessageBuilder:
    MAX_LENGTH = 3500

    HEADER_TEMPLATE = (
        "📖 ترجمة المانهوا\n"
        "الصفحة: {page_num}\n"
        "الرسالة: {msg_num} من {total_msgs}\n"
        "━━━━━━━━━━━━━━━\n"
    )
    CONTINUATION_MARKER = "Scene (Continued)\n\n" 
    FOOTER_NEXT = "\n\n━━━━━━━━━━━━━━━\nانتهى الجزء\nيتبع..."
    FOOTER_END = "\n\n━━━━━━━━━━━━━━━\nاكتملت ترجمة الصفحة."

    def __init__(self, page_num: int, msg_num: int, is_continuation: bool) -> None:
        self.page_num = page_num
        self.msg_num = msg_num
        self.is_continuation = is_continuation
        self._buffer = ""
        self._current_scene_header = ""

    def _get_header(self) -> str:
        return self.HEADER_TEMPLATE.format(page_num=self.page_num, msg_num=self.msg_num, total_msgs="{TOTAL_MSGS}")

    def _get_footer(self, is_last_message: bool) -> str:
        return self.FOOTER_END if is_last_message else self.FOOTER_NEXT

    def format_scene_header(self, scene: Scene) -> str:
        if not scene.scene_number and not scene.environment:
            return ""
        parts = []
        if scene.scene_number:
            parts.append(f"🎬 المشهد {scene.scene_number}")
        if scene.environment:
            parts.append(f"🌍 {scene.environment}")
        return "\n".join(parts) + "\n\n"

    def format_element(self, elem: Element) -> str:
        parts = []
        if elem.speaker:
            parts.append(f"🗣️ {elem.speaker}")
        if elem.original:
            parts.append(f"🇯🇵 {elem.original}")
        if elem.translation:
            parts.append(f"🇸🇦 {elem.translation}")
        if elem.alternative:
            parts.append(f"💬 {elem.alternative}")
        if elem.reason:
            parts.append(f"ℹ️ {elem.reason}")
        if not parts: return ""
        return "\n".join(parts) + "\n\n"

    def can_fit_scene_header(self, scene: Scene) -> bool:
        header = self.format_scene_header(scene)
        if not header: return True
        projected_length = len(self._get_header()) + len(self.CONTINUATION_MARKER if self.is_continuation else "") + len(self._buffer) + len(header) + len(self.FOOTER_NEXT)
        return projected_length <= self.MAX_LENGTH

    def can_fit_element(self, elem: Element) -> bool:
        formatted_elem = self.format_element(elem)
        if not formatted_elem: return True
        projected_length = len(self._get_header()) + len(self.CONTINUATION_MARKER if self.is_continuation else "") + len(self._buffer) + len(self._current_scene_header) + len(formatted_elem) + len(self.FOOTER_NEXT)
        return projected_length <= self.MAX_LENGTH

    def add_scene_header(self, scene: Scene) -> None:
        header = self.format_scene_header(scene)
        if header:
            self._buffer += header
            self._current_scene_header = "" # It's now part of the buffer

    def add_element(self, elem: Element) -> None:
        formatted = self.format_element(elem)
        if formatted:
            self._buffer += self._current_scene_header + formatted
            self._current_scene_header = "" # Clear after adding

    def build(self, is_last_message: bool) -> str:
        header = self._get_header()
        continuation = self.CONTINUATION_MARKER if self.is_continuation else ""
        footer = self._get_footer(is_last_message)
        return f"{header}{continuation}{self._buffer}{footer}"