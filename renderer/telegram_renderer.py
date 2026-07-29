# File: renderer/telegram_renderer.py
from __future__ import annotations

import asyncio
import logging
from typing import List

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from models.page_job import JobState, PageJob

logger = logging.getLogger(__name__)


class TelegramRenderer:
    SEND_DELAY_SECONDS = 0.3

    async def render_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        job: PageJob,
        messages: List[str]
    ) -> None:
        if not messages:
            job.state = JobState.FINISHED
            return

        job.state = JobState.SENDING
        total_messages = len(messages)
        
        for i, raw_text in enumerate(messages, start=1):
            try:
                # Send the message directly. 
                # Escaping is already handled safely by SafeElementContext in MessageBuilder.
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text=raw_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True
                )
                
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)
                    
            except Exception as e:
                logger.error(f"JobID={job.job_id} | Failed to send message {i}/{total_messages}: {str(e)}", exc_info=True)
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)

        job.state = JobState.FINISHED