from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.db.repository import get_group_by_form_and_year, set_user_group
from src.utils.messages import get_user_msg
from src.parser.academic_year import enrollment_year
from src.bot.keyboards.group import form_selection_keyboard, year_selection_keyboard

from config import STUDY_FORMS

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

    selected_form = query.data.split(":")[1]
    context.user_data["study_form"] = selected_form

    reply_markup = year_selection_keyboard()

    await query.edit_message_text(
        get_user_msg(update.effective_chat.id, "group.choose_form.step_2", selected_form=selected_form),
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def handle_year_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculates enrollment year, retrieves group_id from DB, and updates user record."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    study_form = context.user_data.get("study_form")

    if not study_form:
        await query.edit_message_text(get_user_msg(chat_id, "error.session_expired"))
        return

    year_num = int(query.data.split(":")[1])
    group_enrollment_year = enrollment_year(year_num)

    group_info = get_group_by_form_and_year(study_form=study_form, enrollment_year=group_enrollment_year)

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
        get_user_msg(chat_id, "group.success", study_form=study_form, year_num=year_num, enrollment_year=group_enrollment_year, group_name=group_name),
        parse_mode="HTML"
    )


def register_group_handlers(app) -> None:
    """Registers handlers for group selection flow into the Application."""
    app.add_handler(CommandHandler("group", choose_form_command))
    app.add_handler(CallbackQueryHandler(handle_form_selection, pattern=r"^set_form:"))
    app.add_handler(CallbackQueryHandler(handle_year_selection, pattern=r"^set_year:"))