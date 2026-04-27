"""
Configuratie Pytest pentru acest repository.

Nota: In unele medii Windows cu politici restrictive, pasul intern de cleanup
al pytest (`_pytest.pathlib.cleanup_dead_symlinks`) poate ridica PermissionError
cand incearca sa listeze directorul temporar de baza la finalul sesiunii.
Acesta este un pas doar de curatare si nu ar trebui sa pice rularea testelor.

Aplicam un patch best-effort: ignoram PermissionError, dar pastram vizibile
celelalte exceptii.
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
        # Curatare best-effort; ignora problemele de permisiuni ale sistemului.
        return


_pytest.pathlib.cleanup_dead_symlinks = _cleanup_dead_symlinks_best_effort
_pytest.tmpdir.cleanup_dead_symlinks = _cleanup_dead_symlinks_best_effort


def _chmod_noop_on_windows(_path, _mode, *args, **kwargs) -> None:  # pragma: no cover
    # Pe unele endpoint-uri Windows "hardened", chmod aplicat de pytest pe directoarele
    # temporare poate produce ACL-uri care refuza accesul chiar si procesului curent.
    return


if os.name == "nt":
    os.chmod = _chmod_noop_on_windows

    _orig_make_numbered_dir = _pytest.pathlib.make_numbered_dir

    def _make_numbered_dir_windows_safe(root: Path, prefix: str, mode: int = 0o700) -> Path:  # pragma: no cover
        # Re-implementare fara a transmite `mode` la mkdir; pe unele endpoint-uri Windows
        # `mkdir(mode=...)` poate produce ACL-uri restrictive si poate strica tmp_path.
        parse_num = _pytest.pathlib.parse_num
        find_suffixes = _pytest.pathlib.find_suffixes
        _force_symlink = _pytest.pathlib._force_symlink

        for _ in range(10):
            max_existing = max(map(parse_num, find_suffixes(root, prefix)), default=-1)
            new_number = max_existing + 1
            new_path = root.joinpath(f"{prefix}{new_number}")
            try:
                new_path.mkdir()
            except OSError:
                pass
            else:
                _force_symlink(root, prefix + "current", new_path)
                return new_path
        raise OSError(f"could not create numbered dir with prefix {prefix} in {root} after 10 tries")

    _pytest.pathlib.make_numbered_dir = _make_numbered_dir_windows_safe
    _pytest.tmpdir.make_numbered_dir = _make_numbered_dir_windows_safe


    _orig_getbasetemp = _pytest.tmpdir.TempPathFactory.getbasetemp

    def _getbasetemp_windows_safe(self) -> Path:  # pragma: no cover
        """Creare basetemp sigura pe Windows, fara efecte secundare chmod/mode=0o700."""
        if getattr(self, "_basetemp", None) is not None:
            return self._basetemp

        given = getattr(self, "_given_basetemp", None)
        if given is not None:
            # Evita rm_rf + mkdir(mode=0o700) care poate produce ACL-uri ce refuza accesul.
            given.mkdir(parents=True, exist_ok=True)
            self._basetemp = given.resolve()
            return self._basetemp

        try:
            return _orig_getbasetemp(self)
        except PermissionError:
            # In unele sandbox-uri Windows, variabilele TEMP/TMP indica un profil
            # nelocuibil de procesul curent (ex: C:\\Users\\User\\AppData\\Local\\Temp).
            # Fallback: foloseste un director local in repo, ignorat de Git.
            repo_root = Path(__file__).resolve().parents[1]
            fallback = repo_root / ".pytest_tmp_local"
            fallback.mkdir(parents=True, exist_ok=True)
            self._basetemp = fallback.resolve()
            return self._basetemp

    _pytest.tmpdir.TempPathFactory.getbasetemp = _getbasetemp_windows_safe
