# File: core/senders/direct_sender.py
from __future__ import annotations
import asyncio
import logging

from telegram import InputFile
from telegram.constants import ParseMode
from telegram.error import RetryAfter

from utils.markdown_escaper import escape_markdown_v2
from models.page_job import PageJob

logger = logging.getLogger("manga_bot.direct_sender")

class DirectSender:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.bot = pipeline.bot
        self.telegram_renderer = pipeline.telegram_renderer
        self.bot_context = pipeline.bot_context
        self.concurrency_manager = pipeline.concurrency_manager  # <--- جديد

    async def process(self, job: PageJob, handler) -> PageJob:
        user_settings = await self.pipeline.settings_manager.get_user_settings(job.user_id)
        output_method = user_settings.get("output_method", "files_only")
        if output_method == "chat_and_files": output_method = "messages_and_files"
        fmt = user_settings.get("file_format", "docx")

        if output_method in ["messages_only", "messages_and_files"]:
            strings = [p.text for p in job.message_payloads]
            await self.telegram_renderer.render_messages(self.bot_context, job, strings)
        
        if output_method in ["files_only", "messages_and_files"]:
            file_io_txt = None
            file_io_docx = None
            base_filename = job.file_name.split('.')[0] if job.file_name else "translation"
            
            try:
                if fmt in ["txt", "both"]:
                    file_io_txt = await asyncio.to_thread(handler.generate_txt, [job.page_data])
                if fmt in ["docx", "both"]:
                    file_io_docx = await asyncio.to_thread(handler.generate_docx, [job.page_data])
                    
                caption_text = f"📄 ترجمة: {escape_markdown_v2(job.file_name)}"
                
                # --- CONCURRENCY CONTROL: Prevent Telegram Rate Limits ---
                await self.concurrency_manager.acquire_chat_send_lock(job.chat_id)
                try:
                    if file_io_txt:
                        await self.bot.send_document(
                            chat_id=job.chat_id, document=InputFile(file_io_txt, filename=f"{base_filename}_translation.txt"),
                            caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id
                        )
                        await asyncio.sleep(0.3)
                    if file_io_docx:
                        await self.bot.send_document(
                            chat_id=job.chat_id, document=InputFile(file_io_docx, filename=f"{base_filename}_translation.docx"),
                            caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id
                        )
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    if file_io_txt:
                        file_io_txt.seek(0)
                        await self.bot.send_document(chat_id=job.chat_id, document=InputFile(file_io_txt, filename=f"{base_filename}_translation.txt"), caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id)
                    if file_io_docx:
                        file_io_docx.seek(0)
                        await self.bot.send_document(chat_id=job.chat_id, document=InputFile(file_io_docx, filename=f"{base_filename}_translation.docx"), caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id)
                finally:
                    await self.concurrency_manager.release_chat_send_lock(job.chat_id)
                # -----------------------------------------------------------
                    
            except Exception as e:
                logger.error(f"Failed to generate or send document: {e}")
                text = f"❌ *فشل الإرسال\\.*\n🖼️ الملف: `{escape_markdown_v2(job.file_name)}`\nتعذر إرسال الملف\\. حاول مرة أخرى\\."
                await self.pipeline.safe_edit_or_send(job, text)
                return job 
                
        queue_size = await self.pipeline.queue_manager.size()
        if queue_size == 0:
            await self.pipeline.safe_delete_message(job)
            
        return job