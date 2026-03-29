# ============================================================
# MODUL: runtime_bootstrap.py
# Configureaza variabilele de mediu Tcl/Tk necesare pentru
# ca interfata grafica sa functioneze cand rulezi cu Python
# direct (nu ca .exe). In .exe, PyInstaller se ocupa singur.
# ============================================================

import os
import sys
from pathlib import Path


def configure_tk_runtime():
    """
    Seteaza TCL_LIBRARY si TK_LIBRARY daca nu sunt deja setate.
    Necesar in medii de dezvoltare unde Python nu gaseste automat
    librariile Tcl/Tk (ex: medii virtuale, instalari non-standard).
    In modul .exe (frozen), se sare peste aceasta configurare.
    """
    # Daca rulam ca .exe, PyInstaller a inclus deja Tcl/Tk
    if getattr(sys, "frozen", False):
        return

    # Daca variabilele sunt deja setate manual, nu suprascriem
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    # Cauta librariile Tcl/Tk in folderul /tcl/ langa Python.exe
    base_dir    = Path(sys.executable).resolve().parent
    tcl_dir     = base_dir / "tcl"
    tcl_library = tcl_dir / "tcl8.6"
    tk_library  = tcl_dir / "tk8.6"

    # Seteaza doar daca folderele exista efectiv pe disc
    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))
