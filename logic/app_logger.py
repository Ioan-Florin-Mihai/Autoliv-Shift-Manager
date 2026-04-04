# ============================================================
# MODUL: app_logger.py - LOGGING CENTRALIZAT
# ============================================================
#
# Responsabil cu:
#   - Logarea tuturor evenimentelor importante ale aplicației
#   - Captarea și registrarea excepțiilor pentru debugging
#   - Salvare în data/app.log cu timestamp pentru audit
#
# Fișierul log:
#   - Se crează automat în data/app.log
#   - Format: [YYYY-MM-DD HH:MM:SS] context: ErrorType: error message
#   - Folosit pentru debugging și troubleshooting runtime
# ============================================================

from datetime import datetime

from logic.app_paths import DATA_DIR, ensure_directory


# Calea fisierului de log — se afla in /data/app.log
LOG_PATH = DATA_DIR / "app.log"


def log_event(message: str):
    """Adauga un mesaj cu timestamp in fisierul de log."""
    try:
        ensure_directory(DATA_DIR)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
    except OSError:
        # Fallback: scriem in stderr cand fisierul de log nu e accesibil
        import sys
        print(f"[LOG FALLBACK] {message}", file=sys.stderr)


def log_exception(context: str, exc: Exception):
    """Logheaza o exceptie cu contextul in care a aparut."""
    # Formatul: [timestamp] context: TipExceptie: mesaj
    log_event(f"{context}: {type(exc).__name__}: {exc}")
