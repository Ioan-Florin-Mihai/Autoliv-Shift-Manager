from __future__ import annotations

import json

from logic.app_logger import log_info
from logic.app_paths import DATA_DIR, ensure_directory
from logic.utils.io import atomic_write_json

TV_VERSION_FILE = DATA_DIR / "tv_version.json"


def load_tv_version() -> int:
    try:
        payload = json.loads(TV_VERSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    version = payload.get("version", 0) if isinstance(payload, dict) else 0
    try:
        return max(0, int(version))
    except (TypeError, ValueError):
        return 0


def _write_tv_version(version: int) -> int:
    ensure_directory(TV_VERSION_FILE.parent)
    atomic_write_json(TV_VERSION_FILE, {"version": int(version)})
    return int(version)


def trigger_tv_update() -> int:
    version = load_tv_version() + 1
    _write_tv_version(version)
    log_info("[PUBLISH] Trigger TV update")
    return version