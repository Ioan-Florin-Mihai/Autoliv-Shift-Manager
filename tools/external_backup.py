"""Optional external backup helper for Autoliv Shift Manager.

This script is intentionally separate from the application save/publish flow.
It copies runtime files to a timestamped destination folder and never deletes
or modifies source data.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


RUNTIME_JSON_FILES = [
    "data/employees.json",
    "data/schedule_data.json",
    "data/schedule_draft.json",
    "data/schedule_live.json",
    "data/ui_state.json",
    "data/tv_version.json",
    "data/audit_log.json",
    "data/users.json",
    "config.json",
]

OPTIONAL_DIRS = [
    "backups",
    "logs",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a timestamped external backup.")
    parser.add_argument("destination", help="External/shared folder where the backup folder will be created.")
    parser.add_argument(
        "--source-root",
        default=".",
        help="Application root to back up. Default: current project folder.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing anything.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"invalid: {exc}"
    return "valid"


def _copy_file(source_root: Path, backup_root: Path, rel_path: str, dry_run: bool) -> str:
    src = source_root / rel_path
    if not src.is_file():
        return f"SKIP missing file: {rel_path}"
    status = _json_status(src) if src.suffix.lower() == ".json" else "not-json"
    dst = backup_root / rel_path
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return f"COPY file: {rel_path} ({status})"


def _copy_dir(source_root: Path, backup_root: Path, rel_path: str, dry_run: bool) -> list[str]:
    src = source_root / rel_path
    messages: list[str] = []
    if not src.is_dir():
        return [f"SKIP missing folder: {rel_path}"]
    files = [path for path in src.rglob("*") if path.is_file()]
    for file_path in files:
        relative = file_path.relative_to(source_root)
        dst = backup_root / relative
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dst)
        messages.append(f"COPY folder file: {relative}")
    if not files:
        messages.append(f"SKIP empty folder: {rel_path}")
    return messages


def _write_manifest(backup_root: Path, lines: list[str], dry_run: bool) -> None:
    manifest = "\n".join(
        [
            "Autoliv Shift Manager external backup",
            f"Created at: {datetime.now().isoformat(timespec='seconds')}",
            "Mode: dry-run" if dry_run else "Mode: copied",
            "",
            *lines,
            "",
        ]
    )
    if dry_run:
        print()
        print(manifest)
        return
    (backup_root / "backup_manifest.txt").write_text(manifest, encoding="utf-8")


def main() -> int:
    args = _parse_args()
    source_root = Path(args.source_root).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    backup_root = destination / f"Autoliv_Backup_{_timestamp()}"

    print(f"Source root: {source_root}")
    print(f"Destination root: {destination}")
    print(f"Backup folder: {backup_root}")
    print("Safety: source files are never deleted or modified.")
    if args.dry_run:
        print("Mode: dry-run")

    if not source_root.is_dir():
        print(f"[FAIL] Source root does not exist: {source_root}")
        return 1

    if not args.dry_run:
        try:
            backup_root.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            print(f"[FAIL] Backup folder already exists: {backup_root}")
            return 1
        except OSError as exc:
            print(f"[FAIL] Cannot create backup folder: {exc}")
            return 1

    lines: list[str] = []
    for rel_path in RUNTIME_JSON_FILES:
        lines.append(_copy_file(source_root, backup_root, rel_path, args.dry_run))
    for rel_path in OPTIONAL_DIRS:
        lines.extend(_copy_dir(source_root, backup_root, rel_path, args.dry_run))

    for line in lines:
        print(line)

    try:
        _write_manifest(backup_root, lines, args.dry_run)
    except OSError as exc:
        print(f"[FAIL] Backup copied but manifest could not be written: {exc}")
        return 1

    print()
    print("[OK] Dry-run completed." if args.dry_run else "[OK] External backup completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
