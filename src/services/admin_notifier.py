from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from html import escape
from config import ADMIN_ID
from src.db.repository import get_group_by_name
from src.utils.logger import logger
from src.utils.spreadsheets_link_parser import extract_sheet_id
from src.utils.messages import get_user_msg
from src.db.repository import create_pending_submission


async def forward_message_to_admin(
    bot: Bot,
    user_chat_id: int,
    user_name: str,
    user_username: str, 
    group_name: str,
    link_text: str
) -> bool:
    """Forwards sheet link to ADMIN_ID with approve and reject buttons."""
    if not ADMIN_ID:
        logger.error("ADMIN_ID is not configured!")
        return False

    sheet_id = extract_sheet_id(link_text)
    group_info = get_group_by_name(group_name)

    message_text = get_user_msg(
        ADMIN_ID,
        "admin.forwards.link.new_submission",
        user_name=user_name,
        user_username=user_username,
        user_chat_id=user_chat_id,
        group_name=group_name,
        sheet_id=sheet_id or "N/A",
        link_text=link_text
    )

    keyboard = []
    if sheet_id and group_info:
        sub_id = create_pending_submission(
            group_id=group_info["id"],
            group_name=group_name,
            sheet_id=sheet_id,
            user_chat_id=user_chat_id
        )

        keyboard.append([
            InlineKeyboardButton(
                get_user_msg(ADMIN_ID, "admin.forwards.link.approve_button"),
                callback_data = f"approve_sheet:{sub_id}"
            ),
            InlineKeyboardButton(
                get_user_msg(ADMIN_ID, "admin.forwards.link.reject_button"),
                callback_data=f"reject_sheet:{sub_id}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send link to admin: {e}", exc_info=True)
        return False


async def notify_admin_of_error(bot: Bot, error_message: str) -> None:
    """Sends an error notification to the admin."""
    if not ADMIN_ID:
        logger.error("ADMIN_ID is not configured!")
        return

    error_message = escape(error_message)

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=get_user_msg(ADMIN_ID, "admin.forwards.error.error_occurred", error_message=error_message),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin of error: {e}", exc_info=True)