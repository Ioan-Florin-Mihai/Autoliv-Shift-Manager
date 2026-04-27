"""Atomic JSON file writing utility.

Provides a single ``atomic_write_json`` function that replaces the duplicated
tempfile → fdopen → os.replace pattern formerly scattered across:
  schedule_store, auth, app_config, employee_store, personnel_manager,
  audit_logger, and tv_update.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, indent: int = 2, replace_retries: int = 3) -> None:
    """Write *data* as JSON to *path* atomically.

    The write is crash-safe: data is first flushed to a temporary file in the
    same directory, then atomically moved over the target via ``os.replace``.

    Parameters
    ----------
    path:
        Destination file (created/overwritten).
    data:
        Any JSON-serialisable object (``dict``, ``list``, ``int``, …).
    indent:
        JSON indentation level (default ``2``).
    replace_retries:
        Number of extra retries for the final ``os.replace`` step (default ``3``).
        Useful on Windows when antivirus/indexers temporarily lock the destination.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=indent)
            tmp.write("\n")
            tmp.flush()
            try:
                os.fsync(tmp.fileno())
            except OSError:
                pass
        last_exc: Exception | None = None
        for attempt in range(replace_retries + 1):
            try:
                os.replace(tmp_path, path)
                last_exc = None
                break
            except OSError as exc:
                last_exc = exc
                # Common on Windows: destination is temporarily locked.
                is_lock_related = isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32, 33}
                if attempt >= replace_retries or not is_lock_related:
                    break
                time.sleep(0.05 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
    except (OSError, TypeError, ValueError):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
