# File: main.py
from __future__ import annotations

import asyncio
import logging
from telegram import Update, BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, ContextTypes, MessageHandler, 
    filters, CommandHandler, CallbackQueryHandler, TypeHandler, ApplicationHandlerStop
)
from telegram.constants import ParseMode
from utils.markdown_escaper import escape_markdown_v2

from config.settings import Settings
from core.job_manager import JobManager
from core.queue_manager import AsyncSingleWorkerQueue
from core.user_settings_manager import UserSettingsManager
from core.batch_manager import BatchManager
from core.persona_registry import PersonaRegistry
from core.api_key_manager import APIKeyManager
from core.access_manager import AccessManager
from core.pipeline import BotPipeline
from ai.gemini_provider import GeminiProvider
from renderer.telegram_renderer import TelegramRenderer

from handlers.ui.start import start_command, help_command
from handlers.ui.settings import settings_command, settings_callback
from handlers.ui.session import start_session_command, end_session_command
from handlers.ui.admin import add_public_key_command, list_public_keys_command, remove_public_key_command
from handlers.ui.access import (
    add_user_command, remove_user_command, add_admin_command, remove_admin_command, 
    list_users_command, open_requests_command, close_requests_command, handle_request_callback
)
from handlers.messages import handle_image, handle_text

settings = Settings()
logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("manga_bot.main")

queue_manager = AsyncSingleWorkerQueue(max_size=settings.queue_max_size)
job_manager = JobManager(queue_manager, post_job_delay=settings.post_job_delay_seconds)
batch_manager = BatchManager()
settings_manager = UserSettingsManager(file_path="users_data.json")
ai_provider = GeminiProvider(timeout=settings.ai_timeout_seconds)
telegram_renderer = TelegramRenderer()

persona_registry = PersonaRegistry(modules_dir="modules")
api_key_manager = APIKeyManager(file_path="api_keys.json")
access_manager = AccessManager(file_path="access_control.json", super_admin_id=settings.super_admin_id)

async def firewall_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user: return
    user_id = update.effective_user.id
    
    if access_manager.is_authorized(user_id): return

    if access_manager.is_join_requests_open():
        if update.message and update.message.text and update.message.text.startswith("/start"):
            user = update.effective_user
            try:
                await context.bot.send_message(chat_id=user_id, text="⏳ *تم استلام طلبك للانضمام إلى البوت\\.*\nسيقوم المشرفون بمراجعة طلبك\\. ستصلك رسالة فور الموافقة\\.", parse_mode=ParseMode.MARKDOWN_V2)
            except Exception: pass
            
            text_to_admins = f"🔔 *طلب انضمام جديد\\!*\n\n👤 *الاسم:* {escape_markdown_v2(user.first_name or 'N/A')}\n"
            if user.last_name: text_to_admins += f"📎 *اللقب:* {escape_markdown_v2(user.last_name)}\n"
            text_to_admins += f"🆔 *الـ ID:* `{user_id}`\n"
            if user.username: text_to_admins += f"🌐 *اليوزر:* @{escape_markdown_v2(user.username)}\n"
            if user.language_code: text_to_admins += f"🌍 *اللغة:* {escape_markdown_v2(user.language_code)}\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ قبول", callback_data=f"accept_req:{user_id}"),
                 InlineKeyboardButton("❌ رفض", callback_data=f"reject_req:{user_id}")]
            ])
            
            for admin_id in access_manager.get_admins():
                try: await context.bot.send_message(chat_id=int(admin_id), text=text_to_admins, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
                except Exception as e: logger.warning(f"Could not send join request to admin {admin_id}: {e}")
    
    raise ApplicationHandlerStop

async def post_init(app: Application) -> None:
    bot = app.bot
    
    public_commands = [
        BotCommand("start", "بدء استخدام البوت"), BotCommand("settings", "فتح الإعدادات"),
        BotCommand("help", "دليل الاستخدام"), BotCommand("start_session", "بدء الجلسة"),
        BotCommand("end_session", "إنهاء الجلسة")
    ]
    await bot.set_my_commands(public_commands)
    
    admin_commands = public_commands + [
        BotCommand("addkey", "➕ إضافة مفتاح API"), BotCommand("listkeys", "📋 عرض مفاتيح API"),
        BotCommand("removekey", "🗑️ حذف مفتاح API"), BotCommand("adduser", "➕ إضافة مستخدم"),
        BotCommand("removeuser", "🗑️ حذف مستخدم"), BotCommand("listusers", "📋 عرض المستخدمين"),
        BotCommand("openrequests", "🟢 فتح باب الانضمام"), BotCommand("closerequests", "🔴 إغلاق باب الانضمام"),
    ]
    super_admin_commands = admin_commands + [
        BotCommand("addadmin", "👑 ترقية لمشرف"), BotCommand("removeadmin", "📉 إزالة مشرف"),
    ]
    
    for admin_id in access_manager.get_admins():
        try:
            cmds = super_admin_commands if access_manager.is_super_admin(int(admin_id)) else admin_commands
            await bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=int(admin_id)))
        except Exception as e:
            logger.warning(f"Could not set admin commands for {admin_id}: {e}")
    
    app.bot_data["job_manager"] = job_manager
    app.bot_data["queue_manager"] = queue_manager
    app.bot_data["settings_manager"] = settings_manager
    app.bot_data["batch_manager"] = batch_manager
    app.bot_data["persona_registry"] = persona_registry
    app.bot_data["api_key_manager"] = api_key_manager
    app.bot_data["access_manager"] = access_manager
    app.bot_data["pipeline"] = pipeline  # <--- تمت إضافته هنا ليتوفر دائماً في الجلسة

    pipeline = BotPipeline(
        bot=bot, settings_manager=settings_manager, batch_manager=batch_manager, 
        persona_registry=persona_registry, ai_provider=ai_provider, 
        telegram_renderer=telegram_renderer, api_key_manager=api_key_manager,
        queue_manager=queue_manager 
    )
    app.bot_data["pipeline"] = pipeline  # تحديث المرجع بالكائن المبني
    await pipeline.register(job_manager)
    await job_manager.start()

async def post_shutdown(app: Application) -> None:
    await job_manager.stop()

def main() -> None:
    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(TypeHandler(Update, firewall_middleware), group=-1)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("start_session", start_session_command))
    app.add_handler(CommandHandler("end_session", end_session_command))
    
    app.add_handler(CommandHandler("addkey", add_public_key_command))
    app.add_handler(CommandHandler("listkeys", list_public_keys_command))
    app.add_handler(CommandHandler("removekey", remove_public_key_command))
    
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("removeuser", remove_user_command))
    app.add_handler(CommandHandler("listusers", list_users_command))
    app.add_handler(CommandHandler("openrequests", open_requests_command))
    app.add_handler(CommandHandler("closerequests", close_requests_command))
    
    app.add_handler(CommandHandler("addadmin", add_admin_command))
    app.add_handler(CommandHandler("removeadmin", remove_admin_command))
    
    app.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), settings_command))
    app.add_handler(MessageHandler(filters.Regex("📖 المساعدة"), help_command))
    app.add_handler(MessageHandler(filters.Regex("🟢 بدء الجلسة"), start_session_command))
    app.add_handler(MessageHandler(filters.Regex("🔴 إنهاء الجلسة"), end_session_command))
    
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(open_|set_|back_)"))
    app.add_handler(CallbackQueryHandler(handle_request_callback, pattern="^(accept_req|reject_req)"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    logger.info("Starting Manga Translation Bot with Independent Sending Routes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()