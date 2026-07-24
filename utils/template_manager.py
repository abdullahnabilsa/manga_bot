
# File: utils/template_manager.py
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Zero-dependency dynamic template manager.
    Uses built-in regex to render templates with [[ variable ]] and [[if variable]] syntax.
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
                    
        logger.info(f"TemplateManager loaded {len(self._templates)} templates (Built-in Engine).")

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
                
                # Render content only if value exists and is not empty
                if val is not None and str(val).strip() != "":
                    return content
                return ""

            pattern_if = r"\[\[if\s+([a-zA-Z_0-9]+)\]\](.*?)\[\[/if\]\]"
            rendered = re.sub(pattern_if, replace_if, rendered, flags=re.DOTALL)

            # 2. Replace variables: [[ var ]]
            def replace_var(match: re.Match) -> str:
                var_name = match.group(1)
                val = context.get(var_name)
                return str(val) if val is not None and str(val).strip() != "" else ""

            pattern_var = r"\[\[\s*([a-zA-Z_0-9]+)\s*\]\]"
            rendered = re.sub(pattern_var, replace_var, rendered)

            # 3. Clean up excessive empty lines (caused by removed variables)
            rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()
            return rendered

        except Exception as e:
            logger.error(f"Unexpected error rendering '{template_name}': {e}")
            return f"[⚠️ System Error: Failed to render '{template_name}'.]"

    def _create_default_templates(self) -> None:
        """Generates default template files if they don't exist."""
        defaults = {
            "page_header.j2": (
                "📖 ترجمة المانهوا\n"
                "الصفحة: [[ page_num ]]\n"
                "الرسالة: [[ msg_num ]] من [[ TOTAL_MSGS ]]\n"
                "━━━━━━━━━━━━━━━\n"
                "[[if is_continuation]]Scene (Continued)\n\n[[/if]]"
            ),
            "scene_header.j2": (
                "[[if scene_number]]🎬 المشهد [[ scene_number ]]\n[[/if]]"
                "[[if environment]]🌍 [[ environment ]]\n[[/if]]"
            ),
            "scene_continued.j2": (
                "🎬 المشهد [[ scene_number ]] (متابعة)\n\n"
            ),
            "element.j2": (
                "[[if speaker]]🗣️ [[ speaker ]]\n[[/if]]"
                "[[if original]]🇯🇵 [[ original ]]\n[[/if]]"
                "[[if translation]]🇸🇦 [[ translation ]]\n[[/if]]"
                "[[if alternative]]💬 [[ alternative ]]\n[[/if]]"
                "[[if reason]]ℹ️ [[ reason ]]\n[[/if]]"
            ),
            "footer_next.j2": (
                "\n\n━━━━━━━━━━━━━━━\nانتهى الجزء\nيتبع..."
            ),
            "footer_end.j2": (
                "\n\n━━━━━━━━━━━━━━━\nاكتملت ترجمة الصفحة."
            )
        }
        
        for filename, content in defaults.items():
            filepath = os.path.join(self._templates_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)