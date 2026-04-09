import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    bundle_dir = Path(sys._MEIPASS)
    os.environ.setdefault("TCL_LIBRARY", str(bundle_dir / "tcl" / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(bundle_dir / "tcl" / "tk8.6"))
