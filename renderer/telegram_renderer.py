# File: renderer/telegram_renderer.py
from __future__ import annotations

import asyncio
import logging
from typing import List

from telegram.constants import ParseMode
from telegram.error import BadRequest

from models.page_job import JobState, PageJob

logger = logging.getLogger(__name__)


class TelegramRenderer:
    """
    Sends pre-formatted MarkdownV2 strings to Telegram.
    Includes a Fallback mechanism to Plain Text if Markdown parsing fails.
    """

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
        
        for i, text in enumerate(messages, start=1):
            try:
                # 1. Try sending as MarkdownV2 (Primary)
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True
                )
            except BadRequest as e:
                logger.error(f"JobID={job.job_id} | MarkdownV2 failed for msg {i}/{total_messages}: {e}")
                try:
                    # 2. Fallback: Send as Plain Text (Emergency)
                    await context.bot.send_message(
                        chat_id=job.chat_id,
                        text=text,
                        parse_mode=None,
                        disable_web_page_preview=True
                    )
                    logger.info(f"JobID={job.job_id} | Recovered msg {i} via Plain Text fallback.")
                except Exception as fallback_e:
                    logger.critical(f"JobID={job.job_id} | Completely failed to send msg {i}: {fallback_e}")
            
            except Exception as e:
                logger.error(f"JobID={job.job_id} | Unexpected error sending msg {i}: {e}")

            # Apply Rate Limiter (300ms)
            if i < total_messages:
                await asyncio.sleep(self.SEND_DELAY_SECONDS)

        job.state = JobState.FINISHED