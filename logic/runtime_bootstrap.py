import os
import sys
from pathlib import Path


def configure_tk_runtime():
    if getattr(sys, "frozen", False):
        return

    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    base_dir = Path(sys.executable).resolve().parent
    tcl_dir = base_dir / "tcl"
    tcl_library = tcl_dir / "tcl8.6"
    tk_library = tcl_dir / "tk8.6"

    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))
