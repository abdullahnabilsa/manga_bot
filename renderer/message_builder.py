# File: renderer/message_builder.py
from __future__ import annotations

from models.element import Element
from models.scene import Scene
from utils.markdown_escaper import escape_markdown_v2, escape_code


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

    # Spec Constants
    SCENE_SEP = "\n\u200F• ━━━━━━━━━━━━━━━━━━━━━━━━━━ • \n\n"
    ELEMENT_SEP = "\n\u200F• ━ ━ ━ ━ ━ ━ ━ ━ • \n"
    BLOCK_SEP = "\n\u200F• ━ ━ ━ • \n"
    TYPE_TRANSLATION = {
        "speech_bubble": "فقاعة", 
        "bubble": "فقاعة", 
        "sfx": "مؤثر صوتي",
        "narration": "سرد"
    }

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
            return self.ELEMENT_SEP if self._buffer else ""
        
        header = ""
        if self._buffer: # If not the very beginning of the message
            header += self.SCENE_SEP
            
        header += f"\u200F━━━━ ✨ *{escape_markdown_v2('Scene')} {escape_markdown_v2(str(scene.scene_number))}* ✨ ━━━━\n"
        if scene.environment:
            header += f"_{escape_markdown_v2(scene.environment)}_\n"
        header += self.ELEMENT_SEP
        return header

    def format_element(self, elem: Element) -> str:
        parts = []
        translated_type = self.TYPE_TRANSLATION.get(elem.type, elem.type) if elem.type else "نص"
            
        parts.append(f"🧩 *{escape_markdown_v2('العنصر')} {escape_markdown_v2(str(elem.element_number))} \\({escape_markdown_v2(translated_type)}\\)*")
        
        if elem.speaker:
            parts.append(f"🗣 *{escape_markdown_v2('المتحدث')}:* {escape_markdown_v2(elem.speaker)}")
        
        # 1. Original Text (Quote + Inline Code)
        parts.append(f"🇬🇧 *{escape_markdown_v2('النص الأصلي')}*")
        parts.append(f"> `{escape_code(elem.original)}`")
        
        # 2. Main Translation
        parts.append(self.BLOCK_SEP)
        parts.append(f"🇸🇦 *{escape_markdown_v2('الترجمة العربية')}*")
        parts.append(f"> `{escape_code(elem.translation)}`")
        
        # 3. Alternative Translation
        if elem.alternative:
            parts.append(self.BLOCK_SEP)
            parts.append(f"🔄 *{escape_markdown_v2('ترجمة أخرى')}*")
            parts.append(f"> `{escape_code(elem.alternative)}`")
            
        # 4. Reason/Explanation (Padded Code Block)
        if elem.reason:
            parts.append(self.BLOCK_SEP)
            parts.append(f"💡 *{escape_markdown_v2('شرح الترجمة')}*")
            parts.append(f"```\n\n{escape_code(elem.reason)}\n\n```")
            
        return "\n".join(parts) + "\n"

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
            self._current_scene_header = header

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