# File: utils/template_manager.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Manages dynamic message formatting via Jinja2 templates.
    Allows changing the design without touching the Python code.
    """

    def __init__(self, templates_dir: str = "templates") -> None:
        self._templates_dir = templates_dir
        self._env: Environment
        self.reload()

    def reload(self) -> None:
        """Reloads templates from the filesystem safely."""
        if not os.path.exists(self._templates_dir):
            os.makedirs(self._templates_dir)
            self._create_default_templates()

        self._env = Environment(
            loader=FileSystemLoader(self._templates_dir),
            trim_blocks=True,      # Removes newline after block tags
            lstrip_blocks=True,    # Strips whitespace before block tags
            autoescape=False       # We are generating plain text, not HTML
        )
        logger.info(f"TemplateManager loaded templates from {self._templates_dir}")

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Renders a specific template with context, handling errors gracefully."""
        try:
            # Sanitize None values to empty strings to avoid Jinja2 printing "None"
            clean_context = {k: (v if v is not None else "") for k, v in context.items()}
            template = self._env.get_template(template_name)
            return template.render(**clean_context)
        except TemplateNotFound:
            logger.error(f"Template '{template_name}' not found in {self._templates_dir}.")
            return f"[⚠️ System Error: Template '{template_name}' is missing.]"
        except TemplateSyntaxError as e:
            logger.error(f"Syntax error in template '{template_name}': {e}")
            return f"[⚠️ System Error: Template '{template_name}' has a syntax error.]"
        except Exception as e:
            logger.error(f"Unexpected error rendering '{template_name}': {e}")
            return f"[⚠️ System Error: Failed to render '{template_name}'.]"

    def _create_default_templates(self) -> None:
        """Generates default template files if they don't exist."""
        defaults = {
            "page_header.j2": (
                "📖 ترجمة المانهوا\n"
                "الصفحة: {{ page_num }}\n"
                "الرسالة: {{ msg_num }} من {{ TOTAL_MSGS }}\n"
                "━━━━━━━━━━━━━━━\n"
                "{% if is_continuation %}Scene (Continued)\n\n{% endif %}"
            ),
            "scene_header.j2": (
                "{% if scene_number %}🎬 المشهد {{ scene_number }}\n{% endif %}"
                "{% if environment %}🌍 {{ environment }}\n{% endif %}"
            ),
            "scene_continued.j2": (
                "🎬 المشهد {{ scene_number }} (متابعة)\n\n"
            ),
            "element.j2": (
                "{% if speaker %}🗣️ {{ speaker }}\n{% endif %}"
                "{% if original %}🇯🇵 {{ original }}\n{% endif %}"
                "{% if translation %}🇸🇦 {{ translation }}\n{% endif %}"
                "{% if alternative %}💬 {{ alternative }}\n{% endif %}"
                "{% if reason %}ℹ️ {{ reason }}\n{% endif %}"
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