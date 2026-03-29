import shutil
import sys
from pathlib import Path


def get_app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


APP_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
DATA_DIR = APP_DIR / "data"
EXPORT_DIR = APP_DIR / "Exports"
ASSETS_DIR = APP_DIR / "assets"


def ensure_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def ensure_runtime_file(relative_path: str):
    target_path = APP_DIR / relative_path
    source_path = BUNDLE_DIR / relative_path

    ensure_directory(target_path.parent)
    if not target_path.exists() and source_path.exists():
        shutil.copy2(source_path, target_path)

    return target_path

