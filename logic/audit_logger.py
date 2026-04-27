import json
from datetime import datetime
from pathlib import Path

from logic.app_paths import BASE_DIR
from logic.utils.io import atomic_write_json

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
    atomic_write_json(path, payload)

def _acquire_lock(lock_path: Path):
    """
    Best-effort cross-process lock to avoid lost updates when multiple
    instances append to the audit log at the same time.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            import msvcrt  # type: ignore
        except ImportError:  # pragma: no cover
            msvcrt = None

        if msvcrt is not None:  # Windows
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            return handle, ("msvcrt", msvcrt)

        try:
            import fcntl  # type: ignore
        except ImportError:  # pragma: no cover
            fcntl = None

        if fcntl is not None:  # Unix
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            return handle, ("fcntl", fcntl)

        # No lock available on this platform/runtime.
        return handle, ("none", None)
    except OSError:
        handle.close()
        raise


def _release_lock(handle, backend):
    kind, mod = backend
    try:
        if kind == "msvcrt":
            mod.locking(handle.fileno(), mod.LK_UNLCK, 1)
        elif kind == "fcntl":
            mod.flock(handle.fileno(), mod.LOCK_UN)
    finally:
        try:
            handle.close()
        except OSError:
            pass


def log_event(action: str, user: str, week: str, details: dict | None = None):
    """Adauga un eveniment in jurnalul de audit (scriere atomica, append-only, max 1000)."""
    lock_handle, backend = _acquire_lock(AUDIT_LOG_PATH.with_suffix(".lock"))
    try:
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
    finally:
        _release_lock(lock_handle, backend)


def read_recent_events(limit: int = 100, user: str | None = None, action: str | None = None) -> list[dict]:
    events = list(reversed(_read_events(AUDIT_LOG_PATH)))
    if user:
        events = [item for item in events if str(item.get("user", "")).casefold() == user.casefold()]
    if action:
        events = [item for item in events if str(item.get("action", "")).casefold() == action.casefold()]
    return events[:limit]
