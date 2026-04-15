import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    bundle_dir = Path(sys._MEIPASS)
    # Aliniaza cu asteptarile hook-ului runtime PyInstaller:
    # sys._MEIPASS/_tcl_data si sys._MEIPASS/_tk_data.
    os.environ.setdefault("TCL_LIBRARY", str(bundle_dir / "_tcl_data"))
    os.environ.setdefault("TK_LIBRARY", str(bundle_dir / "_tk_data"))
