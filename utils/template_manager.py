# File: utils/template_manager.py
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from utils.markdown_escaper import escape_markdown_v2

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Zero-dependency dynamic template manager.
    Uses [[ variable ]] for raw text and [[escape variable]] for MarkdownV2 safe text.
    """

    def __init__(self, templates_dir: str = "templates") -> None:
        self._templates_dir = templates_dir
        self._templates: Dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """Safely reloads templates from the filesystem."""
        self._templates.clear()
        if not os.path.exists(self._templates_dir):
            os.makedirs(self._templates_dir)
            self._create_default_templates()

        for filename in os.listdir(self._templates_dir):
            if filename.endswith(".j2"):
                filepath = os.path.join(self._templates_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        self._templates[filename] = f.read()
                except Exception as e:
                    logger.error(f"Failed to read template {filename}: {e}")
                    
        logger.info(f"TemplateManager loaded {len(self._templates)} templates.")

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Renders a template using the provided context."""
        template_str = self._templates.get(template_name)
        if template_str is None:
            logger.error(f"Template '{template_name}' not found.")
            return f"[⚠️ System Error: Template '{template_name}' is missing.]"

        try:
            rendered = template_str

            # 1. Process IF blocks: [[if var]] ... [[/if]]
            def replace_if(match: re.Match) -> str:
                var_name = match.group(1)
                content = match.group(2)
                val = context.get(var_name)
                if val is not None and str(val).strip() != "":
                    return content
                return ""

            pattern_if = r"\[\[if\s+([a-zA-Z_0-9]+)\]\](.*?)\[\[/if\]\]"
            rendered = re.sub(pattern_if, replace_if, rendered, flags=re.DOTALL)

            # 2. Replace variables: [[escape var]] or [[ var ]]
            def replace_var(match: re.Match) -> str:
                is_escape = match.group(1) is not None
                var_name = match.group(2)
                val = context.get(var_name)
                
                if val is None or str(val).strip() == "":
                    return ""
                
                str_val = str(val)
                if is_escape:
                    # Flatten newlines to prevent breaking inline code blocks
                    str_val = str_val.replace('\n', ' ')
                    return escape_markdown_v2(str_val)
                return str_val

            # Matches [[escape var]] or [[ var ]]
            pattern_var = r"\[\[\s*(escape\s+)?([a-zA-Z_0-9]+)\s*\]\]"
            rendered = re.sub(pattern_var, replace_var, rendered)

            # 3. Clean up excessive empty lines
            rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()
            return rendered

        except Exception as e:
            logger.error(f"Unexpected error rendering '{template_name}': {e}")
            return f"[⚠️ System Error: Failed to render '{template_name}'.]"

    def _create_default_templates(self) -> None:
        """Generates the professional design templates."""
        defaults = {
            "page_header.j2": (
                "• ━━━━━━━━━━━━━━━━━━━━━━━━━━ •\n"
                "📖 ترجمة المانهوا\n"
                "الصفحة: [[ page_num ]] | الرسالة: [[ msg_num ]] من [[ TOTAL_MSGS ]]\n"
                "• ━━━━━━━━━━━━━━━━━━━━━━━━━━ •\n\n"
                "[[if is_continuation]]\n• ━ ━ ━ ━ ━ ━ ━ ━ •\n(تتمة المشهد السابق)\n• ━ ━ ━ ━ ━ ━ ━ ━ •\n\n[[/if]]"
            ),
            "scene_header.j2": (
                "━━━━ ✨ *Scene [[ scene_number ]]* ✨ ━━━━\n"
                "[[if environment]]_[[escape environment]]_[[/if]]\n"
            ),
            "scene_continued.j2": (
                "━━━━ ✨ *Scene [[ scene_number ]]* (متابعة) ✨ ━━━━\n"
            ),
            "element.j2": (
                "• ━ ━ ━ ━ ━ ━ ━ ━ •\n"
                "🧩 *العنصر [[ element_number ]] ([[escape type]])*\n"
                "[[if speaker]]🗣 *المتحدث:* [[escape speaker]][[/if]]\n"
                "[[if original]]\n• ━ ━ ━ •\n🇬🇧 *النص الأصلي*\n> `[[escape original]]`[[/if]]\n"
                "[[if translation]]\n• ━ ━ ━ •\n🇸🇦 *الترجمة العربية*\n> `[[escape translation]]`[[/if]]\n"
                "[[if alternative]]\n• ━ ━ ━ •\n🔄 *ترجمة أخرى*\n> `[[escape alternative]]`[[/if]]\n"
                "[[if reason]]\n• ━ ━ ━ •\n💡 *شرح الترجمة*\n[[escape reason]][[/if]]\n"
            ),
            "page_footer_next.j2": (
                "\n\n• ━━━━━━━━━━━━━━━━━━━━━━━━━━ •\n"
                "⏳ انتهى الجزء \\(يتبع\\.\\.\\.\\)"
            ),
            "page_footer_end.j2": (
                "\n\n• ━━━━━━━━━━━━━━━━━━━━━━━━━━ •\n"
                "✅ اكتملت ترجمة الصفحة\\."
            )
        }
        
        for filename, content in defaults.items():
            filepath = os.path.join(self._templates_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)