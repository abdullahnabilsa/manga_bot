# File: renderer/paginator.py
from __future__ import annotations

import logging
from typing import List

from models.page_job import PageJob
from renderer.message_builder import MessageBuilder

logger = logging.getLogger(__name__)


class Paginator:
    """
    Algorithmically splits a PageJob's elements into multiple message chunks.
    Enforces rules:
    1. Never split a single Element across two messages.
    2. Start next element in a new message if current is full.
    3. Keep small scenes intact if possible.
    4. Inject 'Scene X (Continued)' when a scene is split.
    """

    async def paginate(self, job: PageJob, page_num: int = 1) -> List[str]:
        """
        Processes the PageJob scene and returns a list of ready-to-send strings.
        
        Args:
            job: The PageJob containing the validated Scene.
            page_num: The logical page number for header context.
            
        Returns:
            A list of formatted strings, each representing a Telegram message.
        """
        if not job.scene or not job.scene.elements:
            logger.info(f"JobID={job.job_id} | No elements to paginate.")
            builder = MessageBuilder(page_num=page_num, msg_num=1, is_continuation=False)
            return [builder.build(is_last_message=True).replace("{TOTAL_MSGS}", "1")]

        elements = job.scene.elements
        messages: List[str] = []
        current_builder: MessageBuilder = MessageBuilder(
            page_num=page_num,
            msg_num=1,
            is_continuation=False
        )

        for elem in elements:
            if current_builder.can_fit(elem):
                current_builder.add_element(elem)
            else:
                # Rule 1 & 2: Message is full, finalize current and start new
                messages.append(current_builder.build(is_last_message=False))
                
                # Start new message. Since it's the same scene, mark as continuation.
                # Rule 4: Inject continuation marker.
                current_builder = MessageBuilder(
                    page_num=page_num,
                    msg_num=len(messages) + 1,
                    is_continuation=True
                )
                
                # Add the element that didn't fit to the new buffer.
                # (Assuming a single element never exceeds MAX_LENGTH alone.
                # If it does, it still must not be split, so we add it anyway).
                current_builder.add_element(elem)

        # Append the final accumulated message
        messages.append(current_builder.build(is_last_message=True))

        # Post-processing: Replace total messages placeholder
        total_msgs = str(len(messages))
        final_messages = [
            msg.replace("{TOTAL_MSGS}", total_msgs) for msg in messages
        ]

        logger.info(
            f"JobID={job.job_id} | Pagination complete. "
            f"Split into {total_msgs} messages."
        )
        
        return final_messages