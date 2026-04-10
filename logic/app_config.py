import json
import socket
from copy import deepcopy
from pathlib import Path

from logic.app_paths import BASE_DIR

CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "server_host": "0.0.0.0",
    "server_ip": "AUTO",
    "server_port": 8000,
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
    "app_password_hash": "$2b$12$6Z/FpUJQWSBanOtVHCq2p.zItXw9jP.SrLd9OSnP/9yNHLp2zzWHa",
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
    merged["server_ip"] = _as_ip(merged.get("server_ip"), DEFAULT_CONFIG["server_ip"])
    merged["server_port"] = _as_int(merged.get("server_port"), DEFAULT_CONFIG["server_port"], 1, 65535)
    merged["rotation_interval"] = _as_int(merged.get("rotation_interval"), DEFAULT_CONFIG["rotation_interval"], 1, 3600)
    merged["refresh_interval"] = _as_int(merged.get("refresh_interval"), DEFAULT_CONFIG["refresh_interval"], 1, 3600)
    merged["max_backups"] = _as_int(merged.get("max_backups"), DEFAULT_CONFIG["max_backups"], 1, 500)
    merged["auto_lock_on_publish"] = _as_bool(merged.get("auto_lock_on_publish"), DEFAULT_CONFIG["auto_lock_on_publish"])
    merged["max_users"] = _as_int(merged.get("max_users"), DEFAULT_CONFIG["max_users"], 1, 100)
    merged["tv_stale_seconds"] = _as_int(merged.get("tv_stale_seconds"), DEFAULT_CONFIG["tv_stale_seconds"], 5, 600)
    merged["tv_browser"] = str(merged.get("tv_browser") or DEFAULT_CONFIG["tv_browser"])
    merged["browser_restart_delay"] = _as_int(merged.get("browser_restart_delay"), DEFAULT_CONFIG["browser_restart_delay"], 1, 300)
    merged["server_restart_delay"] = _as_int(merged.get("server_restart_delay"), DEFAULT_CONFIG["server_restart_delay"], 1, 300)
    merged["log_max_bytes"] = _as_int(merged.get("log_max_bytes"), DEFAULT_CONFIG["log_max_bytes"], 1024, 100 * 1024 * 1024)
    merged["log_backup_count"] = _as_int(merged.get("log_backup_count"), DEFAULT_CONFIG["log_backup_count"], 1, 50)
    merged["app_password_hash"] = str(merged.get("app_password_hash") or DEFAULT_CONFIG["app_password_hash"])
    return merged


def ensure_config() -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return CONFIG_PATH
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    merged = _merge_config(raw)
    if raw != merged:
        CONFIG_PATH.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
