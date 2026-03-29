# ============================================================
# PUNCT DE INTRARE AL APLICATIEI
# Ruleaza acest fisier pentru a porni Autoliv Shift Manager.
# ============================================================

# Configureaza mediul Tcl/Tk inainte de orice import UI
# (necesar mai ales cand rulezi direct din Python, nu din .exe)
from logic.runtime_bootstrap import configure_tk_runtime


if __name__ == "__main__":
    configure_tk_runtime()

    # Importam run_app dupa bootstrap ca sa evitam erori Tcl/Tk
    from ui.dashboard import run_app
    run_app()
