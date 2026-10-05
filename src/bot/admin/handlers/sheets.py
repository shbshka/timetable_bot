from telegram import Update
from telegram.ext import ContextTypes

from src.bot.admin.auth import admin_only
from src.db.repository import (
    delete_pending_submission,
    detach_group_spreadsheet,
    get_group_by_name,
    get_user_schedule_context,
    get_schedule_cache_state,
    set_group_spreadsheet,
)
from src.parser.schedule_parser import refresh_schedule_cache_from_latest_snapshot, schedule_grid_hash
from src.services.google_sheets import fetch_sheet_data_with_sa
from src.utils.logger import get_logger
from src.utils.messages import get_user_msg
from src.utils.spreadsheets_link_parser import extract_sheet_id
from src.db.repository import get_pending_submission

logger = get_logger("admin")


async def _refresh_sheet_cache(
    sheet_id: str,
    fallback_level: str | None = None,
    group_name: str | None = None,
) -> bool:
    grid = await fetch_sheet_data_with_sa(sheet_id=sheet_id, group_name=group_name)
    if grid is None:
        return False

    refresh_schedule_cache_from_latest_snapshot(
        sheet_id,
        fallback_level=fallback_level,
        group_name=group_name,
    )
    cache_state = get_schedule_cache_state(sheet_id)
    return bool(
        cache_state
        and cache_state["content_hash"] == schedule_grid_hash(grid)
        and cache_state["lecture_count"] > 0
    )


@admin_only
async def handle_sheet_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes 'Approve & Attach' inline button clicks from admin chat."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) < 2:
        return

    submission_id = int(parts[1])
    admin_chat_id = update.effective_user.id

    submission = get_pending_submission(submission_id)
    if not submission:
        await query.answer(
            get_user_msg(admin_chat_id, "admin.sheet.errors.submission_not_found"),
            show_alert=True,
        )
        return

    group_id = submission["group_id"]
    group_name = submission["group_name"]
    sheet_id = submission["sheet_id"]
    user_chat_id = submission["user_chat_id"]
    group_info = get_group_by_name(group_name)
    user_group = get_user_schedule_context(user_chat_id)
    fallback_level = (
        user_group["study_form"]
        if user_group
        else group_info["study_form"]
        if group_info
        else None
    )

    if group_info and await _refresh_sheet_cache(
        sheet_id,
        fallback_level=fallback_level,
        group_name=group_name,
    ):
        set_group_spreadsheet(group_id=group_id, sheet_id=sheet_id)
        logger.info(f"Admin {update.effective_user.id} attached Sheet '{sheet_id}' to Group {group_id}")
        await query.edit_message_text(
            f"{query.message.text}\n\n"
            + get_user_msg(
                admin_chat_id,
                "admin.sheet.approved",
                sheet_id=sheet_id,
                ),
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=user_chat_id,
            text=get_user_msg(user_chat_id, "schedule.submit_link.accepted", group_name=group_name),
            parse_mode="HTML"
    )
    else:
        await query.edit_message_text(
            f"{query.message.text}\n\n"
            + get_user_msg(
                admin_chat_id,
                "admin.sheet.invalid"
            ),
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=user_chat_id,
            text=get_user_msg(user_chat_id, "schedule.submit_link.invalid", group_name=group_name),
            parse_mode="HTML"
            )



    try:
        delete_pending_submission(submission_id)
        logger.info(f"Pending submission {submission_id} deleted after processing approval.")
    except Exception as e:
        logger.error(f"Failed to delete pending submission {submission_id}: {e}", exc_info=True)

@admin_only
async def handle_sheet_rejection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes 'Reject' inline button clicks from admin chat."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) < 2:
        return

    submission_id = int(parts[1])
    admin_chat_id = update.effective_user.id

    submission = get_pending_submission(submission_id)
    if not submission:
        await query.answer(
            get_user_msg(admin_chat_id, "admin.sheet.errors.submission_not_found"),
            show_alert=True,
        )
        return

    group_id = submission["group_id"]
    group_name = submission["group_name"]
    sheet_id = submission["sheet_id"]
    user_chat_id = submission["user_chat_id"]

    logger.info(f"Admin {update.effective_user.id} rejected Sheet '{sheet_id}' for Group {group_id}")

    await query.edit_message_text(
        f"{query.message.text}\n\n"
        + get_user_msg(
            admin_chat_id, 
            "admin.sheet.rejected", 
            sheet_id=sheet_id),
        parse_mode="HTML"
    )

    await context.bot.send_message(
        chat_id=user_chat_id,
        text=get_user_msg(user_chat_id, "schedule.submit_link.rejected", group_name=group_name),
        parse_mode="HTML"
    )

    try:
        delete_pending_submission(submission_id)
        logger.info(f"Pending submission {submission_id} deleted after processing rejection.")
    except Exception as e:
        logger.error(f"Failed to delete pending submission {submission_id}: {e}", exc_info=True)


@admin_only
async def attach_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /attach <GROUP_CODE> <SHEET_URL_OR_ID>
    Overwrites old links with the new spreadsheet link.
    """
    admin_chat_id = update.effective_user.id
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.usage.attach"),
            parse_mode="HTML"
        )
        return

    group_code = context.args[0].upper()
    sheet_id = extract_sheet_id(context.args[1])

    if not sheet_id:
        await update.message.reply_text(get_user_msg(admin_chat_id, "admin.sheet.invalid"))
        return

    group_info = get_group_by_name(group_code)
    if not group_info:
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.sheet.errors.group_not_found", group_name=group_code),
            parse_mode="HTML",
        )
        return

    if await _refresh_sheet_cache(
        sheet_id,
        fallback_level=group_info["study_form"],
        group_name=group_info["group_name"],
    ):
        set_group_spreadsheet(group_id=group_info["id"], sheet_id=sheet_id)

        logger.info(f"Admin {admin_chat_id} attached sheet {sheet_id} to group {group_info['group_name']}.")

        await update.message.reply_text(
            get_user_msg(
                admin_chat_id,
                "admin.sheet.attached",
                group_name=group_info["group_name"],
                sheet_id=sheet_id,
            ),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.sheet.invalid"),
            parse_mode="HTML"
        )


@admin_only
async def detach_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Usage: /detach <GROUP_CODE>
    Removes the attached spreadsheet link from a group.
    """
    admin_chat_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(get_user_msg(admin_chat_id, "admin.usage.detach"), parse_mode="HTML")
        return

    group_code = context.args[0].upper()
    group_info = get_group_by_name(group_code)

    if not group_info:
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.sheet.errors.group_not_found", group_name=group_code),
            parse_mode="HTML",
        )
        return

    removed = detach_group_spreadsheet(group_id=group_info["id"])

    if removed:
        logger.info(f"Admin {admin_chat_id} detached sheet from group {group_info['group_name']}.")
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.sheet.detached", group_name=group_code),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            get_user_msg(admin_chat_id, "admin.sheet.not_attached", group_name=group_code),
            parse_mode="HTML",
        )