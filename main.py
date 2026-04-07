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

from logic.runtime_bootstrap import configure_tk_runtime


if __name__ == "__main__":
    # Seteaza variabilele de mediu Tcl/Tk necesare pentru GUI
    configure_tk_runtime()

    # Importa și porneste aplicația după bootstrapping cu succes
    from ui.dashboard import run_app
    try:
        run_app()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("EROARE - Apasa Enter pentru a inchide...")
