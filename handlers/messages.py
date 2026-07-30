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
    settings_manager = context.bot_data["settings_manager"]
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    image_file_id: Optional[str] = None
    file_name: Optional[str] = None
    
    if update.message.photo:
        image_file_id = update.message.photo[-1].file_id
        file_name = f"Photo_{update.message.message_id}.jpg"
    elif update.message.document:
        mime_type = update.message.document.mime_type
        if mime_type and mime_type.startswith('image/'):
            image_file_id = update.message.document.file_id
            file_name = update.message.document.file_name or f"Document_{update.message.message_id}.jpg"
        else:
            await context.bot.send_message(chat_id=chat_id, text="🚫 *ملف غير مدعوم\\.*\nيرجى إرسال صورة بصيغة JPG أو PNG\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return

    if not image_file_id:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ *خطأ في الاستلام\\.*\nلم أتمكن من قراءة الصورة، يرجى إعادة إرسالها\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    if context.user_data.get('awaiting_session_filename'):
        context.user_data['awaiting_session_filename'] = False
        await context.bot.send_message(chat_id=chat_id, text="↩️ *تم إلغاء انتظار الاسم وإضافة الصورة للطابور\\.\"", parse_mode=ParseMode.MARKDOWN_V2)
    
    is_session_active = await batch_manager.is_session_active(user.id)
    queue_size_before = await queue_manager.size()
    
    job = PageJob(
        user_id=user.id, 
        chat_id=chat_id, 
        image_file_id=image_file_id, 
        file_name=file_name,
        photo_message_id=update.message.message_id
    )
    await job_manager.submit_job(job)
    
    if is_session_active:
        tracker_id = await batch_manager.get_tracker(user.id)
        current_queue = await queue_manager.size()
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
                f"⏳ *تم استلام الصور وجاري بدء المعالجة...*\n\n"
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
    else:
        # وضع الترجمة المباشرة (Direct Mode)
        user_settings = await settings_manager.get_user_settings(user.id)
        output_method = user_settings.get("output_method", "files_only")
        if output_method == "chat_and_files": output_method = "messages_and_files"
        
        if output_method == "messages_only":
            # تسليم صامت تام للنصوص
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception: pass
        else:
            # ملفات
            if queue_size_before == 0:
                # دفعة جديدة: التخلص من أي رسالة معلقة من دفعة سابقة
                direct_msg_id = context.user_data.get('direct_status_msg_id')
                if direct_msg_id:
                    try: await context.bot.delete_message(chat_id=chat_id, message_id=direct_msg_id)
                    except: pass
                
                text = "⏳ *جاري التحليل الآن\\.\\.\\.*"
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                    status_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                    job.status_message_id = status_msg.message_id
                    context.user_data['direct_status_msg_id'] = status_msg.message_id
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    try:
                        status_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                        job.status_message_id = status_msg.message_id
                        context.user_data['direct_status_msg_id'] = status_msg.message_id
                    except Exception:
                        pass
                except TelegramError:
                    pass
            else:
                # دفعة مستمرة: تحديث رسالة الحالة الموحدة للدفعة
                direct_msg_id = context.user_data.get('direct_status_msg_id')
                if direct_msg_id:
                    text = f"⏳ *جاري التحليل...*\n📦 في الطابور: `{queue_size_before}`"
                    try:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=direct_msg_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                        job.status_message_id = direct_msg_id
                    except Exception:
                        # If edit fails, create new
                        try:
                            status_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
                            job.status_message_id = status_msg.message_id
                            context.user_data['direct_status_msg_id'] = status_msg.message_id
                        except: pass
                else:
                    # Fallback just in case
                    try: await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                    except: pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_user_api_key'):
        await receive_user_api_key(update, context)
    elif context.user_data.get('awaiting_admin_api_key'):
        await receive_admin_api_key(update, context)
    elif context.user_data.get('awaiting_session_filename'):
        await receive_session_filename(update, context)
    else:
        await update.message.reply_text("ℹ️ *مرحباً\\!*\nيرجى إرسال صورة لترجمتها\\.\nاستخدم الأزرار بالأسفل للتحكم في البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)