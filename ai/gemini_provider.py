# File: ai/gemini_provider.py
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp

from ai.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Concrete AI provider for Google Gemini API.
    Implements a 5-model fallback mechanism.
    Accepts a dynamic prompt (persona) for each request.
    """

    FALLBACK_MODELS: List[str] = [
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-1.0-pro-vision-latest",
        "gemini-pro-vision",
        "gemini-1.0-pro",
    ]

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._timeout = aiohttp.ClientTimeout(total=60.0)

    async def extract_raw_json(
        self,
        image_bytes: bytes,
        job_id: UUID,
        prompt_text: str  # Now accepts dynamic prompt
    ) -> Dict[str, Any]:
        """
        Attempts to extract JSON from the image using the 5-model fallback chain.
        Raises RuntimeError if all models fail.
        """
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = self._build_payload(b64_image, prompt_text)

        last_exception: Optional[Exception] = None

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            for model_name in self.FALLBACK_MODELS:
                try:
                    logger.info(f"JobID={job_id} | Attempting AI extraction with model: {model_name}")
                    result = await self._call_model(session, model_name, payload, job_id)
                    logger.info(f"JobID={job_id} | Success with model: {model_name}")
                    return result
                except Exception as e:
                    logger.warning(
                        f"JobID={job_id} | Model {model_name} failed: {type(e).__name__} - {str(e)}"
                    )
                    last_exception = e

        raise RuntimeError(
            f"All 5 Gemini models failed for JobID={job_id}. Last error: {str(last_exception)}"
        )

    def _build_payload(self, b64_image: str, prompt_text: str) -> Dict[str, Any]:
        """Constructs the request payload for the Gemini API using the provided prompt."""
        return {
            "contents": [
                {
                    "parts": [
                        {"text": "Extract all text elements in Arabic reading order (Top-to-Bottom, Right-to-Left)."},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image,
                            }
                        }
                    ]
                }
            ],
            "system_instruction": {
                "parts": [
                    {"text": prompt_text}  # Dynamic Persona Prompt
                ]
            },
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

    async def _call_model(
        self,
        session: aiohttp.ClientSession,
        model_name: str,
        payload: Dict[str, Any],
        job_id: UUID
    ) -> Dict[str, Any]:
        """Executes the HTTP request to a specific Gemini model and parses JSON."""
        url = f"{self._base_url}/{model_name}:generateContent?key={self._api_key}"

        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"HTTP {response.status}: {error_text}")

            data = await response.json()

            try:
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError("No candidates returned in response.")

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    raise ValueError("No parts found in response content.")

                raw_text = parts[0].get("text", "{}")
                return json.loads(raw_text)

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                raise ValueError(f"Failed to parse JSON response from {model_name}: {str(e)}") from e