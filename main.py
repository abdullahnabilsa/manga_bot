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
from core.database import Database
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
from core.concurrency import ConcurrencyDBStore, ConcurrencyManager  # <--- جديد

from handlers.ui.start import start_command, help_command
from handlers.ui.settings import settings_command, settings_callback
from handlers.ui.session import start_session_command, end_session_command, cancel_command
from handlers.ui.admin import add_public_key_command, list_public_keys_command, remove_public_key_command
from handlers.ui.access import (
    add_user_command, remove_user_command, add_admin_command, remove_admin_command, 
    list_users_command, open_requests_command, close_requests_command, handle_request_callback
)
from handlers.ui.concurrency import boost_command, set_limit_command, grant_parallel_command, revoke_parallel_command  # <--- جديد
from handlers.messages import handle_image, handle_text
from handlers.ui.session import receive_session_filename

settings = Settings()
logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("manga_bot.main")

db = Database(db_path="manga_bot.db")
queue_manager = AsyncSingleWorkerQueue(max_size=settings.queue_max_size)

# Temporary placeholders, will be initialized in post_init
settings_manager: UserSettingsManager = None
persona_registry: PersonaRegistry = None
api_key_manager: APIKeyManager = None
access_manager: AccessManager = None
concurrency_manager: ConcurrencyManager = None  # <--- جديد
job_manager: JobManager = None

async def firewall_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user: return
    user_id = update.effective_user.id
    
    if await access_manager.is_authorized(user_id): return

    if await access_manager.is_join_requests_open():
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
            
            admins = await access_manager.get_admins()
            for admin_id in admins:
                try: await context.bot.send_message(chat_id=int(admin_id), text=text_to_admins, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard)
                except Exception as e: logger.warning(f"Could not send join request to admin {admin_id}: {e}")
    
    raise ApplicationHandlerStop

