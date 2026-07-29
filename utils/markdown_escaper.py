# File: utils/markdown_escaper.py
from __future__ import annotations

import re
from typing import Optional

def escape_markdown_v2(text: Optional[str]) -> str:
    """
    Escapes all special characters required by Telegram MarkdownV2 parse mode.
    Safely handles None values by returning an empty string.
    """
    if not text or not isinstance(text, str):
        return ""
    
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitizes a string to be a safe filename.
    Removes illegal characters and limits length.
    """
    if not filename or not isinstance(filename, str):
        return "manga_translation"
    
    # إزالة أي امتدادات ملفات قد أدخلها المستخدم بالخطأ
    name = re.sub(r'\.(txt|docx|pdf)$', '', filename, flags=re.IGNORECASE)
    
    # إزالة الرموز غير المسموحة في أنظمة الملفات
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    
    # منع الأسماء الفارغة بعد التنظيف
    if not name:
        return "manga_translation"
        
    # تحديد الطول الأقصى لاسم الملف لتجنب مشاكل المسارات
    return name[:50]