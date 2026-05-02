"""Read-only production acceptance smoke checks for Autoliv Shift Manager."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_REQUIRED = [
    "config.json",
    "external_backup.cmd",
    "generate_support_bundle.cmd",
    "verify_build.cmd",
    "tools/post_build_verify.py",
    "tools/external_backup.py",
    "tools/support_bundle.py",
    "tools/clean_dist_runtime.py",
    "docs/RELEASE_CHECKLIST.md",
    "docs/BACKUP_AND_RESTORE.md",
    "docs/SUPPORT_RUNBOOK.md",
    "docs/PRODUCTION_ACCEPTANCE_CHECKLIST.md",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only production smoke checks.")
    parser.add_argument("--root", default=".", help="Project/app root. Default: current folder.")
    parser.add_argument("--dist", default="dist", help="Built dist folder. Default: dist")
    parser.add_argument("--skip-tv", action="store_true", help="Skip TV /health endpoint check.")
    parser.add_argument("--tv-url", default="http://127.0.0.1:8000/health", help="TV health URL.")
    return parser.parse_args()


def _run(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def _check_json(path: Path, label: str, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"Missing JSON file: {label}")
        return
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"Invalid JSON in {label}: {exc}")
    else:
        print(f"[OK] JSON parses: {label}")


def _check_exists(path: Path, label: str, failures: list[str]) -> None:
    if path.exists():
        print(f"[OK] Exists: {label}")
    else:
        failures.append(f"Missing: {label}")


def _check_tv(url: str, failures: list[str]) -> None:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            status = response.status
            body = response.read(4096).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as exc:
        failures.append(f"TV health endpoint not reachable at {url}: {exc}")
        return

    if status != 200:
        failures.append(f"TV health endpoint returned HTTP {status}")
        return
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        failures.append(f"TV health endpoint returned invalid JSON: {exc}")
        return
    if payload.get("status") != "ok":
        failures.append(f"TV health endpoint status is not ok: {payload}")
        return
    print(f"[OK] TV health endpoint reachable: {url}")


def main() -> int:
    args = _parse_args()
    root = Path(args.root).expanduser().resolve()
    dist = Path(args.dist).expanduser().resolve()
    failures: list[str] = []

    print(f"Production smoke check root: {root}")
    print("Mode: read-only")

    if not root.is_dir():
        print(f"[FAIL] Root folder does not exist: {root}")
        return 1

    for rel_path in ROOT_REQUIRED:
        _check_exists(root / rel_path, rel_path, failures)

    _check_json(root / "config.json", "config.json", failures)

    post_build = root / "tools" / "post_build_verify.py"
    if dist.exists() and post_build.is_file():
        code, output = _run([sys.executable, str(post_build), "--dist", str(dist)], root)
        if code != 0:
            failures.append(f"post_build_verify failed:\n{output}")
        else:
            print("[OK] post_build_verify passed")
    elif not dist.exists():
        print(f"[WARN] Dist folder not found, skipped dist verification: {dist}")

    external_backup = root / "tools" / "external_backup.py"
    if external_backup.is_file():
        code, output = _run(
            [sys.executable, str(external_backup), "external_backups", "--source-root", str(root), "--dry-run"],
            root,
        )
        if code != 0:
            failures.append(f"external_backup dry-run failed:\n{output}")
        else:
            print("[OK] external_backup dry-run passed")

    if args.skip_tv:
        print("[OK] TV health check skipped")
    else:
        _check_tv(args.tv_url, failures)

    if failures:
        print()
        print("[FAIL] Production smoke check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print()
    print("[OK] Production smoke check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
