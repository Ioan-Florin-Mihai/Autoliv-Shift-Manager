"""Read-only post-build verification for the portable Windows release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_DIRS = [
    "assets",
    "data",
    "backups",
    "Exports",
    "logs",
]

REQUIRED_FILES = [
    "Autoliv Shift Manager.exe",
    "config.json",
    "assets/autoliv_logo.png",
    "assets/autoliv_app.ico",
    "assets/autoliv_app_icon.png",
    "data/schedule_draft.json",
    "data/schedule_live.json",
    "data/audit_log.json",
    "data/employees.json",
    "data/ui_state.json",
]

JSON_FILES = [
    "config.json",
    "data/schedule_draft.json",
    "data/schedule_live.json",
    "data/audit_log.json",
    "data/employees.json",
    "data/ui_state.json",
]

FORBIDDEN_FILES = [
    "data/users.json",
    "data/bootstrap_admin.json",
    "data/runtime_root.txt",
    "data/planner.lock",
    "data/tv_server.lock",
    "data/audit_log.lock",
    "logs/system.log",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a built Autoliv Shift Manager dist folder.")
    parser.add_argument(
        "--dist",
        default="dist",
        help="Path to the built dist folder. Default: dist",
    )
    parser.add_argument(
        "--min-exe-mb",
        type=int,
        default=10,
        help="Minimum expected EXE size in MB. Default: 10",
    )
    return parser.parse_args()


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _failures_for_dist(dist: Path, min_exe_mb: int) -> list[str]:
    failures: list[str] = []

    if not dist.exists():
        return [f"Dist folder does not exist: {dist}"]
    if not dist.is_dir():
        return [f"Dist path is not a folder: {dist}"]

    for rel_path in REQUIRED_DIRS:
        path = dist / rel_path
        if not path.is_dir():
            failures.append(f"Missing required folder: {rel_path}")
        else:
            _ok(f"Folder exists: {rel_path}")

    for rel_path in REQUIRED_FILES:
        path = dist / rel_path
        if not path.is_file():
            failures.append(f"Missing required file: {rel_path}")
        else:
            _ok(f"File exists: {rel_path}")

    exe_path = dist / "Autoliv Shift Manager.exe"
    if exe_path.is_file():
        exe_size = exe_path.stat().st_size
        min_bytes = min_exe_mb * 1024 * 1024
        if exe_size < min_bytes:
            failures.append(
                f"EXE is unexpectedly small: {exe_size} bytes; expected at least {min_bytes} bytes"
            )
        else:
            _ok(f"EXE size is plausible: {exe_size} bytes")

    for rel_path in JSON_FILES:
        path = dist / rel_path
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"Invalid JSON in {rel_path}: {exc}")
        else:
            _ok(f"JSON parses: {rel_path}")

    for rel_path in FORBIDDEN_FILES:
        path = dist / rel_path
        if path.exists():
            failures.append(f"Sensitive/runtime file should not be shipped: {rel_path}")
        else:
            _ok(f"Not present: {rel_path}")

    return failures


def main() -> int:
    args = _parse_args()
    dist = Path(args.dist).expanduser().resolve()
    print(f"Post-build verification target: {dist}")
    print("Mode: read-only")
    failures = _failures_for_dist(dist, args.min_exe_mb)

    if failures:
        print()
        print("[FAIL] Build verification failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print()
    print("[OK] Build verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
