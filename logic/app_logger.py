from datetime import datetime

from logic.app_paths import DATA_DIR, ensure_directory


LOG_PATH = DATA_DIR / "app.log"


def log_event(message: str):
    ensure_directory(DATA_DIR)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def log_exception(context: str, exc: Exception):
    log_event(f"{context}: {type(exc).__name__}: {exc}")
