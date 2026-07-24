# File: main.py
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, ContextTypes, MessageHandler, 
    filters, CommandHandler, CallbackQueryHandler
)

from config.settings import Settings
from core.job_manager import JobManager
from core.queue_manager import AsyncSingleWorkerQueue
from core.user_settings_manager import UserSettingsManager
from models.page_job import MessagePayload, PageJob
from ai.gemini_provider import GeminiProvider
from parser.validator import Validator
from renderer.paginator import Paginator
from renderer.telegram_renderer import TelegramRenderer
from utils.logger import job_logger
from utils.prompt_manager import PromptManager
from utils.template_manager import TemplateManager
from utils.markdown_escaper import escape_markdown_v2

# Initialize settings and logger
settings = Settings()
logger = logging.getLogger("manga_bot.main")

# --- Pipeline Components Initialization ---
queue_manager = AsyncSingleWorkerQueue(max_size=settings.queue_max_size)
job_manager = JobManager(queue_manager, post_job_delay=settings.post_job_delay_seconds)

ai_provider = GeminiProvider(api_key=settings.ai_api_key)
validator = Validator()

# 🆕 تهيئة محرك القوالب وتمريره للمقسم
template_manager = TemplateManager(templates_dir="templates")
paginator = Paginator(template_manager)

telegram_renderer = TelegramRenderer()

# --- New Managers ---
prompt_manager = PromptManager(prompts_dir="prompts")
settings_manager = UserSettingsManager(file_path="users_data.json")


class _BotContextWrapper:
    def __init__(self, bot):
        self.bot = bot

# --- Pipeline Steps Definition ---
async def processing_step(job: PageJob) -> PageJob:
    persona_name = await settings_manager.get_persona(job.user_id)
    if not persona_name or persona_name not in prompt_manager.get_available_personas():
        persona_name = "Default Translator"
    prompt_text = prompt_manager.get_prompt(persona_name)
    
    raw_json = await ai_provider.extract_raw_json(job.image_bytes, job.job_id, prompt_text)
    return await validator.validate_and_update_job(job, raw_json)

async def rendering_step(job: PageJob) -> PageJob:
    messages: List[str] = await paginator.paginate(job, page_num=1)
    job.message_payloads = [
        MessagePayload(page_index=i, total_pages=len(messages), text=msg)
        for i, msg in enumerate(messages)
    ]
    return job

def create_sending_step(app: Application):
    bot_context = _BotContextWrapper(app.bot)
    async def sending_step(job: PageJob) -> PageJob:
        strings = [p.text for p in job.message_payloads]
        await telegram_renderer.render_messages(bot_context, job, strings)
        return job
    return sending_step

# --- Telegram Bot Handlers ---
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    image_bytes: Optional[bytes] = None
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
    elif update.message.document:
        mime_type = update.message.document.mime_type
        if mime_type and mime_type.startswith('image/'):
            doc_file = await update.message.document.get_file()
            image_bytes = await doc_file.download_as_bytearray()
        else:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ الملف المرسل ليس صورة. الرجاء إرسال ملفات الصور فقط.")
            return

    if not image_bytes:
        await context.bot.send_message(chat_id=chat_id, text="الرجاء إرسال صورة صفحة المانهوا مباشرة أو كملف.")
        return
    
    job = PageJob(user_id=user.id if user else chat_id, chat_id=chat_id, image_bytes=bytes(image_bytes))
    await job_manager.submit_job(job)
    
    current_persona = await settings_manager.get_persona(user.id)
    persona_display = escape_markdown_v2(current_persona) if current_persona else escape_markdown_v2("الافتراضي")
    job_id_str = escape_markdown_v2(str(job.job_id))
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ تم استلام الصفحة\\.\n🆔 رقم الطلب: `{job_id_str}`\n🎭 الشخصية: {persona_display}\n⏳ جاري المعالجة\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    personas = prompt_manager.get_available_personas()
    if not personas:
        await update.message.reply_text("لا توجد شخصيات متاحة حالياً.")
        return
    keyboard = [[InlineKeyboardButton(p, callback_data=f"set_persona_{p}")] for p in personas]
    await update.message.reply_text("🎭 اختر شخصية المترجم:", reply_markup=InlineKeyboardMarkup(keyboard))

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("set_persona_"):
        persona_name = data.replace("set_persona_", "")
        await settings_manager.set_persona(query.from_user.id, persona_name)
        await query.edit_message_text(text=f"✅ تم تثبيت شخصية المترجم: *{escape_markdown_v2(persona_name)}*", parse_mode=ParseMode.MARKDOWN_V2)

# 🆕 أمر تحديث القوالب والشخصيات للمشرف
async def reload_templates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if settings.admin_id and user.id != settings.admin_id:
        await update.message.reply_text("⛔ غير مصرح لك بهذا الأمر.")
        return
    
    prompt_manager.load_prompts()
    template_manager.reload()
    await update.message.reply_text("✅ تم إعادة تحميل القوالب والشخصيات بنجاح.")

async def post_init(app: Application) -> None:
    app.bot_data["job_manager"] = job_manager
    job_manager.register_pipeline_steps(
        processing_step=processing_step,
        rendering_step=rendering_step,
        sending_step=create_sending_step(app)
    )
    await job_manager.start()

async def post_shutdown(app: Application) -> None:
    await job_manager.stop()

def main() -> None:
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("reload_templates", reload_templates)) # 🆕
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_persona_"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    logger.info("Starting Manga Translation Bot with Dynamic Templates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()