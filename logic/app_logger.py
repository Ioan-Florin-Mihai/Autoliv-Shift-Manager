# ============================================================
# MODUL: app_logger.py
# Responsabil cu logarea evenimentelor si exceptiilor aplicatiei
# intr-un fisier app.log din folderul /data/.
# ============================================================

from datetime import datetime

from logic.app_paths import DATA_DIR, ensure_directory


# Calea fisierului de log — se afla in /data/app.log
LOG_PATH = DATA_DIR / "app.log"


def log_event(message: str):
    """Adauga un mesaj cu timestamp in fisierul de log."""
    ensure_directory(DATA_DIR)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def log_exception(context: str, exc: Exception):
    """Logheaza o exceptie cu contextul in care a aparut."""
    # Formatul: [timestamp] context: TipExceptie: mesaj
    log_event(f"{context}: {type(exc).__name__}: {exc}")
