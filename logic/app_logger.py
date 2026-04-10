# ============================================================
# MODUL: app_logger.py - LOGGING CENTRALIZAT PROFESIONAL
# ============================================================
#
# Responsabil cu:
#   - Logging cu nivele (DEBUG, INFO, WARNING, ERROR, CRITICAL)
#   - RotatingFileHandler: maxim 5 MB per fisier, 3 backup-uri
#   - Fallback automat la stderr daca fisierul nu e accesibil
#   - Stack trace complet la log_exception (prin logger.exception)
#
# Fisierul log:
#   - data/app.log (rotit automat)
#   - Format: 2026-01-01 12:00:00 [LEVEL  ] mesaj
# ============================================================

import logging
import sys
from logging.handlers import RotatingFileHandler

from logic.app_config import get_config
from logic.app_paths import DATA_DIR, ensure_directory

# ── Configurare logger ─────────────────────────────────────────
_LOG_DIR = DATA_DIR.parent / "logs"
_LOG_PATH = _LOG_DIR / "system.log"
_LOGGER_NAME = "autoliv_shift_manager"
_logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    """Returneaza (si initializeaza lazy) logger-ul aplicatiei."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        # Logger deja configurat (ex: import multiplu)
        _logger = logger
        return _logger

    logger.setLevel(logging.DEBUG)
    config = get_config()

    # ── Handler fisier rotativ ─────────────────────────────────
    try:
        ensure_directory(_LOG_DIR)
        fh = RotatingFileHandler(
            _LOG_PATH,
            maxBytes=int(config.get("log_max_bytes", 5 * 1024 * 1024)),
            backupCount=int(config.get("log_backup_count", 5)),
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)
    except OSError:
        pass  # Fallback-ul stderr de mai jos acopera cazul

    # ── Handler stderr (WARNING+) — fallback si consola dev ───
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)

    _logger = logger
    return _logger


# ── API public ─────────────────────────────────────────────────

def log_event(message: str, level: str = "INFO", *args) -> None:
    """Logheza un mesaj la nivelul specificat (compatibilitate backward)."""
    lvl = getattr(logging, level.upper(), logging.INFO)
    _get_logger().log(lvl, message, *args)


def log_info(message: str, *args) -> None:
    """Inregistreaza un eveniment informational."""
    _get_logger().info(message, *args)


def log_warning(message: str, *args) -> None:
    """Inregistreaza un avertisment."""
    _get_logger().warning(message, *args)


def log_error(message: str, *args) -> None:
    """Inregistreaza o eroare non-fatala."""
    _get_logger().error(message, *args)


def log_exception(context: str, exc: Exception) -> None:
    """Inregistreaza o exceptie cu stack trace complet."""
    _get_logger().exception("%s: %s: %s", context, type(exc).__name__, exc)
