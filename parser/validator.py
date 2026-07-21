# File: parser/validator.py
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from pydantic import ValidationError

from models.element import Element
from models.page_job import PageJob
from models.scene import Scene

logger = logging.getLogger(__name__)

# Explicit allowed keys (lowercase) to map to Pydantic Element schema
ALLOWED_ELEMENT_KEYS = {
    "environment", "speaker", "original", "translation", "alternative", "reason"
}


class Validator:
    """
    Validates raw AI JSON output against Pydantic schemas.
    Automatically fills missing required fields with `null` instead of crashing.
    Removes unexpected keys to comply with `extra='forbid'` in the schema.
    """

    async def validate_and_update_job(
        self,
        job: PageJob,
        raw_json: Dict[str, Any]
    ) -> PageJob:
        """
        Processes raw JSON, sanitizes elements, constructs a Scene, 
        and attaches it to the PageJob.
        """
        job_id = job.job_id
        logger.info(f"JobID={job_id} | Starting JSON validation")

        try:
            # Extract elements list, default to empty if missing
            elements_data = raw_json.get("elements", [])
            if not isinstance(elements_data, list):
                elements_data = []

            sanitized_elements: List[Element] = []
            
            for idx, raw_elem in enumerate(elements_data):
                try:
                    # Sanitize each element dictionary
                    clean_dict = self._sanitize_element(raw_elem, idx, job_id)
                    
                    # Pydantic will fill missing fields with `None` (null) based on schema defaults
                    element = Element(**clean_dict)
                    sanitized_elements.append(element)
                    
                except ValidationError as ve:
                    logger.warning(
                        f"JobID={job_id} | Element {idx} failed validation: {ve.errors()}. Skipping."
                    )
                    # Even on validation failure of a specific field constraint, we attempt to salvage
                    # by forcing nulls on the problematic fields.
                    salvaged = self._salvage_element(clean_dict, ve)
                    if salvaged:
                        sanitized_elements.append(salvaged)

            # Create the scene with the sanitized elements
            scene = Scene(elements=sanitized_elements)
            job.scene = scene
            
            logger.info(
                f"JobID={job_id} | Validation successful. "
                f"Elements attached: {len(scene.elements)}"
            )
            return job

        except Exception as e:
            logger.error(f"JobID={job_id} | Critical validation failure: {str(e)}", exc_info=True)
            # Attach an empty scene rather than crashing the pipeline
            job.scene = Scene(elements=[])
            return job

    def _sanitize_element(self, raw_elem: Any, idx: int, job_id: UUID) -> Dict[str, Any]:
        """Cleans a raw element dictionary: lowercases keys, filters unknowns."""
        if not isinstance(raw_elem, dict):
            logger.warning(f"JobID={job_id} | Element {idx} is not a dict. Converting to empty dict.")
            return {}

        clean_dict: Dict[str, Any] = {}
        for key, value in raw_elem.items():
            lower_key = key.lower()
            if lower_key in ALLOWED_ELEMENT_KEYS:
                # Ensure None is passed if the value is literally an empty string or missing
                clean_dict[lower_key] = value if value != "" else None
            else:
                logger.debug(f"JobID={job_id} | Element {idx} dropping unknown key: {key}")

        return clean_dict

    def _salvage_element(self, clean_dict: Dict[str, Any], ve: ValidationError) -> Element:
        """Forces fields that caused validation errors to None to prevent pipeline crashes."""
        salvage_dict = clean_dict.copy()
        for error in ve.errors():
            loc = error.get("loc", [])
            if loc and isinstance(loc, tuple) and len(loc) > 0:
                field = loc[0]
                if field in ALLOWED_ELEMENT_KEYS:
                    salvage_dict[field] = None
        
        try:
            return Element(**salvage_dict)
        except Exception:
            # Ultimate fallback if it still fails
            return Element()