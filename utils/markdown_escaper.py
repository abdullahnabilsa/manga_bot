# File: utils/markdown_escaper.py
from __future__ import annotations

import re


def escape_markdown_v2(text: str) -> str:
    """
    Escapes all special characters required by Telegram MarkdownV2 parse mode.
    
    Telegram MarkdownV2 requires escaping the following characters:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Args:
        text: The raw string to be escaped.
        
    Returns:
        The escaped string safe for MarkdownV2 parsing.
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    # Use a raw string for the replacement to ensure single backslash
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)