# File: handlers/ui/concurrency.py
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.markdown_escaper import escape_markdown_v2

async def boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows a normal user to request a 10-minute parallel processing lease."""
    user = update.effective_user
    conc_manager = context.bot_data["concurrency_manager"]
    
    # التحقق مما إذا كان المستخدم يملك صلاحية دائمة أو إيجار نشط
    access = await conc_manager._db_store.check_user_access(user.id)
    
    if access == "permanent":
        await update.message.reply_text("✅ *أنت تمتلك صلاحية المعالجة المتوازية الدائمة\\.*", parse_mode=ParseMode.MARKDOWN_V2)
        return
        
    if access == "lease":
        await update.message.reply_text("⏳ *أنت تستخدم بالفعل خاصية التعزيز المؤقت\\.*\nاستمر في إرسال الصور\\!", parse_mode=ParseMode.MARKDOWN_V2)
        return
        
    granted = await conc_manager.request_lease(user.id)
    
    if granted:
        await update.message.reply_text(
            "🚀 *تم تفعيل التعزيز المؤقت\\!*\n\n"
            "لديك الآن *10 دقائق* لمعالجة صورك بالتوازي \\(حتى 3 صور في نفس الوقت\\)\\. أرسل صورك الآن دفعة واحدة\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "🚫 *لا توجد فتحات متاحة حالياً\\.*\n"
            "الحد الأقصى للمعالجة المتوازية مفعّل لدى مستخدمين آخرين في هذه اللحظة\\. يرجى المحاولة لاحقاً\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def set_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Super Admin command to set the global concurrency limit (1-5)."""
    access_manager = context.bot_data["access_manager"]
    if not access_manager.is_super_admin(update.effective_user.id): return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة: `/setlimit <1-5>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
        
    limit = int(args[0])
    conc_manager = context.bot_data["concurrency_manager"]
    new_limit = await conc_manager.set_global_limit(limit)
    
    await update.message.reply_text(f"⚙️ *تم تحديث الحد الأقصى للمعالجة المتوازية*\nالحد الجديد: `{new_limit}`", parse_mode=ParseMode.MARKDOWN_V2)

async def grant_parallel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Super Admin command to grant permanent parallel access to a user."""
    access_manager = context.bot_data["access_manager"]
    if not access_manager.is_super_admin(update.effective_user.id): return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة: `/grantparallel <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
        
    user_id = int(args[0])
    conc_manager = context.bot_data["concurrency_manager"]
    await conc_manager.grant_permanent_access(user_id)
    
    await update.message.reply_text(f"✅ *تم منح الصلاحية*\nالمستخدم `{escape_markdown_v2(str(user_id))}` يمتلك الآن معالجة متوازية دائمة\\.", parse_mode=ParseMode.MARKDOWN_V2)

async def revoke_parallel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Super Admin command to revoke parallel access."""
    access_manager = context.bot_data["access_manager"]
    if not access_manager.is_super_admin(update.effective_user.id): return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("⚠️ *الاستخدام غير صحيح*\nالصيغة: `/revokeparallel <ID>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
        
    user_id = int(args[0])
    conc_manager = context.bot_data["concurrency_manager"]
    await conc_manager.revoke_access(user_id)
    
    await update.message.reply_text(f"📉 *تم سحب الصلاحية*\nتم إلغاء المعالجة المتوازية من المستخدم `{escape_markdown_v2(str(user_id))}`\\.", parse_mode=ParseMode.MARKDOWN_V2)