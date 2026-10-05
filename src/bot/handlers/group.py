from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from config import MAJORS, STUDY_FORMS, YEARS
from src.bot.keyboards.group import (
    form_selection_keyboard,
    major_selection_keyboard,
    year_selection_keyboard,
)
from src.db.repository import get_group_by_form_and_year, set_user_group
from src.parser.academic_year import enrollment_year
from src.utils.messages import get_user_msg


async def choose_form_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point; Sends inline keyboard buttons to choose a study form."""
    chat_id = update.effective_chat.id
    reply_markup = form_selection_keyboard(STUDY_FORMS)
    
    if update.message:
        await update.message.reply_text(get_user_msg(chat_id, "group.choose_form.step_1"), reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(get_user_msg(chat_id, "group.choose_form.step_1"), reply_markup=reply_markup)


async def handle_form_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stores study_form in context.user_data and prompts for study year."""
    query = update.callback_query
    await query.answer()

    study_form = query.data.split(":")[1]
    context.user_data["study_form"] = study_form

    reply_markup = year_selection_keyboard(YEARS)

    await query.edit_message_text(
        get_user_msg(update.effective_chat.id, "group.choose_form.step_2", selected_form=study_form),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def handle_year_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculates enrollment year, retrieves group_id from DB, and updates user record."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    study_form = context.user_data.get("study_form")
    selected_year = int(query.data.split(":")[1])

    if not study_form:
        await query.edit_message_text(get_user_msg(chat_id, "error.session_expired"))
        return

    context.user_data["selected_year"] = selected_year

    reply_markup = major_selection_keyboard(MAJORS)

    await query.edit_message_text(
        get_user_msg(chat_id, "group.choose_form.step_3", selected_form=study_form, selected_year=selected_year),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def handle_major_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles major selection and updates user group accordingly."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    study_form = context.user_data.get("study_form")
    selected_year = context.user_data.get("selected_year")
    #TODO: Add major to database when connected functionality is implemented
    major = query.data.split(":")[1]

    if not study_form or not selected_year:
        await query.edit_message_text(get_user_msg(chat_id, "error.session_expired"))
        return

    group_info = get_group_by_form_and_year(study_form=study_form, enrollment_year=enrollment_year(selected_year))

    if not group_info:
        await query.edit_message_text(
            get_user_msg(chat_id, "group.errors.not_found"),
            parse_mode="HTML"
        )
        return

    group_id = group_info["id"]
    group_name = group_info["group_name"]

    set_user_group(chat_id, group_id)

    context.user_data.clear()

    await query.edit_message_text(
        get_user_msg(chat_id, "group.success", study_form=study_form, year_num=selected_year, enrollment_year=enrollment_year(selected_year), group_name=group_name),
        parse_mode="HTML"
    )


def register_group_handlers(app) -> None:
    """Registers handlers for group selection flow into the Application."""
    app.add_handler(CommandHandler("group", choose_form_command))
    app.add_handler(CallbackQueryHandler(handle_form_selection, pattern=r"^set_form:"))
    app.add_handler(CallbackQueryHandler(handle_year_selection, pattern=r"^set_year:"))
    app.add_handler(CallbackQueryHandler(handle_major_selection, pattern=r"^set_major:"))