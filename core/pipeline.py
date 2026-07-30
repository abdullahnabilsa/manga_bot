# File: core/pipeline.py
from __future__ import annotations

import asyncio
import io
import logging
from typing import List

from PIL import Image
from telegram import InputFile
from telegram.constants import ParseMode, ChatAction
from telegram.error import RetryAfter

from config.settings import Settings
from core.job_manager import JobManager
from utils.markdown_escaper import escape_markdown_v2
from models.page_job import PageJob, MessagePayload
from core.senders.direct_sender import DirectSender
from core.senders.session_sender import SessionSender
from ai.gemini_provider import ServiceUnavailableError

logger = logging.getLogger("manga_bot.pipeline")

class _BotContextWrapper:
    def __init__(self, bot):
        self.bot = bot

class BotErrorNotifier:
    def __init__(self, bot):
        self._bot = bot

    async def notify(self, job: PageJob, error: Exception) -> None:
        if isinstance(error, ServiceUnavailableError):
            text = "🚨 *الخدمة تحت الصيانة مؤقتاً\\.*\nخوادم الذكاء الاصطناعي تواجه ضغطاً شديداً حالياً\\. يرجى الانتظار دقيقة وإعادة المحاولة\\."
            try:
                await self._bot.send_message(chat_id=job.chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                if job.status_message_id:
                    await self._bot.delete_message(chat_id=job.chat_id, message_id=job.status_message_id)
                    job.status_message_id = None
            except Exception as e:
                logger.error(f"Failed to send maintenance notification: {e}")
            return

        text = f"❌ *فشلت المعالجة*\n🖼️ الملف: `{escape_markdown_v2(job.file_name)}`\n⚠️ لم يتمكن النظام من ترجمة هذه الصفحة\\.\n_يرجى المحاولة مرة أخرى لاحقاً._"
        try:
            if job.status_message_id:
                await self._bot.edit_message_text(
                    chat_id=job.chat_id,
                    message_id=job.status_message_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await self._bot.send_message(
                    chat_id=job.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

class BotPipeline:
    """Main Pipeline Router: Orchestrates processing, rendering, and delegates sending."""
    
    def __init__(self, bot, settings_manager, batch_manager, persona_registry, ai_provider, telegram_renderer, api_key_manager, queue_manager):
        self.bot = bot
        self.settings_manager = settings_manager
        self.batch_manager = batch_manager
        self.persona_registry = persona_registry
        self.ai_provider = ai_provider
        self.telegram_renderer = telegram_renderer
        self.api_key_manager = api_key_manager
        self.queue_manager = queue_manager
        self.bot_context = _BotContextWrapper(bot)
        self._settings = Settings()
        
        self.direct_sender = DirectSender(self)
        self.session_sender = SessionSender(self)

    async def safe_edit_or_send(self, job: PageJob, text: str) -> None:
        try:
            if job.status_message_id:
                await self.bot.edit_message_text(chat_id=job.chat_id, message_id=job.status_message_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                msg = await self.bot.send_message(chat_id=job.chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                job.status_message_id = msg.message_id
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                if job.status_message_id:
                    await self.bot.edit_message_text(chat_id=job.chat_id, message_id=job.status_message_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    msg = await self.bot.send_message(chat_id=job.chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                    job.status_message_id = msg.message_id
            except Exception: pass
        except Exception: pass

    async def safe_delete_message(self, job: PageJob) -> None:
        if not job.status_message_id: return
        try:
            await self.bot.delete_message(chat_id=job.chat_id, message_id=job.status_message_id)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try: await self.bot.delete_message(chat_id=job.chat_id, message_id=job.status_message_id)
            except Exception: pass
        except Exception: pass

    def _optimize_image(self, image_bytes: bytes) -> bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            max_size = 1280
            if max(img.width, img.height) > max_size:
                ratio = max_size / max(img.width, img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            return buffer.getvalue()
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            return image_bytes

    async def processing_step(self, job: PageJob) -> PageJob:
        await self.bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.TYPING)
        
        is_session_active = await self.batch_manager.is_session_active(job.user_id)
        if not is_session_active and job.status_message_id:
            text = f"🔍 *جاري التحليل\\.*\n🖼️ الملف: `{escape_markdown_v2(job.file_name)}`\n⏳ _الذكاء الاصطناعي يقرأ الصورة..._"
            try:
                await self.bot.edit_message_text(chat_id=job.chat_id, message_id=job.status_message_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception: pass

        if not job.image_bytes and job.image_file_id:
            try:
                tg_file = await self.bot.get_file(job.image_file_id)
                job.image_bytes = await tg_file.download_as_bytearray()
            except Exception as e:
                logger.error(f"JobID={job.job_id} | Failed to download image: {e}")
                raise RuntimeError(f"Failed to download image file: {e}")

        if job.image_bytes:
            job.image_bytes = self._optimize_image(job.image_bytes)

        persona_name = await self.settings_manager.get_persona(job.user_id)
        if not persona_name or persona_name not in self.persona_registry.get_available_personas():
            persona_name = "Default Translator"
            
        handler = self.persona_registry.get_handler(persona_name)
        prompt_text = handler.prompt
        
        # --- تم تصحيح الخطأ هنا بإضافة await ---
        api_keys = await self.api_key_manager.get_keys_for_user(job.user_id)
        if not api_keys:
            env_key = self._settings.ai_api_key
            if env_key: api_keys = [env_key]
            else: raise RuntimeError("No API keys available for the user and no fallback key in .env")
        
        raw_json = await self.ai_provider.extract_raw_json(job.image_bytes, job.job_id, prompt_text, api_keys=api_keys)
        
        job = await handler.validate_and_update_job(job, raw_json)
        if job.page_data: job.page_data.file_name = job.file_name
        return job

    async def rendering_step(self, job: PageJob) -> PageJob:
        persona_name = await self.settings_manager.get_persona(job.user_id)
        handler = self.persona_registry.get_handler(persona_name)
        
        user_settings = await self.settings_manager.get_user_settings(job.user_id)
        mode = user_settings.get("mode", "scene_split")
        
        messages: List[str] = await handler.paginate(job, mode=mode)
        job.message_payloads = [
            MessagePayload(page_index=i, total_pages=len(messages), text=msg)
            for i, msg in enumerate(messages)
        ]
        return job

    async def sending_step(self, job: PageJob) -> PageJob:
        await self.bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
        
        persona_name = await self.settings_manager.get_persona(job.user_id)
        handler = self.persona_registry.get_handler(persona_name)
        
        if await self.batch_manager.is_session_active(job.user_id):
            return await self.session_sender.process(job, handler)
        else:
            return await self.direct_sender.process(job, handler)

    async def register(self, job_manager: JobManager) -> None:
        job_manager.register_pipeline_steps(
            processing_step=self.processing_step,
            rendering_step=self.rendering_step,
            sending_step=self.sending_step
        )
        notifier = BotErrorNotifier(self.bot)
        job_manager.register_error_notifier(notifier.notify)