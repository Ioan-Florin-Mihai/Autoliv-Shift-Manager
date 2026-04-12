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
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
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
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=indent)
            tmp.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
