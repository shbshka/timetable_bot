from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.db.repository import get_user_locale, get_user_schedule_context
from src.parser.schedule_parser import get_cached_schedule
from src.services.admin_notifier import forward_message_to_admin, notify_admin_of_error
from src.utils.formatter import format_daily_schedule, format_weekly_schedule
from src.utils.logger import get_logger

logger = get_logger("bot")
from src.utils.messages import get_user_msg


async def _get_schedule_for_user(chat_id: int):
    """
    Helper function to validate user registration and fetch their active schedule context.
    Returns (user_context, None) on success, or (None, error_message) on failure.
    """
    context = get_user_schedule_context(chat_id)

    if not context:
        return None, get_user_msg(chat_id, "group.errors.not_chosen")

    if not context.get("sheet_id"):
        group_name = context.get("group_name", "your group")
        return None, get_user_msg(chat_id, "schedule.errors.not_found", group_name=group_name)

    return context, None


async def handle_incoming_link_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catches incoming text messages when a user is prompted to submit a link.
    Forwards valid Google Sheets links to ADMIN_ID.
    """
    group_name = context.user_data.get("awaiting_sheet_link")
    if not group_name or not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if "docs.google.com/spreadsheets" in text:
        chat_id = update.effective_chat.id
        user_name = update.effective_user.first_name or "Student"
        username = update.effective_user.username or "N/A"

        success = await forward_message_to_admin(
            bot=context.bot,
            user_chat_id=chat_id,
            user_name=user_name,
            user_username=username,
            group_name=group_name,
            link_text=text
        )

        context.user_data.pop("awaiting_sheet_link", None)

        if success:
                await update.message.reply_text(
                    get_user_msg(chat_id, "schedule.submit_link.success", group_name=group_name),
                    parse_mode="HTML"
                )
        else:
                await update.message.reply_text(
                    get_user_msg(chat_id, "schedule.errors.notification_failed"),
                    parse_mode="HTML"
                )


async def render_daily_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, target_date: datetime) -> None:
    """
    Unified renderer for daily schedule with day-by-day pagination buttons.
    Edits existing message if triggered by Inline Button, or sends a new reply for Commands.
    """
    chat_id = update.effective_chat.id
    user_context, error_msg = await _get_schedule_for_user(chat_id)

    if error_msg:
        group_context = get_user_schedule_context(chat_id)

        if group_context and not group_context.get("sheet_id"):
            group_name = group_context.get("group_name", "your group")
            context.user_data["awaiting_sheet_link"] = group_name
            prompt_text = get_user_msg(chat_id, "schedule.errors.not_found", group_name=group_name)

            if update.callback_query:
                    await update.callback_query.edit_message_text(prompt_text, parse_mode="HTML")
            elif update.effective_message:
                    await update.effective_message.reply_text(prompt_text, parse_mode="HTML")
            return

        if update.callback_query:
                await update.callback_query.edit_message_text(error_msg, parse_mode="HTML")
        elif update.effective_message:
                await update.effective_message.reply_text(error_msg, parse_mode="HTML")
        return

    group_name = user_context["group_name"]
    sheet_id = user_context["sheet_id"]

    try:
        schedule = get_cached_schedule(
            sheet_id=sheet_id,
            group_id=user_context["group_id"],
            target_date=target_date,
        )

        response_text = format_daily_schedule(
            group_name=group_name,
            date=target_date,
            schedule=schedule,
            locale=get_user_locale(chat_id),
        )

        prev_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)

        prev_callback = f"cmd_day:{prev_date.strftime('%Y-%m-%d')}"
        next_callback = f"cmd_day:{next_date.strftime('%Y-%m-%d')}"

        keyboard = [
            [
                InlineKeyboardButton(f"⬅️ {prev_date.strftime('%d.%m')}", callback_data=prev_callback),
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today"),
                InlineKeyboardButton(f"{next_date.strftime('%d.%m')} ➡️", callback_data=next_callback),
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_week"), callback_data="cmd_week")
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                    await update.callback_query.edit_message_text(
                        response_text, reply_markup=reply_markup, parse_mode="HTML"
                    )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif update.effective_message:
                await update.effective_message.reply_text(
                    response_text, reply_markup=reply_markup, parse_mode="HTML"
                )

    except Exception as e:
        error_msg = f"Error fetching schedule for date {target_date} in chat_id {chat_id}: {e}"
        logger.error(error_msg, exc_info=True)
        fail_msg = get_user_msg(chat_id, "error.schedule_fetch_failed")
        await notify_admin_of_error(context.bot, error_msg)
        if update.callback_query:
            await update.callback_query.edit_message_text(fail_msg)
        elif update.effective_message:
            await update.effective_message.reply_text(fail_msg)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /today command."""
    await render_daily_schedule(update, context, datetime.now())


async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /tomorrow command."""
    await render_daily_schedule(update, context, datetime.now() + timedelta(days=1))


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /week command."""
    chat_id = update.effective_chat.id
    user_context, error_msg = await _get_schedule_for_user(chat_id)

    if error_msg:
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg, parse_mode="HTML")
        elif update.effective_message:
            await update.effective_message.reply_text(error_msg, parse_mode="HTML")
        return

    group_name = user_context["group_name"]
    sheet_id = user_context["sheet_id"]

    try:
        weekly_schedule = get_cached_schedule(
            sheet_id=sheet_id,
            group_id=user_context["group_id"],
            fetch_full_week=True,
        )
        response_text = format_weekly_schedule(
            group_name=group_name,
            weekly_schedule=weekly_schedule,
            locale=get_user_locale(chat_id),
        )

        keyboard = [
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_today"), callback_data="cmd_today"),
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_tomorrow"), callback_data="cmd_tomorrow")
            ],
            [
                InlineKeyboardButton(get_user_msg(chat_id, "btns.btn_home"), callback_data="cmd_home")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    response_text, reply_markup=reply_markup, parse_mode="HTML"
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise e
        elif update.effective_message:
            await update.effective_message.reply_text(
                response_text, reply_markup=reply_markup, parse_mode="HTML"
            )

    except Exception as e:
        error_msg = f"Error fetching weekly schedule for chat_id {chat_id}: {e}"
        logger.error(error_msg, exc_info=True)
        fail_msg = get_user_msg(chat_id, "error.schedule_fetch_failed")
        await notify_admin_of_error(context.bot, error_msg)
        if update.callback_query:
            await update.callback_query.edit_message_text(fail_msg)
        elif update.effective_message:
            await update.effective_message.reply_text(fail_msg)


async def handle_schedule_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline navigation buttons including pagination (e.g., 'cmd_day:2026-09-26')."""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "cmd_today":
        await render_daily_schedule(update, context, datetime.now())
    elif action == "cmd_tomorrow":
        await render_daily_schedule(update, context, datetime.now() + timedelta(days=1))
    elif action == "cmd_week":
        await week_command(update, context)
    elif action.startswith("cmd_day:"):
        date_str = action.split(":", 1)[1]
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            await render_daily_schedule(update, context, target_date)
        except ValueError:
            logger.error(f"Invalid date format in callback_data: {date_str}")


def register_schedule_handlers(app) -> None:
    """Registers schedule command and callback handlers into the Application."""
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("tomorrow", tomorrow_command))
    app.add_handler(CommandHandler("week", week_command))
    
    app.add_handler(CallbackQueryHandler(handle_schedule_callbacks, pattern="^cmd_(today|tomorrow|week|day:)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_link_submission))