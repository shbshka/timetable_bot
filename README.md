# Timetable Bot
_Vibecoded (yes, even the entire readme below) with passion, cursing at Copilot and fixing broken stuff after it, coffee mugs (total: fourteen), broken computer mouse (one; and thank god not it was not laptop screen), sleepless nights, and complete lack of time. If anything fails, blame GPT-5.6 Luna and not me. Made for personal use of the ex-SDC cohort of students who absolutely hate the new timetable layouts and the timeframe within which we were notified of this (no, seriously, we could've been warned in advance, couldn't we?)._
##
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

3. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and `ADMIN_ID`. Azure deployments should set `SERVICE_ACCOUNT_BASE64`; local development automatically uses `credentials.json`. Keep `.env` and service-account data out of version control.
4. Set `ADMIN_ID` to the Telegram numeric user ID allowed to use admin commands or a list of Telegram numeric user IDs separated with a comma.
5. For local development, place the service-account JSON key at `credentials.json` in the project root. For Azure, set `SERVICE_ACCOUNT_BASE64` to the base64-encoded JSON. Share each timetable spreadsheet with the service account's email.
6. Start the bot from the project root:

	```powershell
	python main.py
	```

The bot initializes SQLite, fetches each active spreadsheet at startup, verifies that parsed rows were cached, then starts polling. The configured watcher checks for later changes and the snapshot cleanup job enforces retention. The JobQueue support is included through the `python-telegram-bot[job-queue]` dependency.

## Container Deployment

The worker is packaged by [`Dockerfile`](Dockerfile) and can be run locally with the Compose manifest:

```powershell
docker compose build
docker compose up -d
```

`docker-compose.yml` runs the bot without HTTP ingress, passes credentials through environment variables, and stores SQLite data, snapshots, and logs in named volumes. Do not put production secrets in the Compose file or image; provide `TELEGRAM_BOT_TOKEN`, `ADMIN_ID`, and `SERVICE_ACCOUNT_BASE64` through the deployment secret store.

The bot also starts a minimal health endpoint on `0.0.0.0:8000` while Telegram polling is active. Azure App Service deployments should configure the app's health check to use `/` on port `8000`; the endpoint returns HTTP 200 with `ok`.

For Azure Container Apps, push the image to Azure Container Registry and create the worker without ingress, or use the Compose manifest with the Azure Container Apps Compose command supported by your Azure CLI extension. Mount Azure Files at `/app/data` and `/app/logs` when persistence across container revisions is required; otherwise SQLite, snapshots, and file logs are ephemeral. Container console logs remain available through ACA diagnostics.

## Configuration

All settings are read from environment variables or `.env`. Relative filesystem paths are resolved from the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `ADMIN_ID` | unset | Numeric Telegram admin user ID/IDs |
| `SERVICE_ACCOUNT_BASE64` | unset | Base64-encoded Google service-account JSON for Azure; local fallback uses `credentials.json` |
| `SPREADSHEET_ID` | unset | Optional default spreadsheet ID for direct fetches |
| `DATABASE_PATH` | `src/db/timetable.db` | SQLite database path |
| `SCHEDULE_SNAPSHOTS_DIR` | `schedule_snapshots` | Directory for raw fetched-grid snapshots |
| `MAX_SCHEDULE_SNAPSHOTS` | `25` | Newest snapshots retained per spreadsheet |
| `SNAPSHOT_CLEANUP_INTERVAL_SECONDS` | `86400` | Periodic cleanup interval |
| `CHECK_INTERVAL_SECONDS` | `43200` | Schedule-change watcher interval |
| `SCHEDULE_PARSER` | `awful_uni_grid` | Compatibility/default parser name; timetable ingestion uses the registered parser chain with `awful_uni_grid` last |
| `ENVIRONMENT` | `dev` | Selects default log level |
| `LOG_LEVEL` | derived from environment | Python log level |

Snapshot retention runs both after a successful snapshot write and as a scheduled cleanup job. Snapshot JSON and database files are local runtime data and are ignored by Git.

Schedule-update notifications are sent only to users who are not banned and whose
`notifications_enabled` database flag is enabled. The flag defaults to enabled, but
there is currently no user-facing command to change it.

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

The `ADMIN_ID` users is exempt from the global banned-user update guard. User display names are refreshed when they use `/start`.

## Parser Architecture

`src/parser/interface.py` defines the parser protocol. Implementations live under `src/parser/implementations/`; `four_week_grid` handles repeated four-week `Date, Time, Room, Course, Teacher, Form` blocks and `awful_uni_grid` handles the legacy wide layout. `src/parser/registry.py` tries registered parsers in order, accepts the first parser that produces lectures, and always tries `awful_uni_grid` last. The selected user's group study form is used as a fallback when a source layout does not encode `HR`, `HRO`, or `LR` in lecture rows.

To add another layout, implement `parse_all(grid)` and `parse(grid, target_date=None, fetch_full_week=False)`, register an instance with `register_parser("your_parser", YourParser())`, and set `SCHEDULE_PARSER=your_parser`. The old `src.parser.grid` import path remains as a compatibility facade.

## Data and Logs

- Each successful Google Sheets fetch writes a JSON snapshot containing fetch time, spreadsheet/tab metadata, formatted cell values, and notes. Snapshots are stored under `SCHEDULE_SNAPSHOTS_DIR/<group>/`; group names are sanitized for filesystem use, and retention is applied separately for each group and spreadsheet.
- Parsed `Lecture` rows are associated with SQLite group records and read by schedule commands.
- `logs/` contains rotating purpose-specific logs: `app/application.log`, `bot/telegram.log`, `database/database.log`, `parser/parser.log`, `google/google_sheets.log`, `admin/admin.log`, `jobs/jobs.log`, and `errors/errors.log`.
- Logs also remain visible in the console. `LOG_LEVEL` controls file and normal console verbosity; test mode keeps console output at warnings and does not create log files.
- Keep credentials and snapshots private. Snapshots may contain timetable data and cell notes.

## Development

Install the optional tools with `python -m pip install -e ".[dev]"`. Run tests with `python -m pytest`; lint with `python -m ruff check .`.

Tests live under `tests/` and mirror the production layout: parser, database, service, and utility tests are separated into matching directories. Test names describe observable behavior, and each test follows Arrange, Act, Assert phases.
