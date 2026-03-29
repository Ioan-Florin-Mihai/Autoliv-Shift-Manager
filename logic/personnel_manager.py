import json
from datetime import datetime
from pathlib import Path

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file

CACHE_PATH = ensure_runtime_file("data/cache.json")

class PersonnelManager:
    def __init__(self):
        self.records = self.load_cache()

    def load_cache(self):
        if not CACHE_PATH.exists():
            return []
        try:
            with CACHE_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
                return data.get("employees", []) if isinstance(data, dict) else []
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("personnel_load_cache", exc)
            return []

    def save_cache(self):
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with CACHE_PATH.open("w", encoding="utf-8") as file:
                json.dump(self.records, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            log_exception("personnel_save_cache", exc)

    def is_duplicate(self, nume: str, prenume: str):
        full_name = f"{nume.strip()} {prenume.strip()}".casefold()
        for record in self.records:
            rec_nume = record.get("nume", "").strip()
            rec_prenume = record.get("prenume", "").strip()
            rec_full = f"{rec_nume} {rec_prenume}".casefold()
            if rec_full == full_name:
                return True
        return False

    def add_record(self, data: dict):
        # adauga inregistrarea doar daca nu este duplicata conform (nume + prenume)
        nume = data.get("nume", "")
        prenume = data.get("prenume", "")
        if self.is_duplicate(nume, prenume):
            return False

        # Asigura data curenta pe record
        if "data_adaugare" not in data:
            data["data_adaugare"] = datetime.now().strftime("%Y-%m-%d")

        self.records.append(data)
        self.save_cache()
        return True

    def delete_record(self, fullname: str):
        full_name_clean = " ".join(fullname.split()).casefold()
        initial_length = len(self.records)
        self.records = [
            r for r in self.records 
            if f"{r.get('nume', '').strip()} {r.get('prenume', '').strip()}".casefold() != full_name_clean
        ]
        if len(self.records) < initial_length:
            self.save_cache()
            return True
        return False

    def get_all(self):
        return self.records
