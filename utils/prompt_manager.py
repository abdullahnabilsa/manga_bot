# File: utils/prompt_manager.py
from __future__ import annotations

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

class PromptManager:
    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._prompts_dir = prompts_dir
        self._prompts: Dict[str, str] = {}
        self.load_prompts()

    def load_prompts(self) -> None:
        self._prompts.clear()
        if not os.path.exists(self._prompts_dir):
            os.makedirs(self._prompts_dir)
            self._create_default_prompts()

        for filename in os.listdir(self._prompts_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(self._prompts_dir, filename)
                display_name = filename.replace(".txt", "").replace("_", " ").title()
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._prompts[display_name] = content
                        
        logger.info(f"PromptManager loaded {len(self._prompts)} personas.")

    def _create_default_prompts(self) -> None:
        default_content = (
            "You are an expert manga and manhwa translator. "
            "Analyze the provided image and extract text elements following the Arabic reading order strictly (Top-to-Bottom, then Right-to-Left). "
            "Group elements into logical 'scenes'. "
            "You MUST return a valid JSON object matching this exact schema: "
            "{"
            '"metadata": {"model": "string", "page": 1, "total_pages": 1, "scene_count": "integer"}, '
            '"scenes": ['
            '{"scene_number": "integer", "environment": "string|null", "elements": ['
            '{"element_number": "integer", "type": "speech_bubble|sfx|narration", "speaker": "string|null", '
            '"original": "string|null", "translation": "string|null", "alternative": "string|null", "reason": "string|null"}'
            "]}]}. "
            "Do not include any markdown, code blocks, or conversational text. Output JSON only."
        )
        with open(os.path.join(self._prompts_dir, "default_translator.txt"), "w", encoding="utf-8") as f:
            f.write(default_content)

    def get_available_personas(self) -> List[str]:
        return list(self._prompts.keys())

    def get_prompt(self, persona_name: str) -> str:
        return self._prompts.get(persona_name, self._prompts.get("Default Translator", ""))