async def state_purge_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_session_filename'):
        if update.callback_query:
            await update.callback_query.answer("📝 يرجى إرسال اسم الملف فقط كنص أو /cancel للإلغاء.", show_alert=True)
            raise ApplicationHandlerStop
            
        msg = update.message
        if msg and msg.text in ["/cancel", "/start"]: return
            
        persistent_buttons = ["⚙️ الإعدادات", "📖 المساعدة", "🟢 بدء الجلسة", "🔴 إنهاء الجلسة"]
        is_plain_text = (msg and msg.text and not msg.text.startswith('/') and msg.text not in persistent_buttons and not msg.photo and not msg.document)
        
        if is_plain_text:
            await receive_session_filename(update, context)
            raise ApplicationHandlerStop
            
        if msg:
            try: await msg.delete()
            except Exception: pass
            raise ApplicationHandlerStop

    is_command = update.message and update.message.text and update.message.text.startswith('/')
    is_callback = update.callback_query is not None
    is_media = update.message and (update.message.photo or (update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/')))
    is_persistent_btn = update.message and update.message.text in ["⚙️ الإعدادات", "📖 المساعدة", "🟢 بدء الجلسة", "🔴 إنهاء الجلسة"]
    
    is_system_interaction = is_command or is_callback or is_persistent_btn or is_media
    if (context.user_data.get('awaiting_admin_api_key') or context.user_data.get('awaiting_user_api_key')) and is_system_interaction:
        context.user_data['awaiting_admin_api_key'] = False
        context.user_data['awaiting_user_api_key'] = False

async def session_guard_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if "batch_manager" not in context.bot_data: return
    if not await context.bot_data["batch_manager"].is_session_active(user_id): return

    if context.user_data.get('awaiting_session_filename'): return
    if update.callback_query and update.callback_query.data.startswith(("accept_req", "reject_req")): return

    if update.callback_query:
        await update.callback_query.answer("🚫 معطل أثناء الجلسة. اضغط 🔴 إنهاء الجلسة للخروج.", show_alert=True)
        raise ApplicationHandlerStop

    if update.message and (update.message.photo or (update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'))):
        return

    if update.message and update.message.text in ["/end_session", "🔴 إنهاء الجلسة", "/cancel", "/start"]:
        return

    if update.message:
        try: await update.message.delete()
        except Exception: pass
    raise ApplicationHandlerStop

async def post_init(app: Application) -> None:
    global settings_manager, persona_registry, api_key_manager, access_manager, concurrency_manager, job_manager
    
    bot = app.bot
    await db.connect()
    
    access_manager = AccessManager(db=db, super_admin_ids=settings.super_admin_ids)
    api_key_manager = APIKeyManager(db=db)
    settings_manager = UserSettingsManager(db=db)
    persona_registry = PersonaRegistry(modules_dir="modules")
    
    # --- Concurrency Engine Initialization ---
    concurrency_db_store = ConcurrencyDBStore(db=db)
    concurrency_manager = ConcurrencyManager(db_store=concurrency_db_store)
    
    # Dynamically spawn workers based on the global limit
    max_workers = await concurrency_manager.get_global_limit()
    job_manager = JobManager(
        queue_manager, 
        concurrency_manager=concurrency_manager, 
        max_running_jobs=max_workers, 
        post_job_delay=settings.post_job_delay_seconds
    )
    
    public_commands = [
        BotCommand("start", "بدء استخدام البوت"), BotCommand("settings", "فتح الإعدادات"),
        BotCommand("help", "دليل الاستخدام"), BotCommand("start_session", "بدء الجلسة"),
        BotCommand("end_session", "إنهاء الجلسة"), BotCommand("cancel", "إلغاء الجلسة"),
        BotCommand("boost", "🚀 تفعيل المعالجة المتوازية")  # <--- جديد
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
        BotCommand("setlimit", "⚙️ تحديد حد المعالجة المتوازية"),  # <--- جديد
        BotCommand("grantparallel", "✅ منح معالجة متوازية"),       # <--- جديد
        BotCommand("revokeparallel", "📉 سحب معالجة متوازية")       # <--- جديد
    ]
    
    admins = await access_manager.get_admins()
    for admin_id in admins:
        try:
            cmds = super_admin_commands if access_manager.is_super_admin(int(admin_id)) else admin_commands
            await bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=int(admin_id)))
        except Exception as e:
            logger.warning(f"Could not set admin commands for {admin_id}: {e}")
    
    pipeline = BotPipeline(
        bot=bot, settings_manager=settings_manager, batch_manager=batch_manager, 
        persona_registry=persona_registry, ai_provider=ai_provider, 
        telegram_renderer=telegram_renderer, api_key_manager=api_key_manager,
        queue_manager=queue_manager, concurrency_manager=concurrency_manager  # <--- جديد
    )
    
    app.bot_data["db"] = db
    app.bot_data["job_manager"] = job_manager
    app.bot_data["queue_manager"] = queue_manager
    app.bot_data["settings_manager"] = settings_manager
    app.bot_data["batch_manager"] = batch_manager
    app.bot_data["persona_registry"] = persona_registry
    app.bot_data["api_key_manager"] = api_key_manager
    app.bot_data["access_manager"] = access_manager
    app.bot_data["pipeline"] = pipeline
    app.bot_data["concurrency_manager"] = concurrency_manager  # <--- جديد

    await pipeline.register(job_manager)
    await job_manager.start()

async def post_shutdown(app: Application) -> None:
    await job_manager.stop()
    if 'db' in app.bot_data:
        await app.bot_data['db'].close()

def main() -> None:
    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_handler(TypeHandler(Update, firewall_middleware), group=-3)
    app.add_handler(TypeHandler(Update, state_purge_middleware), group=-2)
    app.add_handler(TypeHandler(Update, session_guard_middleware), group=-1)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("start_session", start_session_command))
    app.add_handler(CommandHandler("end_session", end_session_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("boost", boost_command))  # <--- جديد
    
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
    app.add_handler(CommandHandler("setlimit", set_limit_command))                  # <--- جديد
    app.add_handler(CommandHandler("grantparallel", grant_parallel_command))        # <--- جديد
    app.add_handler(CommandHandler("revokeparallel", revoke_parallel_command))      # <--- جديد
    
    app.add_handler(MessageHandler(filters.Regex("⚙️ الإعدادات"), settings_command))
    app.add_handler(MessageHandler(filters.Regex("📖 المساعدة"), help_command))
    app.add_handler(MessageHandler(filters.Regex("🟢 بدء الجلسة"), start_session_command))
    app.add_handler(MessageHandler(filters.Regex("🔴 إنهاء الجلسة"), end_session_command))
    
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(open_|set_|back_)"))
    app.add_handler(CallbackQueryHandler(handle_request_callback, pattern="^(accept_req|reject_req)"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    logger.info("Starting Manga Translation Bot with Dynamic Concurrency Engine...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()