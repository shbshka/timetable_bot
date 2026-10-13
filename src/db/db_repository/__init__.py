# import importlib.util
# from pathlib import Path

# from config import DB_PATH as DB_PATH

# _legacy_path = Path(__file__).resolve().parent.parent / "repository.py"
# _legacy_spec = importlib.util.spec_from_file_location("_timetable_repository", _legacy_path)
# if _legacy_spec is None or _legacy_spec.loader is None:
#     raise ImportError(f"Could not load repository implementation from {_legacy_path}")
# _legacy_module = importlib.util.module_from_spec(_legacy_spec)
# _legacy_spec.loader.exec_module(_legacy_module)

# for _name in dir(_legacy_module):
#     if not _name.startswith("_"):
#         globals()[_name] = getattr(_legacy_module, _name)