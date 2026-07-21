# File: ai/gemini_provider.py
from __future__ import annotations

import asyncio
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
    Implements a multi-model fallback mechanism AND a retry logic for transient errors.
    Accepts a dynamic prompt (persona) for each request.
    """

    # Updated 5-model fallback chain (using latest stable endpoints)
    FALLBACK_MODELS: List[str] = [
        "gemini-1.5-flash-latest",       # Fastest & most stable
        "gemini-1.5-pro-latest",         # Higher quality, fallback
        "gemini-1.5-flash-8b-latest",    # Very lightweight fallback
        "gemini-1.0-pro-vision-latest",  # Older vision model fallback
        "gemini-pro-vision",             # Legacy fallback
    ]

    MAX_RETRIES_PER_MODEL = 2
    RETRY_DELAY_SECONDS = 1.0

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._timeout = aiohttp.ClientTimeout(total=60.0)

    async def extract_raw_json(
        self,
        image_bytes: bytes,
        job_id: UUID,
        prompt_text: str
    ) -> Dict[str, Any]:
        """
        Attempts to extract JSON from the image.
        Tries each model up to MAX_RETRIES_PER_MODEL times before falling back to the next.
        Raises RuntimeError if all models fail.
        """
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = self._build_payload(b64_image, prompt_text)

        last_exception: Optional[Exception] = None

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            for model_name in self.FALLBACK_MODELS:
                for attempt in range(1, self.MAX_RETRIES_PER_MODEL + 1):
                    try:
                        logger.info(f"JobID={job_id} | Model: {model_name} | Attempt {attempt}/{self.MAX_RETRIES_PER_MODEL}")
                        result = await self._call_model(session, model_name, payload, job_id)
                        logger.info(f"JobID={job_id} | Success with model: {model_name}")
                        return result
                    
                    except (asyncio.TimeoutError, RuntimeError) as e:
                        error_str = str(e)
                        # Check if it's a transient error worth retrying (503 Service Unavailable, 429 Rate Limit, or Timeout)
                        is_transient = isinstance(e, asyncio.TimeoutError) or "503" in error_str or "429" in error_str
                        
                        if is_transient and attempt < self.MAX_RETRIES_PER_MODEL:
                            logger.warning(
                                f"JobID={job_id} | Transient error on {model_name}. "
                                f"Retrying in {self.RETRY_DELAY_SECONDS}s... Error: {error_str}"
                            )
                            await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                            continue
                        else:
                            # Non-transient error (like 400/404) or out of retries
                            logger.warning(f"JobID={job_id} | Model {model_name} failed permanently: {error_str}")
                            last_exception = e
                            break  # Break inner loop, move to next model
                            
                    except Exception as e:
                        # Catch-all for unexpected parsing/value errors
                        logger.warning(f"JobID={job_id} | Unexpected error on {model_name}: {str(e)}")
                        last_exception = e
                        break

        raise RuntimeError(
            f"All Gemini models failed for JobID={job_id}. Last error: {str(last_exception)}"
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
                    {"text": prompt_text}
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

            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
                raise ValueError(f"Failed to parse JSON response from {model_name}: {str(e)}") from e