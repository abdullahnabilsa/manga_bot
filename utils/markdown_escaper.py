# File: utils/markdown_escaper.py
import re


def escape_markdown_v2(text: str) -> str:
    """
    Escapes all special characters required by Telegram MarkdownV2 parse mode.
    Used for normal text outside of code blocks.
    """
    if not text:
        return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))


def escape_code(text: str) -> str:
    """
    Escapes ONLY backslash and backtick for text inside inline code or code blocks.
    Prevents breaking code blocks while keeping content readable.
    """
    if not text:
        return ""
    return str(text).replace("\\", "\\\\").replace("`", "\\`")