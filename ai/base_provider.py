# File: ai/base_provider.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.
    Enforces strict asynchronous JSON extraction from manga page images.
    """

    @abstractmethod
    async def extract_raw_json(
        self,
        image_bytes: bytes,
        job_id: UUID
    ) -> Dict[str, Any]:
        """
        Send the image to the AI provider and return strictly parsed JSON.
        
        Args:
            image_bytes: Raw bytes of the manga/manhwa page image.
            job_id: The unique identifier of the current processing job.
            
        Returns:
            A dictionary containing the structured AI response.
            
        Raises:
            ValueError: If the response cannot be parsed as JSON.
            RuntimeError: If the provider fails after all fallback attempts.
        """
        pass