# File: renderer/telegram_renderer.py
from __future__ import annotations

import asyncio
import logging
from typing import List

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from models.page_job import JobState, PageJob
from utils.markdown_escaper import escape_markdown_v2

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
        Takes a list of pre-paginated strings, formats them as MarkdownV2 cards,
        and sends them sequentially to the user's chat.
        
        Args:
            context: The Telegram Context object providing bot API access.
            job: The PageJob object containing chat_id, job_id, and state.
            messages: The list of raw strings to be sent.
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
                # 1. Escape raw text for strict MarkdownV2 parsing
                escaped_text = escape_markdown_v2(raw_text)
                
                # 2. Format as a professional Telegram Card using Blockquote
                # Wrapping the entire message in a blockquote creates a distinct visual card
                card_lines = []
                for line in escaped_text.split("\n"):
                    card_lines.append(f"> {line}" if line else ">")
                card_text = "\n".join(card_lines)
                
                # 3. Send the message
                await context.bot.send_message(
                    chat_id=job.chat_id,
                    text=card_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True
                )
                logger.info(
                    f"JobID={job.job_id} | Successfully sent message {i}/{total_messages}."
                )
                
                # 4. Apply Rate Limiter (300ms) if not the last message
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)
                    
            except Exception as e:
                # Strict Error Handling: Log and attempt to send the next one
                logger.error(
                    f"JobID={job.job_id} | Failed to send message {i}/{total_messages}: {str(e)}",
                    exc_info=True
                )
                # Even if this message failed, wait 300ms before attempting the next
                # to respect rate limits and avoid rapid-fire error loops.
                if i < total_messages:
                    await asyncio.sleep(self.SEND_DELAY_SECONDS)

        # Update state to FINISHED upon completion
        job.state = JobState.FINISHED
        logger.info(f"JobID={job.job_id} | State transitioned to FINISHED.")