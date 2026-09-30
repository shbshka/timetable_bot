from datetime import datetime

from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.admin.auth import admin_only
from src.db.repository import (
    get_group_by_form_and_year,
    get_users_for_group,
    set_user_banned,
)
from src.utils.messages import get_user_msg
from config import STUDY_FORMS, YEARS


@admin_only
async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.effective_message.reply_text(get_user_msg(chat_id, "admin.help"), parse_mode="HTML")


@admin_only
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if len(context.args) != 2:
        await update.effective_message.reply_text(get_user_msg(chat_id, "admin.users_usage"), parse_mode="HTML")
        return

    try:
        course_year = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(get_user_msg(chat_id, "admin.users_usage"), parse_mode="HTML")
        return

    study_form = context.args[1].upper()
    if course_year not in YEARS or study_form not in STUDY_FORMS:
        await update.effective_message.reply_text(get_user_msg(chat_id, "admin.users_usage"), parse_mode="HTML")
        return

    now = datetime.now()
    academic_start_year = now.year if now.month >= 8 else now.year - 1
    enrollment_year = academic_start_year - course_year + 1
    group = get_group_by_form_and_year(study_form=study_form, enrollment_year=enrollment_year)
    if not group:
        await update.effective_message.reply_text(
            get_user_msg(
                chat_id,
                "admin.group_not_found",
                course_year=course_year,
                study_form=study_form,
                enrollment_year=enrollment_year,
            ),
            parse_mode="HTML",
        )
        return

    users = get_users_for_group(group["id"])
    if not users:
        await update.effective_message.reply_text(
            get_user_msg(chat_id, "admin.users_empty", group_name=group["group_name"]),
            parse_mode="HTML",
        )
        return

    header = get_user_msg(
        chat_id,
        "admin.users_header",
        group_name=group["group_name"],
        count=len(users),
    )
    for offset in range(0, len(users), 25):
        lines = []
        for user in users[offset : offset + 25]:
            display_name = user["first_name"] or user["username"] or "Unknown"
            username = f" (@{user['username']})" if user["username"] else ""
            status = get_user_msg(chat_id, "admin.banned_status") if user["is_banned"] else ""
            lines.append(
                f"• <b>{escape(display_name)}</b> {escape(username)} — "
                f"<code>{user['chat_id']}</code> {status}"
            )
        message = f"{header}\n" + "\n".join(lines) if offset == 0 else "\n".join(lines)
        await update.effective_message.reply_text(message, parse_mode="HTML")


@admin_only
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_chat_id = update.effective_chat.id
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text(get_user_msg(admin_chat_id, "admin.ban_usage"), parse_mode="HTML")
        return

    chat_id = int(context.args[0])
    if chat_id <= 0:
        await update.effective_message.reply_text(get_user_msg(admin_chat_id, "admin.ban_usage"), parse_mode="HTML")
        return

    if set_user_banned(chat_id, True):
        message_key = "admin.user_banned"
    else:
        message_key = "admin.user_already_banned"

    await update.effective_message.reply_text(
        get_user_msg(admin_chat_id, message_key, chat_id=chat_id),
            parse_mode="HTML",
    )


@admin_only
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_chat_id = update.effective_chat.id
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text(get_user_msg(admin_chat_id, "admin.ban_usage"), parse_mode="HTML")
        return

    chat_id = int(context.args[0])
    if chat_id <= 0:
        await update.effective_message.reply_text(get_user_msg(admin_chat_id, "admin.ban_usage"), parse_mode="HTML")
        return

    if set_user_banned(chat_id, False):
        message_key = "admin.user_unbanned"
    else:
        message_key = "admin.user_not_banned"
    await update.effective_message.reply_text(
        get_user_msg(admin_chat_id, message_key, chat_id=chat_id),
            parse_mode="HTML",
    )
