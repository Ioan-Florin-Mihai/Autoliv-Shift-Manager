import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from logic.app_paths import BASE_DIR

AUDIT_LOG_PATH = BASE_DIR / "data" / "audit_log.json"
MAX_AUDIT_ENTRIES = 1000


def _ensure_log_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _read_events(path: Path) -> list[dict]:
    _ensure_log_file(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _atomic_write(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def log_event(action: str, user: str, week: str, details: dict | None = None):
    """Adauga un eveniment in jurnalul de audit (scriere atomica, append-only, max 1000)."""
    events = _read_events(AUDIT_LOG_PATH)
    event = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user": user or "unknown",
        "action": action,
        "week": week,
        "details": details or {},
    }
    events.append(event)
    if len(events) > MAX_AUDIT_ENTRIES:
        events = events[-MAX_AUDIT_ENTRIES:]
    _atomic_write(AUDIT_LOG_PATH, events)


def read_recent_events(limit: int = 100, user: str | None = None, action: str | None = None) -> list[dict]:
    events = list(reversed(_read_events(AUDIT_LOG_PATH)))
    if user:
        events = [item for item in events if str(item.get("user", "")).casefold() == user.casefold()]
    if action:
        events = [item for item in events if str(item.get("action", "")).casefold() == action.casefold()]
    return events[:limit]
