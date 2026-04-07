# ============================================================
# MODUL: runtime_bootstrap.py - INITIALIZARE TCL/TK RUNTIME
# ============================================================
#
# Responsabil cu:
#   - Configurarea variabilelor de mediu TCL_LIBRARY și TK_LIBRARY
#   - Necesare doar în modul dev (Python direct), nu în .exe
#   - În .exe, PyInstaller include deja bibliotecile Tcl/Tk
#
# Flux:
#   1. Detectează dacă rulează ca .exe (sys.frozen)
#   2. Dacă e dev mode, caută librariile Tcl/Tk lângă python.exe
#   3. Seteaza variabilele de mediu dacă librairele există
#   4. Dacă librairele lipsesc, va trebui instalat tk
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
    # ── Startup diagnostic ────────────────────────────────────
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        print(f"[bootstrap] Mod EXE  — BASE PATH: {base}")
        print(f"[bootstrap] MEIPASS  — BUNDLE:    {getattr(sys, '_MEIPASS', 'N/A')}")
    else:
        base = Path(__file__).resolve().parent.parent
        print(f"[bootstrap] Mod DEV  — BASE PATH: {base}")

    # ── Startup diagnostic ────────────────────────────────────
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        print(f"[bootstrap] Mod EXE  — BASE PATH: {base}")
        print(f"[bootstrap] MEIPASS  — BUNDLE:    {getattr(sys, '_MEIPASS', 'N/A')}")
    else:
        base = Path(__file__).resolve().parent.parent
        print(f"[bootstrap] Mod DEV  — BASE PATH: {base}")

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
