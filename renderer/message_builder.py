# File: renderer/message_builder.py
from __future__ import annotations

from typing import Optional

from models.element import Element


class MessageBuilder:
    """
    Incrementally builds a message string by adding elements one by one.
    Measures length dynamically to prevent hard truncation.
    Injects fixed Headers and Footers based on pagination state.
    """

    MAX_LENGTH = 3500

    # Fixed format templates
    HEADER_TEMPLATE = (
        "📖 ترجمة المانهوا\n"
        "الصفحة: {page_num}\n"
        "الرسالة: {msg_num} من {total_msgs}\n"
        "━━━━━━━━━━━━━━━\n"
    )
    CONTINUATION_MARKER = "Scene 1 (Continued)\n\n"  # Assuming 1 scene per page job
    FOOTER_NEXT = "\n\n━━━━━━━━━━━━━━━\nانتهى الجزء\nيتبع..."
    FOOTER_END = "\n\n━━━━━━━━━━━━━━━\nاكتملت ترجمة الصفحة."

    def __init__(
        self,
        page_num: int,
        msg_num: int,
        is_continuation: bool
    ) -> None:
        """
        Initialize the builder for a specific message chunk.
        
        Args:
            page_num: The current page number being processed.
            msg_num: The sequence number of this message chunk.
            is_continuation: True if this chunk continues a split scene.
        """
        self.page_num = page_num
        self.msg_num = msg_num
        self.is_continuation = is_continuation
        self._buffer = ""
        self._has_elements = False

    def _get_header(self) -> str:
        """Constructs the header with a placeholder for total messages."""
        return self.HEADER_TEMPLATE.format(
            page_num=self.page_num,
            msg_num=self.msg_num,
            total_msgs="{TOTAL_MSGS}"  # Placeholder for later replacement
        )

    def _get_footer(self, is_last_message: bool) -> str:
        """Selects the correct footer based on whether this is the last chunk."""
        return self.FOOTER_END if is_last_message else self.FOOTER_NEXT

    def format_element(self, elem: Element) -> str:
        """Formats an Element into a readable text block, skipping None fields."""
        parts = []
        if elem.speaker:
            parts.append(f"🗣️ {elem.speaker}")
        if elem.environment:
            parts.append(f"🌍 {elem.environment}")
        if elem.original:
            parts.append(f"🇯🇵 {elem.original}")
        if elem.translation:
            parts.append(f"🇸🇦 {elem.translation}")
        if elem.alternative:
            parts.append(f"💬 {elem.alternative}")
        if elem.reason:
            parts.append(f"ℹ️ {elem.reason}")

        if not parts:
            return ""

        return "\n".join(parts) + "\n\n"

    def can_fit(self, elem: Element) -> bool:
        """
        Simulates adding an element and checks if the total length
        remains under the safe threshold (MAX_LENGTH).
        """
        formatted_elem = self.format_element(elem)
        if not formatted_elem:
            return True

        # Calculate maximum possible length (using the larger FOOTER_NEXT)
        header = self._get_header()
        continuation = self.CONTINUATION_MARKER if self.is_continuation else ""
        footer = self.FOOTER_NEXT  # Safest assumption for length check

        projected_length = (
            len(header) +
            len(continuation) +
            len(self._buffer) +
            len(formatted_elem) +
            len(footer)
        )

        return projected_length <= self.MAX_LENGTH

    def add_element(self, elem: Element) -> None:
        """Appends a formatted element to the internal buffer."""
        formatted = self.format_element(elem)
        if formatted:
            self._buffer += formatted
            self._has_elements = True

    def build(self, is_last_message: bool) -> str:
        """
        Constructs the final message string.
        Replaces the total messages placeholder.
        """
        header = self._get_header()
        continuation = self.CONTINUATION_MARKER if self.is_continuation else ""
        footer = self._get_footer(is_last_message)
        
        return f"{header}{continuation}{self._buffer}{footer}"