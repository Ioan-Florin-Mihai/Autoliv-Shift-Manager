# ============================================================
# AUTOLIV SHIFT MANAGER - PUNCT DE INTRARE
# ============================================================
# 
# Fișierul principal care pornește aplicația.
# Rulează: python main.py (din IDE) sau Autoliv Shift Manager.exe
#
# Flux:
#   1. Configurează mediul Tcl/Tk (runtime bootstrap)
#   2. Importă UI-ul (dashboard) - care gestionează autentificarea
#   3. Pornește bucla główna a aplicației (GUI)
#
# NOTE: În modul .exe (PyInstaller), bootstrapping-ul e inclus automat.
#       Doar în dev mode (Python direct) e nevoie de setup suplimentar.
# ============================================================

import sys
import threading
import traceback

from logic.runtime_bootstrap import configure_tk_runtime


def _global_crash_handler(exc_type, exc_value, exc_tb):
    """Handler global pentru excepții necapturate pe main thread."""
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        import tkinter.messagebox as _mb
        _mb.showerror(
            "Eroare neașteptată",
            f"A apărut o eroare neașteptată:\n\n{err_text[:600]}\n\nReporniți aplicația.",
        )
    except Exception:
        pass
    traceback.print_exception(exc_type, exc_value, exc_tb)


def _thread_crash_handler(args):
    """Handler global pentru excepții necapturate în thread-uri background."""
    _global_crash_handler(args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = _global_crash_handler
threading.excepthook = _thread_crash_handler


if __name__ == "__main__":
    # Seteaza variabilele de mediu Tcl/Tk necesare pentru GUI
    configure_tk_runtime()

    # TV MODE: pornit cu flagul --tv (ex: Autoliv_Shift_Manager.exe --tv)
    if "--tv" in sys.argv:
        from ui.tv_mode import run_tv_mode
        run_tv_mode()
    else:
        # Importa și porneste aplicația după bootstrapping cu succes
        from ui.dashboard import run_app
        try:
            run_app()
        except Exception:
            traceback.print_exc()
            input("EROARE - Apasa Enter pentru a inchide...")
