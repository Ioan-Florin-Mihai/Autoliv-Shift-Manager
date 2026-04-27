"""Minimal single-instance locking for internal stability.

Prevents two concurrent processes from writing the same JSON files and
clobbering user data. This is intentionally simple and best-effort.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logic.app_paths import DATA_DIR


@dataclass(frozen=True)
class ProcessLock:
    handle: object
    path: Path
    backend: str


def try_acquire_process_lock(name: str) -> ProcessLock | None:
    """Acquire a cross-process lock file for *name*.

    Returns a ProcessLock object that must be kept alive for the duration
    of the process. Returns None if another instance holds the lock.
    """
    safe_name = "".join(ch for ch in (name or "").strip() if ch.isalnum() or ch in ("-", "_")).strip() or "app"
    lock_path = DATA_DIR / f"{safe_name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    handle = lock_path.open("a+", encoding="utf-8")
    try:
        # Windows
        try:
            import msvcrt  # type: ignore
        except ImportError:
            msvcrt = None
        if msvcrt is not None:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                handle.close()
                return None
            return ProcessLock(handle=handle, path=lock_path, backend="msvcrt")

        # Unix
        try:
            import fcntl  # type: ignore
        except ImportError:
            fcntl = None
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return None
            return ProcessLock(handle=handle, path=lock_path, backend="fcntl")

        # Fallback: no locking available, assume single instance.
        return ProcessLock(handle=handle, path=lock_path, backend="none")
    except OSError:
        try:
            handle.close()
        except OSError:
            pass
        raise
