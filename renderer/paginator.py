# File: renderer/paginator.py
from __future__ import annotations

import logging
from typing import List

from models.page_job import PageJob
from renderer.message_builder import MessageBuilder

logger = logging.getLogger(__name__)

class Paginator:
    async def paginate(self, job: PageJob, page_num: int = 1) -> List[str]:
        if not job.page_data or not job.page_data.scenes:
            builder = MessageBuilder(page_num=page_num, msg_num=1, is_continuation=False)
            return [builder.build(is_last_message=True).replace("{TOTAL_MSGS}", "1")]

        scenes = job.page_data.scenes
        messages: List[str] = []
        current_builder = MessageBuilder(page_num=page_num, msg_num=1, is_continuation=False)

        for scene in scenes:
            # Try to add scene header
            if not current_builder.can_fit_scene_header(scene):
                messages.append(current_builder.build(is_last_message=False))
                current_builder = MessageBuilder(page_num=page_num, msg_num=len(messages)+1, is_continuation=True)
            
            # We buffer the scene header until we add the first element, 
            # to avoid empty scene headers at the end of a message
            current_builder._current_scene_header = current_builder.format_scene_header(scene)

            for elem in scene.elements:
                if current_builder.can_fit_element(elem):
                    current_builder.add_element(elem)
                else:
                    # Element doesn't fit, finalize current message
                    messages.append(current_builder.build(is_last_message=False))
                    # Start new message
                    current_builder = MessageBuilder(page_num=page_num, msg_num=len(messages)+1, is_continuation=True)
                    # Re-add the scene header as continuation context
                    current_builder._current_scene_header = f"🎬 المشهد {scene.scene_number} (متابعة)\n\n"
                    current_builder.add_element(elem)

        # Append final message
        messages.append(current_builder.build(is_last_message=True))

        total_msgs = str(len(messages))
        return [msg.replace("{TOTAL_MSGS}", total_msgs) for msg in messages]