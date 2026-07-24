# File: renderer/paginator.py
from __future__ import annotations

import logging
from typing import List

from models.page_job import PageJob
from renderer.message_builder import MessageBuilder
from utils.template_manager import TemplateManager

logger = logging.getLogger(__name__)

class Paginator:
    def __init__(self, template_manager: TemplateManager) -> None:
        self._tm = template_manager

    async def paginate(self, job: PageJob, page_num: int = 1) -> List[str]:
        if not job.page_data or not job.page_data.scenes:
            builder = MessageBuilder(self._tm, page_num=page_num, msg_num=1, is_continuation=False)
            return [builder.build(is_last_message=True).replace("{TOTAL_MSGS}", "1")]

        scenes = job.page_data.scenes
        messages: List[str] = []
        current_builder = MessageBuilder(self._tm, page_num=page_num, msg_num=1, is_continuation=False)

        for scene in scenes:
            if not current_builder.can_fit_scene_header(scene):
                messages.append(current_builder.build(is_last_message=False))
                current_builder = MessageBuilder(self._tm, page_num=page_num, msg_num=len(messages)+1, is_continuation=True)
            
            current_builder._current_scene_header = current_builder.format_scene_header(scene)

            for elem in scene.elements:
                if current_builder.can_fit_element(elem):
                    current_builder.add_element(elem)
                else:
                    messages.append(current_builder.build(is_last_message=False))
                    current_builder = MessageBuilder(self._tm, page_num=page_num, msg_num=len(messages)+1, is_continuation=True)
                    
                    # 🆕 استخدام قالب ديناميكي لرأس المشهد المقطوع
                    current_builder._current_scene_header = self._tm.render_template(
                        "scene_continued.j2",
                        {"scene_number": scene.scene_number}
                    )
                    current_builder.add_element(elem)

        messages.append(current_builder.build(is_last_message=True))

        total_msgs = str(len(messages))
        return [msg.replace("{TOTAL_MSGS}", total_msgs) for msg in messages]