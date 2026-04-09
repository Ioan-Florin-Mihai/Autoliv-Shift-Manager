# ============================================================
# MODUL: ui_state_store.py
# Salveaza si restaureaza starea interfetei intre sesiuni.
# In prezent retine ultima data selectata de utilizator,
# astfel incat la redeschidere sa se afiseze aceeasi saptamana.
# ============================================================

import json
from datetime import date, datetime

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file
from logic.schedule_store import get_week_start

# Calea fisierului JSON cu starea UI — creat automat la primul rulaj
UI_STATE_PATH = ensure_runtime_file("data/ui_state.json")


class UIStateStore:
    """Gestioneaza persistenta starii interfetei utilizatorului."""

    def load_last_selected_date(self):
        """
        Citeste ultima data selectata din fisierul de stare.
        Returneaza un obiect date sau None daca nu exista / e invalida.
        """
        if not UI_STATE_PATH.exists():
            return None

        try:
            with UI_STATE_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("ui_state_load", exc)
            return None

        if not isinstance(data, dict):
            return None

        value = data.get("last_selected_date", "").strip()
        if not value:
            return None

        # Parseaza data din format ISO (YYYY-MM-DD)
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def resolve_startup_date(self):
        """
        Determina ce data sa afiseze la pornirea aplicatiei.
        - Daca exista o data salvata DIN ACEEASI SAPTAMANA → o folosim
        - Altfel → afisam saptamana curenta (azi)
        Logica: daca utilizatorul a salvat joi, si azi e luni saptamana urmatoare,
        se va afisa azi. Daca azi e miercuri din aceeasi saptamana, afisam joi.
        """
        today      = date.today()
        saved_date = self.load_last_selected_date()

        if saved_date is None:
            return today

        # Comparam inceputul saptamanii (luni) pentru ambele date
        if get_week_start(saved_date) != get_week_start(today):
            # Saptamana salvata e veche → resetam la saptamana curenta
            return today

        return saved_date

    def save_last_selected_date(self, selected_date: date):
        """Salveaza data selectata curenta in fisierul de stare — scriere atomica."""
        import os
        import tempfile
        payload = {"last_selected_date": selected_date.isoformat()}
        try:
            UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_path = tempfile.mkstemp(dir=UI_STATE_PATH.parent, suffix=".tmp")
            try:
                import json as _json
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    _json.dump(payload, tmp, ensure_ascii=False, indent=2)
            except Exception:
                os.unlink(tmp_path)
                raise
            os.replace(tmp_path, UI_STATE_PATH)
        except OSError as exc:
            log_exception("ui_state_save", exc)
