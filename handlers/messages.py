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
    image_file_id: Optional[str] = None
    file_name: Optional[str] = None
    
    # التحقق من حالة الجلسة مبكراً لاستخدامها في فلترة الملفات غير المدعومة
    is_session_active = await batch_manager.is_session_active(user.id)
    
    # الاستجابة الفورية: التقاط file_id فقط دون تحميل الصورة
    if update.message.photo:
        image_file_id = update.message.photo[-1].file_id
        file_name = f"Photo_{update.message.message_id}.jpg"
    elif update.message.document:
        mime_type = update.message.document.mime_type
        if mime_type and mime_type.startswith('image/'):
            image_file_id = update.message.document.file_id
            file_name = update.message.document.file_name or f"Document_{update.message.message_id}.jpg"
        else:
            # وضع التركيز الإلزامي: حذف الملفات غير المدعومة بصمت أثناء الجلسة
            if is_session_active:
                try:
                    await update.message.delete()
                except Exception:
                    pass
                return
            else:
                await context.bot.send_message(chat_id=chat_id, text="🚫 *ملف غير مدعوم\\.*\nيرجى إرسال صورة بصيغة JPG أو PNG\\.", parse_mode=ParseMode.MARKDOWN_V2)
                return

    if not image_file_id:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ *خطأ في الاستلام\\.*\nلم أتمكن من قراءة الصورة، يرجى إعادة إرسالها\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    # إلغاء انتظار اسم الملف إذا أرسل المستخدم صورة بالخطأ أثناء الانتظار
    if context.user_data.get('awaiting_session_filename'):
        context.user_data['awaiting_session_filename'] = False
        await context.bot.send_message(chat_id=chat_id, text="↩️ *تم إلغاء انتظار الاسم وإضافة الصورة للطابور\\.\"", parse_mode=ParseMode.MARKDOWN_V2)
    
    queue_size_before = await queue_manager.size()
    
    # إنشاء الـ Job وإدخاله في الطابور فوراً (Queue First)
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
        
        # السيناريو الثاني: دفعة جديدة بعد انتهاء السابقة (الطابور كان فارغاً).
        # نحذف الرسالة القديمة لمنع الازدحام ونبدأ رسالة جديدة بالأسفل.
        if queue_size_before == 0 and tracker_id:
            try: 
                await context.bot.delete_message(chat_id=chat_id, message_id=tracker_id)
            except: 
                pass
            await batch_manager.set_tracker(user.id, None)
            tracker_id = None
            
        if not tracker_id:
            # رسالة البدء المباشرة (قبل بدء التحليل)
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
            # تحديث عداد الطابور فقط إذا وردت صور إضافية أثناء المعالجة
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
        # وضع الترجمة المباشرة (بدون جلسة)
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
    # 1. مسارات انتظار الإدخال (أولوية قصوى)
    if context.user_data.get('awaiting_user_api_key'):
        await receive_user_api_key(update, context)
        return
    elif context.user_data.get('awaiting_admin_api_key'):
        await receive_admin_api_key(update, context)
        return
    elif context.user_data.get('awaiting_session_filename'):
        await receive_session_filename(update, context)
        return

    # 2. وضع التركيز الإلزامي أثناء الجلسة
    batch_manager = context.bot_data["batch_manager"]
    if await batch_manager.is_session_active(update.effective_user.id):
        # حذف أي رسالة نصية عشوائية يرسلها المستخدم أثناء الجلسة بصمت تام
        try:
            await update.message.delete()
        except Exception:
            pass
        return

    # 3. الرد الافتراضي (إذا لم يكن في جلسة)
    await update.message.reply_text("ℹ️ *مرحباً\\!*\nيرجى إرسال صورة لترجمتها\\.\nاستخدم الأزرار بالأسفل للتحكم في البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)