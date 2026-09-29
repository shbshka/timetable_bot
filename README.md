# Timetable Bot

Telegram bot for viewing group timetables, managing schedule links, and notifying users when a linked Google Sheet changes. Schedule data is fetched into timestamped local snapshots, parsed into schedule models, and cached in SQLite so normal bot requests do not call Google Sheets.

## Requirements

- Python 3.10 or newer
- A Telegram bot token
- A Google service account JSON key with read access to the timetable spreadsheets
- The service account's email shared on each Google spreadsheet

## Setup

1. Create and activate a virtual environment.
2. Install the project and optional development tools:

	```powershell
	python -m pip install -e ".[dev]"
	```

3. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`, `ADMIN_ID`, and `SERVICE_ACCOUNT_PATH`. Keep `.env` and the service-account key out of version control.
4. Set `ADMIN_ID` to the Telegram numeric user ID allowed to use admin commands.
5. Place the service-account JSON key at the configured path and share each timetable spreadsheet with the service account's email.
6. Start the bot from the project root:

	```powershell
	python main.py
	```

The bot initializes SQLite, fetches each active spreadsheet at startup, verifies that parsed rows were cached, then starts polling. The configured watcher checks for later changes and the snapshot cleanup job enforces retention. The JobQueue support is included through the `python-telegram-bot[job-queue]` dependency.

## Configuration

All settings are read from environment variables or `.env`. Relative filesystem paths are resolved from the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `ADMIN_ID` | unset | Numeric Telegram admin user ID |
| `SERVICE_ACCOUNT_PATH` | `credentials.json` | Google service-account JSON key |
| `SPREADSHEET_ID` | unset | Optional default spreadsheet ID for direct fetches |
| `DATABASE_PATH` | `src/db/timetable.db` | SQLite database path |
| `SCHEDULE_SNAPSHOTS_DIR` | `schedule_snapshots` | Directory for raw fetched-grid snapshots |
| `MAX_SCHEDULE_SNAPSHOTS` | `25` | Newest snapshots retained per spreadsheet |
| `SNAPSHOT_CLEANUP_INTERVAL_SECONDS` | `86400` | Periodic cleanup interval |
| `CHECK_INTERVAL_SECONDS` | `43200` | Schedule-change watcher interval |
| `SCHEDULE_PARSER` | `awful_uni_grid` | Registered timetable parser implementation |
| `ENVIRONMENT` | `dev` | Selects default log level |
| `LOG_LEVEL` | derived from environment | Python log level |

Snapshot retention runs both after a successful snapshot write and as a scheduled cleanup job. Snapshot JSON and database files are local runtime data and are ignored by Git.

## Bot Commands

### Users

- `/start` — register and open the group menu
- `/group` — choose a study form and year
- `/language` — choose English or Russian
- `/today`, `/tomorrow`, `/week` — view the cached schedule

### Admin

- `/admin` — show admin help
- `/attach <group> <sheet URL or ID>` — attach a timetable and immediately refresh its cache
- `/detach <group>` — remove the schedule link and stale rows for the group
- `/users <year 1-5> <HR|HRO|LR>` — list registered users in a group
- `/ban <chat_id>` and `/unban <chat_id>` — restrict or restore bot access

The `ADMIN_ID` user is exempt from the global banned-user update guard. User display names are refreshed when they use `/start`.

## Parser Architecture

`src/parser/interface.py` defines the parser protocol. Implementations live under `src/parser/implementations/`; the current `awful_uni_grid` parser handles the existing wide university timetable layout. `src/parser/registry.py` selects the implementation configured by `SCHEDULE_PARSER`.

To add another layout, implement `parse_all(grid)` and `parse(grid, target_date=None, fetch_full_week=False)`, register an instance with `register_parser("your_parser", YourParser())`, and set `SCHEDULE_PARSER=your_parser`. The old `src.parser.grid` import path remains as a compatibility facade.

## Data and Logs

- Each successful Google Sheets fetch writes a JSON snapshot containing fetch time, spreadsheet/tab metadata, formatted cell values, and notes.
- Parsed `Lecture` rows are associated with SQLite group records and read by schedule commands.
- `logs/` contains application logs; log level can be changed with `LOG_LEVEL`.
- Keep credentials and snapshots private. Snapshots may contain timetable data and cell notes.

## Development

Install the optional tools with `python -m pip install -e ".[dev]"`. Run tests with `python -m pytest`; lint with `python -m ruff check .`.
