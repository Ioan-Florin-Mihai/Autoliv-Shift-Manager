"""Read-only support bundle generator for Autoliv Shift Manager."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


SECRET_KEYS = {
    "api_key",
    "password",
    "password_hash",
    "must_change_password",
}

JSON_FILES = [
    "config.json",
    "data/employees.json",
    "data/schedule_data.json",
    "data/schedule_draft.json",
    "data/schedule_live.json",
    "data/ui_state.json",
    "data/tv_version.json",
    "data/audit_log.json",
    "data/users.json",
]

TEXT_FILES = [
    "README.md",
    "logs/system.log",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a sanitized support bundle.")
    parser.add_argument("--source-root", default=".", help="Application root. Default: current folder.")
    parser.add_argument("--output-root", default="support_bundles", help="Output folder.")
    parser.add_argument("--log-lines", type=int, default=200, help="Recent log lines to include. Default: 200")
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _json_summary(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "valid_json": False,
    }
    if not path.exists():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    result["valid_json"] = True
    if isinstance(data, dict):
        result["top_level_keys"] = sorted(str(key) for key in data.keys())
        if isinstance(data.get("weeks"), dict):
            result["week_count"] = len(data["weeks"])
        if isinstance(data.get("employees"), list):
            result["employee_count"] = len(data["employees"])
    elif isinstance(data, list):
        result["item_count"] = len(data)
    return result


def _safe_json_payload(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return json.dumps({"error": str(exc)}, indent=2)
    return json.dumps(_redact(data), ensure_ascii=False, indent=2)


def _tail_text(path: Path, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"Could not read {path.name}: {exc}\n"
    return "\n".join(lines[-max_lines:]) + "\n"


def _run_git(args: list[str], source_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=source_root,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"git unavailable: {exc}"
    output = completed.stdout.strip() or completed.stderr.strip()
    return output[:4000]


def _metadata(source_root: Path) -> dict[str, Any]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "git_commit": _run_git(["rev-parse", "--short", "HEAD"], source_root),
        "git_status_short": _run_git(["status", "--short"], source_root),
    }


def main() -> int:
    args = _parse_args()
    source_root = Path(args.source_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    bundle_name = f"Autoliv_Support_Bundle_{_timestamp()}.zip"
    bundle_path = output_root / bundle_name

    if not source_root.is_dir():
        print(f"[FAIL] Source root does not exist: {source_root}")
        return 1

    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[FAIL] Cannot create output folder: {exc}")
        return 1

    summaries = {rel_path: _json_summary(source_root / rel_path) for rel_path in JSON_FILES}
    metadata = _metadata(source_root)

    try:
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("metadata.json", json.dumps(metadata, indent=2))
            bundle.writestr("json_summary.json", json.dumps(summaries, indent=2))

            for rel_path in JSON_FILES:
                path = source_root / rel_path
                if path.exists():
                    bundle.writestr(f"sanitized/{rel_path}", _safe_json_payload(path))

            for rel_path in TEXT_FILES:
                path = source_root / rel_path
                if path.exists():
                    if rel_path == "logs/system.log":
                        bundle.writestr("logs/system_tail.log", _tail_text(path, args.log_lines))
                    else:
                        bundle.write(path, rel_path)
    except OSError as exc:
        print(f"[FAIL] Could not create support bundle: {exc}")
        return 1

    print(f"[OK] Support bundle created: {bundle_path}")
    print("Secrets are redacted where recognized: api_key, password, password_hash.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
