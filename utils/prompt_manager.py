# File: utils/prompt_manager.py
from __future__ import annotations

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Dynamically loads and manages prompt files (.txt) from the 'prompts' directory.
    The filename (without extension) becomes the persona name, with underscores replaced by spaces.
    """

    def __init__(self, prompts_dir: str = "prompts") -> None:
        self._prompts_dir = prompts_dir
        self._prompts: Dict[str, str] = {}
        self.load_prompts()

    def load_prompts(self) -> None:
        """Scans the directory and loads all .txt files into memory."""
        self._prompts.clear()
        
        # Ensure directory exists
        if not os.path.exists(self._prompts_dir):
            os.makedirs(self._prompts_dir)
            self._create_default_prompts()

        for filename in os.listdir(self._prompts_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(self._prompts_dir, filename)
                
                # Convert filename to display name (e.g., "english_translator.txt" -> "English Translator")
                display_name = filename.replace(".txt", "").replace("_", " ").title()
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._prompts[display_name] = content
                        
        logger.info(f"PromptManager loaded {len(self._prompts)} personas: {list(self._prompts.keys())}")

    def _create_default_prompts(self) -> None:
        """Creates a default prompt file if none exist."""
        default_content = (
            "You are an expert manga and manhwa translator. "
            "Analyze the provided image and extract text elements following the "
            "Arabic reading order strictly (Top-to-Bottom, then Right-to-Left). "
            "You MUST return a valid JSON object matching this exact schema: "
            '{"elements": [{"environment": str|null, "speaker": str|null, "original": str|null, '
            '"translation": str|null, "alternative": str|null, "reason": str|null}]}. '
            "Do not include any markdown, code blocks, or conversational text. Output JSON only."
        )
        with open(os.path.join(self._prompts_dir, "default_translator.txt"), "w", encoding="utf-8") as f:
            f.write(default_content)

    def get_available_personas(self) -> List[str]:
        """Returns a list of available persona display names."""
        return list(self._prompts.keys())

    def get_prompt(self, persona_name: str) -> str:
        """Returns the prompt text for a specific persona. Falls back to default."""
        return self._prompts.get(persona_name, self._prompts.get("Default Translator", ""))