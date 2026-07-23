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
    """
    Independent rendering component responsible for sending paginated strings
    to Telegram as professional MarkdownV2 cards.
    Enforces a strict 300ms rate limit between sends and handles state updates.
    """

    SEND_DELAY_SECONDS = 0.3

    async def render_messages(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        job: PageJob,
        messages: List[str]
    ) -> None:
        """
        Takes a list of pre-formatted MarkdownV2 strings and sends them sequentially.
        """
        if not messages:
            logger.warning(f"JobID={job.job_id} | No messages to render.")
            job.state = JobState.FINISHED
            return

        # Update state to SENDING upon start
        job.state = JobState.SENDING
        logger.info(f"JobID={job.job_id} | State transitioned to SENDING.")

        total_messages = len(messages)
        
        for i, raw_text in enumerate(messages, start=1):
            try:
                # Send the message exactly as formatted by MessageBuilder
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text=raw_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True  # Enforced by Spec
                )
                logger.info(
                    f"JobID={job.job_id} | Successfully sent message {i}/{total_messages}."
                )
                
                # Apply Rate Limiter (300ms) if not the last message
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)
                    
            except Exception as e:
                # Strict Error Handling: Log and attempt to send the next one
                logger.error(
                    f"JobID={job.job_id} | Failed to send message {i}/{total_messages}: {str(e)}",
                    exc_info=True
                )
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)

        # Update state to FINISHED upon completion
        job.state = JobState.FINISHED
        logger.info(f"JobID={job.job_id} | State transitioned to FINISHED.")