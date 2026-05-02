"""Clean generated runtime files from the built dist folder only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


RUNTIME_FILES = [
    "data/users.json",
    "data/bootstrap_admin.json",
    "data/runtime_root.txt",
    "data/planner.lock",
    "data/tv_server.lock",
    "data/audit_log.lock",
    "logs/system.log",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove known runtime-only files from a generated dist folder."
    )
    parser.add_argument("--dist", default="dist", help="Generated dist folder. Default: dist")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would be removed.")
    return parser.parse_args()


def _is_safe_dist(root: Path, dist: Path) -> bool:
    try:
        dist.relative_to(root)
    except ValueError:
        return False
    return dist.name.casefold() == "dist"


def main() -> int:
    args = _parse_args()
    root = Path.cwd().resolve()
    dist = Path(args.dist).expanduser().resolve()

    print(f"Dist runtime cleanup target: {dist}")
    print("Scope: generated dist folder only")
    if args.dry_run:
        print("Mode: dry-run")

    if not dist.exists():
        print(f"[OK] Dist folder does not exist, nothing to clean: {dist}")
        return 0
    if not dist.is_dir():
        print(f"[FAIL] Dist path is not a folder: {dist}")
        return 1
    if not _is_safe_dist(root, dist):
        print(f"[FAIL] Refusing to clean outside project dist folder: {dist}")
        return 1

    removed = 0
    for rel_path in RUNTIME_FILES:
        path = dist / rel_path
        if not path.exists():
            print(f"[OK] Not present: {rel_path}")
            continue
        if path.is_dir():
            print(f"[FAIL] Expected file but found folder, not removing: {rel_path}")
            return 1
        print(f"[CLEAN] {rel_path}")
        if not args.dry_run:
            try:
                path.unlink()
            except OSError as exc:
                print(f"[FAIL] Could not remove {rel_path}: {exc}")
                return 1
        removed += 1

    print()
    print(f"[OK] Dist runtime cleanup complete. Files cleaned: {removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
