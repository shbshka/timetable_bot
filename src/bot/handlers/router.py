from src.bot.handlers.schedule import handle_incoming_link_submission
from src.bot.handlers.help import handle_incoming_message_submission

async def handle_text(update, context):
    if context.user_data.get("awaiting_sheet_link"):
        await handle_incoming_link_submission(update, context)
    elif context.user_data.get("awaiting_message"):
        await handle_incoming_message_submission(update, context)