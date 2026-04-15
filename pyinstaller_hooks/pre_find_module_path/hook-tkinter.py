"""
PyInstaller pre-find hook override for tkinter.

Why this exists:
- When PyInstaller runs from a venv on Windows, its built-in pre-find hook can
  mis-detect Tcl/Tk and exclude tkinter entirely, producing a packaged exe that
  crashes with `ModuleNotFoundError: No module named 'tkinter'`.
- This project already bundles Tcl/Tk files explicitly via the .spec and sets
  TCL_LIBRARY/TK_LIBRARY at runtime via `pyinstaller_runtime_hook.py`.

This hook keeps things minimal and production-safe:
- Ensure TCL_LIBRARY/TK_LIBRARY are pointed at the base Python install during
  analysis so imports resolve.
- Do not exclude tkinter even if local Tcl/Tk probing fails in the build env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def pre_find_module_path(api) -> None:  # PyInstaller hook entrypoint signature
    base = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
    tcl_root = base / "tcl"
    tcl_lib = tcl_root / "tcl8.6"
    tk_lib = tcl_root / "tk8.6"
    if tcl_lib.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_lib))
    if tk_lib.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_lib))

