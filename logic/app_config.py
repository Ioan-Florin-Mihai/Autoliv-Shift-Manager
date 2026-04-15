import json
import socket
from copy import deepcopy
from pathlib import Path
from typing import cast

from logic.app_paths import BASE_DIR
from logic.utils.io import atomic_write_json

CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "server_host": "127.0.0.1",
    "server_ip": "AUTO",
    "server_port": 8000,
    "api_key": "",
    "rotation_interval": 10,
    "refresh_interval": 5,
    "max_backups": 20,
    "auto_lock_on_publish": True,
    "max_users": 3,
    "tv_stale_seconds": 15,
    "tv_browser": "auto",
    "browser_restart_delay": 3,
    "server_restart_delay": 5,
    "log_max_bytes": 5 * 1024 * 1024,
    "log_backup_count": 5,
}
_cached_config: dict | None = None


def get_local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        sock.connect(("8.8.8.8", 80))
        ip = str(sock.getsockname()[0])
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _as_int(value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _as_ip(value, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _merge_config(raw: dict | None) -> dict:
    merged = deepcopy(DEFAULT_CONFIG)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in merged:
                merged[key] = value
    merged["server_host"] = str(merged.get("server_host") or DEFAULT_CONFIG["server_host"])
    merged["server_ip"] = _as_ip(merged.get("server_ip"), cast(str, DEFAULT_CONFIG["server_ip"]))
    merged["server_port"] = _as_int(merged.get("server_port"), cast(int, DEFAULT_CONFIG["server_port"]), 1, 65535)
    merged["api_key"] = str(merged.get("api_key") or "").strip()
    merged["rotation_interval"] = _as_int(merged.get("rotation_interval"), cast(int, DEFAULT_CONFIG["rotation_interval"]), 1, 3600)
    merged["refresh_interval"] = _as_int(merged.get("refresh_interval"), cast(int, DEFAULT_CONFIG["refresh_interval"]), 1, 3600)
    merged["max_backups"] = _as_int(merged.get("max_backups"), cast(int, DEFAULT_CONFIG["max_backups"]), 1, 500)
    merged["auto_lock_on_publish"] = _as_bool(merged.get("auto_lock_on_publish"), cast(bool, DEFAULT_CONFIG["auto_lock_on_publish"]))
    merged["max_users"] = _as_int(merged.get("max_users"), cast(int, DEFAULT_CONFIG["max_users"]), 1, 100)
    merged["tv_stale_seconds"] = _as_int(merged.get("tv_stale_seconds"), cast(int, DEFAULT_CONFIG["tv_stale_seconds"]), 5, 600)
    merged["tv_browser"] = str(merged.get("tv_browser") or DEFAULT_CONFIG["tv_browser"])
    merged["browser_restart_delay"] = _as_int(merged.get("browser_restart_delay"), cast(int, DEFAULT_CONFIG["browser_restart_delay"]), 1, 300)
    merged["server_restart_delay"] = _as_int(merged.get("server_restart_delay"), cast(int, DEFAULT_CONFIG["server_restart_delay"]), 1, 300)
    merged["log_max_bytes"] = _as_int(merged.get("log_max_bytes"), cast(int, DEFAULT_CONFIG["log_max_bytes"]), 1024, 100 * 1024 * 1024)
    merged["log_backup_count"] = _as_int(merged.get("log_backup_count"), cast(int, DEFAULT_CONFIG["log_backup_count"]), 1, 50)
    # app_password_hash este gestionat exclusiv in users.json — nu se stocheaza in config
    merged.pop("app_password_hash", None)
    return merged


def _write_config_atomic(path: Path, data: dict) -> None:
    atomic_write_json(path, data)


def ensure_config() -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _write_config_atomic(CONFIG_PATH, DEFAULT_CONFIG)
        return CONFIG_PATH
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    merged = _merge_config(raw)
    if raw != merged:
        _write_config_atomic(CONFIG_PATH, merged)
    return CONFIG_PATH


def get_config(force_reload: bool = False) -> dict:
    global _cached_config
    if _cached_config is not None and not force_reload:
        return deepcopy(_cached_config)
    ensure_config()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    _cached_config = _merge_config(raw)
    if str(_cached_config.get("server_ip", "")).strip().upper() == "AUTO":
        _cached_config["server_ip"] = get_local_ip()
    return deepcopy(_cached_config)
