import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _configured_path(variable_name: str, default: Path) -> Path:
	configured = os.getenv(variable_name)
	path = Path(configured).expanduser() if configured else default
	return path if path.is_absolute() else PROJECT_ROOT / path


ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()

DB_PATH = _configured_path("DATABASE_PATH", PROJECT_ROOT / "src" / "db" / "timetable.db")
SNAPSHOTS_DIR = _configured_path("SCHEDULE_SNAPSHOTS_DIR", PROJECT_ROOT / "schedule_snapshots")
MAX_SCHEDULE_SNAPSHOTS = int(os.getenv("MAX_SCHEDULE_SNAPSHOTS", "25"))
SNAPSHOT_CLEANUP_INTERVAL_SECONDS = int(os.getenv("SNAPSHOT_CLEANUP_INTERVAL_SECONDS", "86400"))
SCHEDULE_PARSER = os.getenv("SCHEDULE_PARSER", "awful_uni_grid").strip().lower()
STUDY_FORMS = {"HR", "HRO", "LR"}
YEARS = {1, 2, 3, 4, 5}
SUPPORTED_USER_LOCALES = {"en", "ru"}

DEFAULT_LOG_LEVEL = "DEBUG" if ENVIRONMENT in ("dev", "test") else "INFO"
LOG_LEVEL = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

_admin_raw = os.getenv("ADMIN_ID", "")
ADMIN_ID = int(_admin_raw)

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "43200"))

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_PATH = _configured_path("SERVICE_ACCOUNT_PATH", PROJECT_ROOT / "credentials.json")

if MAX_SCHEDULE_SNAPSHOTS < 1:
	raise ValueError("MAX_SCHEDULE_SNAPSHOTS must be at least 1")
if SNAPSHOT_CLEANUP_INTERVAL_SECONDS < 1:
	raise ValueError("SNAPSHOT_CLEANUP_INTERVAL_SECONDS must be positive")