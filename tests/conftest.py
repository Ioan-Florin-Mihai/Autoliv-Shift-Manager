"""
Pytest configuration for this repository.

Note: In some locked-down Windows environments, pytest's internal cleanup step
(`_pytest.pathlib.cleanup_dead_symlinks`) can raise PermissionError when trying
to list the base temp directory at session finish. This is a cleanup-only step
and should not fail the test run.

We patch it to be best-effort: ignore PermissionError while keeping all other
exceptions visible.
"""

from __future__ import annotations

import os
from pathlib import Path

import _pytest.pathlib
import _pytest.tmpdir

_orig_cleanup_dead_symlinks = _pytest.pathlib.cleanup_dead_symlinks
_orig_os_chmod = os.chmod


def _cleanup_dead_symlinks_best_effort(root) -> None:  # pragma: no cover
    try:
        _orig_cleanup_dead_symlinks(root)
    except PermissionError:
        # Cleanup is best-effort; ignore permission issues from the host OS.
        return


_pytest.pathlib.cleanup_dead_symlinks = _cleanup_dead_symlinks_best_effort
_pytest.tmpdir.cleanup_dead_symlinks = _cleanup_dead_symlinks_best_effort


def _chmod_noop_on_windows(_path, _mode, *args, **kwargs) -> None:  # pragma: no cover
    # On some hardened Windows endpoints, chmod applied by pytest to its temp dirs
    # can result in ACLs that deny access even to the current process.
    return


if os.name == "nt":
    os.chmod = _chmod_noop_on_windows

    _orig_make_numbered_dir = _pytest.pathlib.make_numbered_dir

    def _make_numbered_dir_windows_safe(root: Path, prefix: str, mode: int = 0o700) -> Path:  # pragma: no cover
        # Re-implement without passing `mode` to mkdir; on some Windows endpoints
        # `mkdir(mode=...)` can result in restrictive ACLs and break tmp_path.
        parse_num = _pytest.pathlib.parse_num
        find_suffixes = _pytest.pathlib.find_suffixes
        _force_symlink = _pytest.pathlib._force_symlink

        for _ in range(10):
            max_existing = max(map(parse_num, find_suffixes(root, prefix)), default=-1)
            new_number = max_existing + 1
            new_path = root.joinpath(f"{prefix}{new_number}")
            try:
                new_path.mkdir()
            except Exception:
                pass
            else:
                _force_symlink(root, prefix + "current", new_path)
                return new_path
        raise OSError(f"could not create numbered dir with prefix {prefix} in {root} after 10 tries")

    _pytest.pathlib.make_numbered_dir = _make_numbered_dir_windows_safe
    _pytest.tmpdir.make_numbered_dir = _make_numbered_dir_windows_safe


    _orig_getbasetemp = _pytest.tmpdir.TempPathFactory.getbasetemp

    def _getbasetemp_windows_safe(self) -> Path:  # pragma: no cover
        """Windows-safe basetemp creation without chmod/mode=0o700 side effects."""
        if getattr(self, "_basetemp", None) is not None:
            return self._basetemp

        given = getattr(self, "_given_basetemp", None)
        if given is not None:
            # Avoid rm_rf + mkdir(mode=0o700) which can produce ACLs that deny access.
            given.mkdir(parents=True, exist_ok=True)
            self._basetemp = given.resolve()
            return self._basetemp

        return _orig_getbasetemp(self)

    _pytest.tmpdir.TempPathFactory.getbasetemp = _getbasetemp_windows_safe
