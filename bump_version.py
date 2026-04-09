from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parent / "logic" / "version.py"
VERSION_PATTERN = re.compile(r'^VERSION\s*=\s*"(?P<version>\d+\.\d+\.\d+)"\s*$', re.MULTILINE)
BUILD_DATE_PATTERN = re.compile(r'^BUILD_DATE\s*=\s*"(?P<build_date>\d{4}-\d{2}-\d{2})"\s*$', re.MULTILINE)


def read_version_file() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Nu pot citi {VERSION_FILE}") from exc


def extract_version(content: str) -> str:
    matches = VERSION_PATTERN.findall(content)
    if not matches:
        raise RuntimeError("Constanta VERSION nu a putut fi gasita in logic/version.py")
    if len(matches) != 1:
        raise RuntimeError("logic/version.py contine mai multe declaratii VERSION")
    match = VERSION_PATTERN.search(content)
    assert match is not None
    return match.group("version")


def validate_version_format(version: str) -> None:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise RuntimeError(f"Versiune invalida: {version}. Formatul corect este MAJOR.MINOR.PATCH")


def validate_build_date_entry(content: str) -> None:
    matches = BUILD_DATE_PATTERN.findall(content)
    if not matches:
        raise RuntimeError("Constanta BUILD_DATE nu a putut fi gasita in logic/version.py")
    if len(matches) != 1:
        raise RuntimeError("logic/version.py contine mai multe declaratii BUILD_DATE")


def bump_patch(version: str) -> str:
    validate_version_format(version)
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def write_version_file(content: str, new_version: str, build_date: str) -> None:
    validate_version_format(new_version)
    updated = VERSION_PATTERN.sub(f'VERSION    = "{new_version}"', content, count=1)
    updated = BUILD_DATE_PATTERN.sub(f'BUILD_DATE = "{build_date}"', updated, count=1)
    try:
        VERSION_FILE.write_text(updated, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Nu pot scrie in {VERSION_FILE}") from exc

    verified_content = read_version_file()
    verified_version = extract_version(verified_content)
    validate_build_date_entry(verified_content)
    if verified_version != new_version:
        raise RuntimeError("Verificarea dupa scriere a esuat: VERSION nu a fost actualizata corect")
    if f'BUILD_DATE = "{build_date}"' not in verified_content:
        raise RuntimeError("Verificarea dupa scriere a esuat: BUILD_DATE nu a fost actualizata corect")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestionare versiune pentru Autoliv Shift Manager")
    parser.add_argument("--current", action="store_true", help="Afiseaza versiunea curenta")
    parser.add_argument("--patch", action="store_true", help="Incrementeaza patch version")
    args = parser.parse_args()

    try:
        content = read_version_file()
        current_version = extract_version(content)
        validate_version_format(current_version)
        validate_build_date_entry(content)

        if args.current:
            print(current_version)
            return 0

        if args.patch or not any(vars(args).values()):
            new_version = bump_patch(current_version)
            build_date = date.today().isoformat()
            write_version_file(content, new_version, build_date)
            print(new_version)
            return 0

        parser.print_help()
        return 0
    except RuntimeError as exc:
        print(f"[EROARE] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())