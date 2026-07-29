# File: handlers/ui/session.py
from __future__ import annotations
import asyncio
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from telegram.error import RetryAfter

from utils.markdown_escaper import escape_markdown_v2, sanitize_filename
from models.page_job import PageJob

async def start_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    batch_manager = context.bot_data["batch_manager"]
    settings_manager = context.bot_data["settings_manager"]
    user_id = update.effective_user.id
    
    persona_name = await settings_manager.get_persona(user_id)
    if not persona_name: persona_name = "Default Translator"
    await batch_manager.start_session(user_id, persona_name)
    
    text = (
        "🎬 *تم تفعيل الجلسة بنجاح\\!*\n\n"
        "يمكنك الآن إرسال صور صفحات المانغا\\. سأقوم بمعالجتها وتخزينها في الذاكرة\\.\n\n"
        "⚠️ *مهم:* عند انتهائك، اضغط *🔴 إنهاء الجلسة* لتسمية الملف وتجميعه\\."
    )
    await update.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)

async def end_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    batch_manager = context.bot_data["batch_manager"]
    queue_manager = context.bot_data["queue_manager"]
    user_id = update.effective_user.id
    
    if not await batch_manager.is_session_active(user_id):
        await update.message.reply_text("⚠️ *لا توجد جلسة نشطة حالياً\\.*\nاضغط *🟢 بدء الجلسة* أولاً قبل إرسال الصور\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    session_data = await batch_manager.get_session_data(user_id)
    if not session_data:
        await update.message.reply_text("⚠️ *الجلسة فارغة\\.*\nلم تقم بإرسال أي صور صالحة\\. أرسل صوراً أولاً ثم أنهِ الجلسة\\.", parse_mode=ParseMode.MARKDOWN_V2)
        await batch_manager.clear_session(user_id)
        return

    # تفعيل وضع انتظار اسم الملف
    context.user_data['awaiting_session_filename'] = True
    
    text = (
        "📝 *تسمية ملف الترجمة*\n\n"
        "يرجى إرسال الاسم الذي تريد حفظ ملف الترجمة به الآن\\.\n\n"
        "_ملاحظة: سيتم تنظيف الاسم تلقائياً من الرموز غير المسموحة_"
    )
    await update.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)

async def receive_session_filename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    batch_manager = context.bot_data["batch_manager"]
    queue_manager = context.bot_data["queue_manager"]
    user_id = update.effective_user.id
    
    context.user_data['awaiting_session_filename'] = False
    
    raw_filename = update.message.text
    clean_filename = sanitize_filename(raw_filename)
    escaped_filename = escape_markdown_v2(clean_filename)
    
    await batch_manager.set_custom_filename(user_id, clean_filename)
    
    # مسح رسالة المستخدم التي تحتوي على الاسم للحفاظ على نظافة الشات
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except Exception:
        pass
    
    queue_size = await queue_manager.size()
    
    if queue_size > 0:
        # الطابور مليء: تفعيل التجميع المؤجل
        await batch_manager.set_pending_compile(user_id)
        msg_text = f"⏳ *تم تسجيل اسم الملف:* `{escaped_filename}`\nلا تزال لديك صور قيد المعالجة\\. سيقوم البوت بتجميع الملف وإرساله فور اكتمالها\\."
        
        # إرسال كرسالة جديدة بدلاً من تعديل رسالة الإحصائيات
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg_text, parse_mode=ParseMode.MARKDOWN_V2)
        return

    # الطابور فارغ: التجميع الفوري
    msg_text = f"⏳ *جاري تجميع الترجمة بإسم:* `{escaped_filename}`\\.\\.\\."
    
    # إرسال كرسالة جديدة بدلاً من تعديل رسالة الإحصائيات
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg_text, parse_mode=ParseMode.MARKDOWN_V2)
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
    
    # استدعاء محرك التجميع الموحد في SessionSender
    session_sender = context.bot_data["pipeline"].session_sender
    await session_sender.compile_and_send(user_id, update.effective_chat.id)