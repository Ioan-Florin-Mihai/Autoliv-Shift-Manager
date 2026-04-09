# ============================================================
# MODUL: employee_store.py
# Gestioneaza lista simpla de angajati (employees.json).
# Aceasta lista e folosita pentru autocomplete in planner.
#
# La incarcare, colecteaza automat numele din:
#   1. employees.json (lista primara)
#   2. schedule_data.json (mig. date vechi din planificare)
#   3. cache.json via PersonnelManager (angajati inregistrati)
# ============================================================

import json
import os
import tempfile

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file

# Fisierul principal cu lista de angajati
EMPLOYEES_PATH = ensure_runtime_file("data/employees.json")


class EmployeeStore:
    """
    Strat de acces pentru lista de angajati (employees.json).
    Suporta cautare, adaugare, stergere si redenumire.
    """

    def __init__(self):
        # Incarcam si normalizam lista la initializare
        self.data = self._load()

    def _load(self):
        """
        Incarca lista de angajati. Daca fisierul nu exista,
        colecteaza numele direct din planificari si cache.
        """
        if not EMPLOYEES_PATH.exists():
            # Prima rulare — construim lista din datele existente
            normalized = self._collect_schedule_names(set())
            return {"employees": sorted(normalized, key=str.casefold)}

        try:
            with EMPLOYEES_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("employee_store_load", exc)
            return {"employees": []}

        if not isinstance(data, dict):
            return {"employees": []}

        employees = data.get("employees", [])
        if not isinstance(employees, list):
            employees = []

        # Normalizam: eliminam duplicate si spatii extra
        normalized, seen = self._normalize_names(employees)

        # Migram orice angajat nou gasit in planificari sau cache
        migrated = self._collect_schedule_names(seen)
        if migrated:
            normalized.extend(migrated)
            normalized.sort(key=str.casefold)

        return {"employees": normalized}

    def _normalize_names(self, employees):
        """
        Curata lista de angajati:
        - Elimina spatii multiple
        - Elimina duplicate (case-insensitive)
        - Sorteaza alfabetic
        Returneaza (lista_curata, set_lowercase).
        """
        normalized = []
        seen       = set()
        for employee in employees:
            if not isinstance(employee, str):
                continue
            value = " ".join(employee.split()).strip()
            if value and value.casefold() not in seen:
                normalized.append(value)
                seen.add(value.casefold())
        normalized.sort(key=str.casefold)
        return normalized, seen

    def _collect_schedule_names(self, seen):
        """
        Extrage numele angajatilor din schedule_data.json si cache.json,
        fara a duplica ce avem deja in `seen`.
        Returneaza lista de nume noi descoperite.
        """
        discovered = []

        # ── Extragere din planificare (schedule_data.json) ──────────
        try:
            from logic.schedule_store import SCHEDULE_PATH
        except Exception:
            SCHEDULE_PATH = None

        if SCHEDULE_PATH and SCHEDULE_PATH.exists():
            try:
                with SCHEDULE_PATH.open("r", encoding="utf-8") as file:
                    schedule_data = json.load(file)

                weeks = schedule_data.get("weeks", {})
                if isinstance(weeks, dict):
                    for week_record in weeks.values():
                        if not isinstance(week_record, dict):
                            continue
                        # Format nou: modes → { "Magazie": {...}, "Bucle": {...} }
                        if isinstance(week_record.get("modes"), dict):
                            for mode_record in week_record["modes"].values():
                                self._collect_names_from_mode(mode_record, seen, discovered)
                        # Format vechi: schedule direct pe week_record
                        elif isinstance(week_record.get("schedule"), dict):
                            self._collect_names_from_schedule(week_record["schedule"], seen, discovered)
            except (OSError, json.JSONDecodeError):
                pass

        # ── Extragere din cache (cache.json via PersonnelManager) ────
        self._collect_names_from_personnel_manager(seen, discovered)

        return discovered

    def _collect_names_from_mode(self, mode_record, seen, discovered):
        """Extrage numele din structura unui mod (Magazie/Bucle)."""
        schedule = mode_record.get("schedule", {})
        if isinstance(schedule, dict):
            self._collect_names_from_schedule(schedule, seen, discovered)

    def _collect_names_from_schedule(self, schedule, seen, discovered):
        """
        Parcurge planificarea (departament → zi → schimb → celula)
        si colecteaza toate numele angajatilor noi.
        """
        for department_schedule in schedule.values():
            if not isinstance(department_schedule, dict):
                continue
            for day_schedule in department_schedule.values():
                if not isinstance(day_schedule, dict):
                    continue
                for cell in day_schedule.values():
                    employees = []
                    if isinstance(cell, dict):
                        employees = cell.get("employees", [])
                    elif isinstance(cell, str):
                        # Format text vechi (inainte de migrare)
                        employees = [line.strip() for line in cell.splitlines()]
                    for employee in employees:
                        if not isinstance(employee, str):
                            continue
                        value = " ".join(employee.split()).strip()
                        if value and value.casefold() not in seen:
                            discovered.append(value)
                            seen.add(value.casefold())

    def _collect_names_from_personnel_manager(self, seen, discovered):
        """
        Extrage numele din cache.json (PersonnelManager).
        Apelata o singura data per incarcare pentru eficienta.
        """
        try:
            from logic.personnel_manager import PersonnelManager
            pm = PersonnelManager()
            for rec in pm.get_all():
                fullname = f"{rec.get('nume', '').strip()} {rec.get('prenume', '').strip()}"
                if fullname and fullname.casefold() not in seen:
                    discovered.append(fullname)
                    seen.add(fullname.casefold())
        except Exception:
            pass  # Cache indisponibil — continuam fara el

    # ── Operatii CRUD ─────────────────────────────────────────────

    def save(self):
        """Salveaza lista curenta in employees.json (scriere atomica)."""
        EMPLOYEES_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=EMPLOYEES_PATH.parent, suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    json.dump(self.data, tmp, ensure_ascii=False, indent=2)
            except Exception:
                os.unlink(tmp_path)
                raise
            os.replace(tmp_path, EMPLOYEES_PATH)
        except OSError as exc:
            log_exception("employee_store_save", exc)
            raise

    def get_all(self):
        """Returneaza toti angajatii din lista."""
        return list(self.data.get("employees", []))

    def search(self, query: str):
        """
        Cauta angajati dupa un query (case-insensitive, substring).
        Returneaza maxim 30 de rezultate.
        Fara query → primii 30 din lista.
        """
        query     = query.strip().casefold()
        employees = self.get_all()
        if not query:
            return employees[:30]
        return [e for e in employees if query in e.casefold()][:30]

    def add_employee(self, employee_name: str):
        """
        Adauga un angajat nou daca nu exista deja (case-insensitive).
        Returneaza numele normalizat.
        """
        value = " ".join(employee_name.split()).strip()
        if not value:
            raise ValueError("Numele angajatului este obligatoriu.")

        employees = self.data.setdefault("employees", [])
        # Nu adaugam duplicate
        if any(existing.casefold() == value.casefold() for existing in employees):
            return value

        employees.append(value)
        employees.sort(key=str.casefold)
        self.save()
        return value

    def delete_employee(self, employee_name: str):
        """
        Sterge un angajat din lista (case-insensitive).
        Returneaza True daca a fost gasit si sters.
        """
        value = " ".join(employee_name.split()).strip()
        if not value:
            return False

        employees    = self.data.setdefault("employees", [])
        initial_len  = len(employees)
        self.data["employees"] = [e for e in employees if e.casefold() != value.casefold()]

        if len(self.data["employees"]) < initial_len:
            self.save()
            return True
        return False

    def rename_employee(self, old_name: str, new_name: str):
        """
        Redenumeste un angajat in lista.
        Arunca ValueError daca: old_name nu exista, new_name deja exista,
        sau unul din nume e gol.
        """
        old_val   = " ".join(old_name.split()).strip().casefold()
        new_val   = " ".join(new_name.split()).strip()

        if not old_val or not new_val:
            raise ValueError("Ambele nume trebuie să fie valide.")

        employees = self.data.setdefault("employees", [])

        # Verificam ca noul nume nu exista deja
        if any(existing.casefold() == new_val.casefold() for existing in employees):
            raise ValueError(f"Numele '{new_name}' există deja.")

        # Inlocuim in lista
        renamed = False
        for idx, emp in enumerate(employees):
            if emp.casefold() == old_val:
                employees[idx] = new_val
                renamed = True
                break

        if renamed:
            employees.sort(key=str.casefold)
            self.save()
            return new_val

        raise ValueError(f"Angajatul '{old_name}' nu a fost găsit.")
