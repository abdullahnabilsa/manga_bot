# File: handlers/messages.py
from __future__ import annotations
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from telegram.error import RetryAfter, TelegramError
from models.page_job import PageJob
from utils.markdown_escaper import escape_markdown_v2

from handlers.ui.api_keys import receive_user_api_key
from handlers.ui.admin import receive_admin_api_key
from handlers.ui.session import receive_session_filename

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    job_manager = context.bot_data["job_manager"]
    queue_manager = context.bot_data["queue_manager"]
    batch_manager = context.bot_data["batch_manager"]
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # إلغاء انتظار اسم الملف إذا أرسل المستخدم صورة بالخطأ أثناء الانتظار
    if context.user_data.get('awaiting_session_filename'):
        context.user_data['awaiting_session_filename'] = False
        await context.bot.send_message(chat_id=chat_id, text="↩️ *تم إلغاء انتظار الاسم وإضافة الصورة للطابور\\.\"", parse_mode=ParseMode.MARKDOWN_V2)
    
    is_session_active = await batch_manager.is_session_active(user.id)
    queue_size_before = await queue_manager.size()
    
    # --- إرسال رسالة التحليل فوراً قبل التحميل والترجمة (استجابة فورية) ---
    if is_session_active:
        tracker_id = await batch_manager.get_tracker(user.id)
        current_queue = queue_size_before + 1
        translated_count = len(await batch_manager.get_session_data(user.id))
        
        if queue_size_before == 0 and tracker_id:
            try: 
                await context.bot.delete_message(chat_id=chat_id, message_id=tracker_id)
            except: 
                pass
            await batch_manager.set_tracker(user.id, None)
            tracker_id = None
            
        if not tracker_id:
            text = (
                f"⏳ *جاري التحليل...*\n\n"
                f"📊 *إحصائيات الجلسة الحالية:*\n"
                f"• الصور المترجمة: `{translated_count}`\n"
                f"• الصور في الطابور: `{current_queue}`\n\n"
                f"_يرجى الانتظار، الذكاء الاصطناعي يحلل الصور..._"
            )
            try:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                await batch_manager.set_tracker(user.id, msg.message_id)
            except Exception: pass
        else:
            text = (
                f"⏳ *تم استلام صور جديدة وإضافتها للطابور...*\n\n"
                f"📊 *إحصائيات الجلسة الحالية:*\n"
                f"• الصور المترجمة: `{translated_count}`\n"
                f"• الصور في الطابور: `{current_queue}`\n\n"
                f"_يرجى الانتظار، جاري المعالجة..._"
            )
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=tracker_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception: pass 
    # -----------------------------------------------------------------

    # تحميل الصورة من تيليجرام (يستغرق وقتاً)
    image_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        file_name = f"Photo_{update.message.message_id}.jpg"
    elif update.message.document:
        mime_type = update.message.document.mime_type
        if mime_type and mime_type.startswith('image/'):
            doc_file = await update.message.document.get_file()
            image_bytes = await doc_file.download_as_bytearray()
            file_name = update.message.document.file_name or f"Document_{update.message.message_id}.jpg"
        else:
            await context.bot.send_message(chat_id=chat_id, text="🚫 *ملف غير مدعوم\\.*\nيرجى إرسال صورة بصيغة JPG أو PNG\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

    if not image_bytes:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ *خطأ في الاستلام\\.*\nلم أتمكن من قراءة الصورة، يرجى إعادة إرسالها\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    # إنشاء الـ Job وإدخاله في الطابور
    job = PageJob(
        user_id=user.id, 
        chat_id=chat_id, 
        image_bytes=bytes(image_bytes), 
        file_name=file_name,
        photo_message_id=update.message.message_id
    )
    await job_manager.submit_job(job)
    
    # إرسال رسالة الحالة للوضع العادي (بدون جلسة)
    if not is_session_active:
        eta_seconds = (queue_size_before + 1) * 15
        escaped_file = escape_markdown_v2(file_name) if file_name else "Unknown"
        if queue_size_before == 0:
            text = (
                f"📥 *تم استلام الصورة بنجاح\\.*\n"
                f"🖼️ الملف: `{escaped_file}`\n"
                f"⏳ *جاري التحليل الآن\\.\\.\\.*"
            )
        else:
            text = (
                f"📥 *تم استلام الصورة بنجاح\\.*\n"
                f"🖼️ الملف: `{escaped_file}`\n"
                f"⏳ *في الطابور:* مكانك الحالي {queue_size_before} \\| الوقت المتوقع: ~{eta_seconds} ثانية\\."
            )
        
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            status_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            job.status_message_id = status_msg.message_id
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                status_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                job.status_message_id = status_msg.message_id
            except Exception:
                pass
        except TelegramError:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_user_api_key'):
        await receive_user_api_key(update, context)
    elif context.user_data.get('awaiting_admin_api_key'):
        await receive_admin_api_key(update, context)
    elif context.user_data.get('awaiting_session_filename'):
        await receive_session_filename(update, context)
    else:
        await update.message.reply_text("ℹ️ *مرحباً\\!*\nيرجى إرسال صورة لترجمتها\\.\nاستخدم الأزرار بالأسفل للتحكم في البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)