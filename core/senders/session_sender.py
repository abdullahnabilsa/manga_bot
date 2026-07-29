# File: core/senders/session_sender.py
from __future__ import annotations
import asyncio
import logging

from telegram import InputFile
from telegram.constants import ParseMode
from telegram.error import RetryAfter, BadRequest

from utils.markdown_escaper import escape_markdown_v2
from models.page_job import PageJob

logger = logging.getLogger("manga_bot.session_sender")

class SessionSender:
    """Handles buffering pages and triggering deferred compilation with advanced UX tracking."""
    
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.bot = pipeline.bot
        self.batch_manager = pipeline.batch_manager
        self.settings_manager = pipeline.settings_manager

    async def process(self, job: PageJob, handler) -> PageJob:
        total_pages = await self.batch_manager.add_page_data(job.user_id, job.page_data)
        logger.info(f"JobID={job.job_id} | Added to session buffer. Total pages: {total_pages}")
        
        is_pending = await self.batch_manager.is_pending_compile(job.user_id)
        queue_size = await self.pipeline.queue_manager.size()
        
        await self._update_session_tracker(job, total_pages, queue_size, is_pending)
        
        # إذا كان التجميع مؤجلاً والطابور أصبح فارغاً، نبدأ التجميع النهائي
        if is_pending and queue_size == 0:
            logger.info(f"JobID={job.job_id} | Queue empty, triggering deferred compile.")
            await self.compile_and_send(job.user_id, job.chat_id)
            
        return job

    async def _update_session_tracker(self, job: PageJob, total_pages: int, queue_size: int, is_pending: bool) -> None:
        tracker_id = await self.batch_manager.get_tracker(job.user_id)
        session_data = await self.batch_manager.get_session_data(job.user_id)
        
        file_names = [escape_markdown_v2(pd.file_name) for pd in session_data if pd.file_name]
        
        if len(file_names) > 10:
            files_text = "_... عرض آخر 5 صور_\n" + "\n".join([f"{i+1}\\. `{name}`" for i, name in enumerate(file_names[-5:])])
        else:
            files_text = "\n".join([f"{i+1}\\. `{name}`" for i, name in enumerate(file_names)])
        
        if is_pending:
            if queue_size > 0:
                text = (
                    f"⏳ *معالجة الصور المتبقية للجلسة...*\n\n"
                    f"✅ تمت معالجة `{total_pages}` صورة بنجاح\\.\n"
                    f"📦 يتبقى `{queue_size}` صورة في الطابور\\.\n\n"
                    f"📄 *الصور المجهزة:*\n{files_text}\n\n"
                    f"_تم استلام اسم الملف\\. جاري معالجة الباقي تلقائياً، يرجى الانتظار..._"
                )
            else:
                text = "📦 *اكتملت معالجة جميع الصور\\!*\nجاري تجميع الملفات النهائية وإرسالها\\.\\.\\."
        else:
            text = (
                f"✅ *تمت معالجة الصور بنجاح وتخزينها في الجلسة\\.*\n\n"
                f"📊 *إحصائيات الجلسة الحالية:*\n"
                f"• الصور المترجمة: `{total_pages}`\n"
                f"• الصور في الطابور: `{queue_size}`\n\n"
                f"📄 *الصور المجهزة:*\n{files_text}\n\n"
                f"_يمكنك متابعة الإرسال، أو اضغط 🔴 إنهاء الجلسة لتجميع الملفات\\._"
            )
            
        try:
            if tracker_id:
                await self.bot.edit_message_text(chat_id=job.chat_id, message_id=tracker_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                msg = await self.bot.send_message(chat_id=job.chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                await self.batch_manager.set_tracker(job.user_id, msg.message_id)
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to update tracker: {e}")
        except Exception as e:
            logger.warning(f"Failed to update session tracker: {e}")

    async def compile_and_send(self, user_id: int, chat_id: int) -> None:
        """وظيفة موحدة لتجميع البيانات وإرسالها بناءً على إعدادات المستخدم واسم الملف المخصص."""
        session_data = await self.batch_manager.get_session_data(user_id)
        if not session_data:
            return

        # جلب اسم الملف المخصص أو الافتراضي
        custom_name = await self.batch_manager.get_custom_filename(user_id)
        base_filename = custom_name if custom_name else "manga_session"
        
        user_settings = await self.settings_manager.get_user_settings(user_id)
        output_method = user_settings.get("output_method", "files_only")
        if output_method == "chat_and_files": output_method = "messages_and_files"
        fmt = user_settings.get("file_format", "docx")
        mode = user_settings.get("mode", "scene_split")
        
        persona_name = await self.batch_manager.get_session_persona(user_id)
        handler = self.pipeline.persona_registry.get_handler(persona_name)

        try:
            if output_method == "messages_only":
                for pd in session_data:
                    temp_job = PageJob(user_id=user_id, chat_id=chat_id, page_data=pd, file_name=pd.file_name)
                    msgs = await handler.paginate(temp_job, mode=mode)
                    for msg_text in msgs:
                        try:
                            await self.bot.send_message(chat_id=chat_id, text=msg_text, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)
                            await asyncio.sleep(0.3)
                        except RetryAfter as e:
                            await asyncio.sleep(e.retry_after)
                            try: await self.bot.send_message(chat_id=chat_id, text=msg_text, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)
                            except Exception: pass
            else:
                if fmt in ["txt", "both"]:
                    file_io = handler.generate_txt(session_data)
                    await self.bot.send_document(chat_id=chat_id, document=InputFile(file_io, filename=f"{base_filename}.txt"))
                if fmt in ["docx", "both"]:
                    file_io = handler.generate_docx(session_data)
                    await self.bot.send_document(chat_id=chat_id, document=InputFile(file_io, filename=f"{base_filename}.docx"))
                    
            await self.bot.send_message(chat_id=chat_id, text="✅ *اكتملت الجلسة\\!*\nتم تجهيز الملفات وإرسالها بنجاح\\.", parse_mode=ParseMode.MARKDOWN_V2)
            
            # ترك رسالة المتابعة (Tracker) كأرشيف للمستخدم كما هو مخطط له في الـ UX
                
        except Exception as e:
            logger.error(f"Failed to process deferred compile: {e}")
            await self.bot.send_message(chat_id=chat_id, text="❌ *فشل التجميع\\.*\nحدث خطأ أثناء دمج ملفات الجلسة\\. يرجى المحاولة لاحقاً\\.", parse_mode=ParseMode.MARKDOWN_V2)
            
        await self.batch_manager.clear_session(user_id)
        await self.batch_manager.clear_pending_compile(user_id)