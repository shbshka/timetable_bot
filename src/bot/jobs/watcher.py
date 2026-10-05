from telegram.ext import ContextTypes

from src.db.repository import (
    enqueue_schedule_notifications,
    get_active_sheets_for_watcher,
    get_group_subscribers,
    get_pending_schedule_notifications,
    get_schedule_cache_state,
    has_pending_schedule_notifications,
    mark_schedule_notification_delivered,
    update_spreadsheet_hash,
)
from src.parser.registry import parse_with_first_successful_parser
from src.parser.schedule_parser import (
    refresh_schedule_cache_from_latest_snapshot,
    schedule_grid_hash,
)
from src.services.google_sheets import fetch_sheet_data_with_sa
from src.services.snapshots.snapshot_cleanup import cleanup_old_schedule_snapshots
from src.utils.logger import get_logger

logger = get_logger("jobs")
from src.utils.messages import get_user_msg
from src.utils.time import institution_now


async def cleanup_schedule_snapshots_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    removed = cleanup_old_schedule_snapshots()
    if removed:
        logger.info("Snapshot cleanup removed %d old files.", removed)


async def refresh_schedules_on_startup() -> None:
    """Fetch every active sheet once and verify its complete mapping before polling."""
    sheets = get_active_sheets_for_watcher()
    unique_sheets = {}
    for sheet in sheets:
        unique_sheets.setdefault(sheet["sheet_id"], []).append(sheet)

    if not unique_sheets:
        logger.info("No active spreadsheets to refresh at startup.")
        return

    for sheet_id, links in unique_sheets.items():
        try:
            grid = await fetch_sheet_data_with_sa(
                sheet_id=sheet_id,
                group_name=links[0].get("group_name"),
            )
            if grid is None:
                logger.error(f"Startup fetch failed for spreadsheet '{sheet_id}'.")
                continue

            parser_name, _, lectures = parse_with_first_successful_parser(grid)
            parsed_count = len(lectures)

            refresh_schedule_cache_from_latest_snapshot(
                sheet_id,
                fallback_level=links[0].get("study_form"),
                group_name=links[0].get("group_name"),
            )
            cache_state = get_schedule_cache_state(sheet_id)
            if (
                not cache_state
                or cache_state["content_hash"] != schedule_grid_hash(grid)
                or cache_state["lecture_count"] != parsed_count
            ):
                logger.error(
                    f"Startup cache verification failed for '{sheet_id}': "
                    f"expected {parsed_count} mapped entries."
                )
                continue

            for link in links:
                update_spreadsheet_hash(link["spreadsheet_db_id"], cache_state["content_hash"])
            logger.info(
                f"Startup schedule cache verified for '{sheet_id}': "
                f"{parsed_count} entries using parser '{parser_name}'."
            )
        except Exception as e:
            logger.error(f"Startup schedule refresh failed for '{sheet_id}': {e}", exc_info=True)


async def check_sheet_updates_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    sheets = get_active_sheets_for_watcher()
    unique_sheets = {}
    for sheet in sheets:
        unique_sheets.setdefault(sheet["sheet_id"], []).append(sheet)

    for sheet_id, links in unique_sheets.items():
        try:
            grid = await fetch_sheet_data_with_sa(
                sheet_id=sheet_id,
                group_name=links[0].get("group_name"),
            )
            if grid is None:
                continue

            refreshed = refresh_schedule_cache_from_latest_snapshot(
                sheet_id,
                fallback_level=links[0].get("study_form"),
                group_name=links[0].get("group_name"),
            )
            cache_state = get_schedule_cache_state(sheet_id)
            if not cache_state:
                continue

            for link in links:
                previous_hash = link.get("last_hash")
                if not refreshed or not previous_hash or previous_hash == cache_state["content_hash"]:
                        continue

                enqueue_schedule_notifications(
                        sheet_id=sheet_id,
                        content_hash=cache_state["content_hash"],
                        group_id=link["group_id"],
                        group_name=link["group_name"],
                        chat_ids=get_group_subscribers(link["group_id"]),
                )

            pending = get_pending_schedule_notifications(sheet_id, cache_state["content_hash"])
            for notification in pending:
                try:
                        chat_id = notification["chat_id"]
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=get_user_msg(
                                chat_id,
                                "schedule.updated",
                                group_name=notification["group_name"],
                                date_str=institution_now().strftime("%d.%m.%Y"),
                            ),
                            parse_mode="HTML",
                        )
                        mark_schedule_notification_delivered(notification["id"])
                except Exception as e:
                        logger.warning(
                            "Schedule update notification %s failed for chat %s: %s",
                            notification["id"],
                            notification["chat_id"],
                            e,
                            exc_info=True,
                        )

            if not has_pending_schedule_notifications(sheet_id, cache_state["content_hash"]):
                for link in links:
                        update_spreadsheet_hash(link["spreadsheet_db_id"], cache_state["content_hash"])
        except Exception as e:
            logger.error(f"Schedule refresh failed for spreadsheet '{sheet_id}': {e}", exc_info=True)