# File: core/senders/direct_sender.py
from __future__ import annotations
import asyncio
import logging
from typing import List

from telegram import InputFile
from telegram.constants import ParseMode
from telegram.error import RetryAfter

from utils.markdown_escaper import escape_markdown_v2
from models.page_job import PageJob

logger = logging.getLogger("manga_bot.direct_sender")

class DirectSender:
    """Handles sending translation results immediately without session buffering."""
    
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.bot = pipeline.bot
        self.telegram_renderer = pipeline.telegram_renderer
        self.bot_context = pipeline.bot_context

    async def process(self, job: PageJob, handler) -> PageJob:
        user_settings = await self.pipeline.settings_manager.get_user_settings(job.user_id)
        output_method = user_settings.get("output_method", "files_only")
        if output_method == "chat_and_files": output_method = "messages_and_files"
        
        fmt = user_settings.get("file_format", "docx")

        # 1. إرسال رسائل الشات إذا كان الإخراج يشمل ذلك
        if output_method in ["messages_only", "messages_and_files"]:
            strings = [p.text for p in job.message_payloads]
            await self.telegram_renderer.render_messages(self.bot_context, job, strings)
        
        # 2. توليد وإرسال الملفات إذا كان الإخراج يشمل ذلك
        if output_method in ["files_only", "messages_and_files"]:
            # التسليم الصامت: لا نرسل رسالة "جاري الرفع"، المؤشر الصامت يكفي.
            file_io_txt = handler.generate_txt([job.page_data]) if fmt in ["txt", "both"] else None
            file_io_docx = handler.generate_docx([job.page_data]) if fmt in ["docx", "both"] else None
            
            sent_successfully = True
            caption_text = f"📄 ترجمة: {escape_markdown_v2(job.file_name)}"
            
            try:
                if file_io_txt:
                    await self.bot.send_document(
                        chat_id=job.chat_id, 
                        document=InputFile(file_io_txt, filename=f"{job.file_name.split('.')[0]}_translation.txt"),
                        caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id
                    )
                    await asyncio.sleep(0.3)
                if file_io_docx:
                    await self.bot.send_document(
                        chat_id=job.chat_id, 
                        document=InputFile(file_io_docx, filename=f"{job.file_name.split('.')[0]}_translation.docx"),
                        caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id
                    )
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    if file_io_txt:
                        await self.bot.send_document(chat_id=job.chat_id, document=InputFile(file_io_txt, filename=f"{job.file_name.split('.')[0]}_translation.txt"), caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id)
                    if file_io_docx:
                        await self.bot.send_document(chat_id=job.chat_id, document=InputFile(file_io_docx, filename=f"{job.file_name.split('.')[0]}_translation.docx"), caption=caption_text, parse_mode=ParseMode.MARKDOWN_V2, reply_to_message_id=job.photo_message_id)
                except Exception:
                    sent_successfully = False
            except Exception as e:
                logger.error(f"Failed to send document: {e}")
                sent_successfully = False
                
            if not sent_successfully:
                text = f"❌ *فشل الإرسال\\.*\n🖼️ الملف: `{escape_markdown_v2(job.file_name)}`\nتعذر إرسال الملف\\. حاول مرة أخرى\\."
                await self.pipeline.safe_edit_or_send(job, text)
                return job # الخروج فوراً دون حذف رسالة الخطأ
                
        # Zero-Clutter: حذف رسالة الحالة بعد النجاح فقط إذا كان الطابور فارغاً
        # إذا كان الطابور لا يزال به عناصر، نترك الرسالة ليقوم الـ Pipeline بتعديلها للصورة التالية
        queue_size = await self.pipeline.queue_manager.size()
        if queue_size == 0:
            await self.pipeline.safe_delete_message(job)
            
        return job