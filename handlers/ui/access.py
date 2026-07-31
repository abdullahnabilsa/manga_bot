# File: handlers/ui/access.py
from __future__ import annotations
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.markdown_escaper import escape_markdown_v2

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not await access_manager.is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للمشرفين فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة الصحيحة: `/adduser <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    user_id = int(args[0])
    escaped_id = escape_markdown_v2(str(user_id))
    added = await access_manager.add_user(user_id)
    
    if added:
        await update.message.reply_text(f"✅ *تمت الإضافة بنجاح*\nتم منح المستخدم `{escaped_id}` صلاحية استخدام البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(f"ℹ️ *معلومات*\nالمستخدم `{escaped_id}` موجود مسبقاً في القائمة أو أنه مشرف\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not await access_manager.is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للمشرفين فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة الصحيحة: `/removeuser <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    user_id = int(args[0])
    escaped_id = escape_markdown_v2(str(user_id))
    removed = await access_manager.remove_user(user_id)
    
    if removed:
        await update.message.reply_text(f"🗑️ *تم الحذف بنجاح*\nتم إلغاء صلاحية المستخدم `{escaped_id}`\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(f"⚠️ *غير موجود*\nالمستخدم `{escaped_id}` غير موجود في قائمة المستخدمين\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not access_manager.is_super_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للسوبر أدمن فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة الصحيحة: `/addadmin <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    user_id = int(args[0])
    escaped_id = escape_markdown_v2(str(user_id))
    added = await access_manager.add_admin(user_id)
    
    if added:
        await update.message.reply_text(f"👑 *تمت الترقية بنجاح*\nأصبح المستخدم `{escaped_id}` مشرفاً في البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(f"ℹ️ *معلومات*\nالمستخدم `{escaped_id}` مشرف مسبقاً أو أنه السوبر أدمن\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not access_manager.is_super_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للسوبر أدمن فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة الصحيحة: `/removeadmin <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    user_id = int(args[0])
    escaped_id = escape_markdown_v2(str(user_id))
    removed = await access_manager.remove_admin(user_id)
    
    if removed:
        await update.message.reply_text(f"📉 *تمت الإزالة بنجاح*\nتم سحب صلاحية المشرف من `{escaped_id}`\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(f"⚠️ *غير موجود*\nالمستخدم `{escaped_id}` ليس مشرفاً أو أنه السوبر أدمن \\(لا يمكن حذفه\\)\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not await access_manager.is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للمشرفين فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    users = await access_manager.get_users()
    admins = await access_manager.get_admins()
    # تم إصلاح الخطأ هنا: استخدام القائمة _super_admin_ids بدلاً من المتغير المفرد
    super_admin_ids = access_manager._super_admin_ids
    join_status = "مفتوح 🟢" if await access_manager.is_join_requests_open() else "مغلق 🔴"
    
    text = "📋 *قائمة الصلاحيات*\n\n"
    text += f"🚪 *حالة باب الانضمام:* {join_status}\n\n"
    text += "👑 *المشرفون:*\n"
    for i, adm in enumerate(admins, 1):
        escaped_adm = escape_markdown_v2(adm)
        tag = "السوبر أدمن" if str(adm) in super_admin_ids else "مشرف"
        escaped_tag = escape_markdown_v2(tag)
        text += f"{i}\\. `{escaped_adm}` \\({escaped_tag}\\)\n"
        
    text += "\n👤 *المستخدمون العاديون:*\n"
    if not users:
        text += "_لا يوجد مستخدمون عاديون بعد_\\.\n"
    for i, usr in enumerate(users, 1):
        escaped_usr = escape_markdown_v2(usr)
        text += f"{i}\\. `{escaped_usr}`\n"
        
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

async def open_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not await access_manager.is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للمشرفين فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    await access_manager.set_join_requests(True)
    await update.message.reply_text("🟢 *تم فتح باب الانضمام\\.*\nأي مستخدم جديد يضغط /start سيتم إرسال طلبه إليك\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def close_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    access_manager = context.bot_data["access_manager"]
    if not await access_manager.is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر مخصص للمشرفين فقط\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    
    await access_manager.set_join_requests(False)
    await update.message.reply_text("🔴 *تم إغلاق باب الانضمام\\.*\nلن يستلم البوت أي طلبات جديدة، وسيتم تجاهل المستخدمين الجدد بصمت لتوفير الموارد\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def handle_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    access_manager = context.bot_data["access_manager"]
    
    if not await access_manager.is_admin(query.from_user.id):
        return
        
    data = query.data
    action, user_id_str = data.split(":")
    user_id = int(user_id_str)
    
    admin_name = escape_markdown_v2(query.from_user.first_name or "مشرف")
    
    if action == "accept_req":
        await access_manager.add_user(user_id)
        await query.edit_message_text(f"✅ *تم قبول الطلب\\.*\nتمت إضافة المستخدم `{escape_markdown_v2(user_id_str)}` بواسطة {admin_name}\\.", parse_mode=ParseMode.MARKDOWN_V2)
        try:
            await context.bot.send_message(chat_id=user_id, text="🎉 *مبروك\\!*\nتم قبول طلب انضمامك\\. يمكنك الآن استخدام البوت بحرية\\.\nأرسل /start للبدء\\.", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception: pass
    elif action == "reject_req":
        await query.edit_message_text(f"❌ *تم رفض الطلب\\.*\nتم رفض المستخدم `{escape_markdown_v2(user_id_str)}` بواسطة {admin_name}\\.", parse_mode=ParseMode.MARKDOWN_V2)
        try:
            await context.bot.send_message(chat_id=user_id, text="🚫 للأسف، تم رفض طلب انضمامك من قبل إدارة البوت\\.", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception: pass