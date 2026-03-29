# ============================================================
# MODUL: personnel_manager.py
# Gestioneaza inregistrarile de personal din cache.json.
# Rolul sau: pastreaza o lista locala de angajati cu detalii
# (contract, departament, ore) separata de lista simpla din
# employees.json. Folosit de EmployeeRegistrationWindow.
# ============================================================

import json
from datetime import datetime
from pathlib import Path

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file

# Fisierul cache al personalului — format: lista de obiecte JSON
CACHE_PATH = ensure_runtime_file("data/cache.json")


class PersonnelManager:
    """Strat de acces pentru inregistrarile de personal (cache.json)."""

    def __init__(self):
        # Incarcam toate inregistrarile la initializare
        self.records = self.load_cache()

    def load_cache(self):
        """
        Citeste lista de angajati din cache.json.
        Accepta atat format lista cat si format dict cu cheia 'employees'.
        Returneaza lista goala daca fisierul lipseste sau e corupt.
        """
        if not CACHE_PATH.exists():
            return []
        try:
            with CACHE_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
                # Suport format vechi dict { "employees": [...] }
                return data.get("employees", []) if isinstance(data, dict) else []
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("personnel_load_cache", exc)
            return []

    def save_cache(self):
        """Scrie lista curenta de inregistrari in cache.json."""
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with CACHE_PATH.open("w", encoding="utf-8") as file:
                json.dump(self.records, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            log_exception("personnel_save_cache", exc)

    def is_duplicate(self, nume: str, prenume: str):
        """
        Verifica daca un angajat cu acelasi nume complet exista deja.
        Comparatia e case-insensitive.
        """
        full_name = f"{nume.strip()} {prenume.strip()}".casefold()
        for record in self.records:
            rec_full = f"{record.get('nume','').strip()} {record.get('prenume','').strip()}".casefold()
            if rec_full == full_name:
                return True
        return False

    def add_record(self, data: dict):
        """
        Adauga o noua inregistrare daca nu e duplicat.
        Seteaza automat data_adaugare daca lipseste.
        Returneaza True la succes, False daca e duplicat.
        """
        # Guard: nu adaugam duplicate
        if self.is_duplicate(data.get("nume", ""), data.get("prenume", "")):
            return False

        # Injectam data curenta daca nu e furnizata
        if "data_adaugare" not in data:
            data["data_adaugare"] = datetime.now().strftime("%Y-%m-%d")

        self.records.append(data)
        self.save_cache()
        return True

    def delete_record(self, fullname: str):
        """
        Sterge inregistrarea cu numele complet dat.
        Returneaza True daca a gasit si sters, False daca nu a gasit.
        """
        full_name_clean = " ".join(fullname.split()).casefold()
        initial_length  = len(self.records)

        # Filtram afara inregistrarea cu numele dat
        self.records = [
            r for r in self.records
            if f"{r.get('nume','').strip()} {r.get('prenume','').strip()}".casefold() != full_name_clean
        ]

        if len(self.records) < initial_length:
            self.save_cache()
            return True
        return False

    def get_all(self):
        """Returneaza toate inregistrarile de personal."""
        return self.records
