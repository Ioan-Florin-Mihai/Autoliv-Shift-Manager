# ============================================================
# MODUL: employee_store.py
# Gestioneaza lista de angajati si profilul minim folosit pentru sugestii.
# ============================================================

from __future__ import annotations

import json
from typing import Any

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file
from logic.utils.io import atomic_write_json

EMPLOYEES_PATH = ensure_runtime_file("data/employees.json")


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _compose_full_name(nume: str, prenume: str) -> str:
    return " ".join(part for part in (_clean_text(nume), _clean_text(prenume)) if part).strip()


class EmployeeStore:
    """Strat de acces pentru lista de angajati."""

    def __init__(self):
        self.data = self._load()

    def _load(self):
        if not EMPLOYEES_PATH.exists():
            records, seen = self._normalize_employee_records([])
            migrated = self._collect_schedule_names(seen)
            if migrated:
                records.extend(migrated)
                records.sort(key=lambda item: item["full_name"].casefold())
            return {"employees": records}

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

        normalized, seen = self._normalize_employee_records(employees)
        migrated = self._collect_schedule_names(seen)
        if migrated:
            normalized.extend(migrated)
            normalized.sort(key=lambda item: item["full_name"].casefold())

        return {"employees": normalized}

    def _record_from_name(self, full_name: str, departament: str | None = None) -> dict[str, str | None]:
        value = _clean_text(full_name)
        if not value:
            return {}
        parts = value.split(" ", 1)
        nume = parts[0]
        prenume = parts[1] if len(parts) > 1 else ""
        return self._record_from_profile(nume, prenume, departament)

    def _record_from_profile(self, nume: str, prenume: str, departament: str | None = None) -> dict[str, str | None]:
        clean_nume = _clean_text(nume)
        clean_prenume = _clean_text(prenume)
        full_name = _compose_full_name(clean_nume, clean_prenume)
        if not full_name:
            return {}
        clean_departament = _clean_text(departament) or None
        return {
            "nume": clean_nume,
            "prenume": clean_prenume,
            "departament": clean_departament,
            "full_name": full_name,
        }

    def _normalize_employee_records(self, employees: list[Any]) -> tuple[list[dict[str, str | None]], set[str]]:
        normalized: list[dict[str, str | None]] = []
        seen: set[str] = set()

        for employee in employees:
            record: dict[str, str | None] = {}
            if isinstance(employee, str):
                record = self._record_from_name(employee)
            elif isinstance(employee, dict):
                record = self._record_from_profile(
                    employee.get("nume", ""),
                    employee.get("prenume", ""),
                    employee.get("departament"),
                )
                if not record and isinstance(employee.get("full_name"), str):
                    record = self._record_from_name(employee.get("full_name", ""), employee.get("departament"))
            if not record:
                continue
            key = record["full_name"].casefold()
            if key in seen:
                continue
            normalized.append(record)
            seen.add(key)

        normalized.sort(key=lambda item: item["full_name"].casefold())
        return normalized, seen

    def _collect_schedule_names(self, seen: set[str]) -> list[dict[str, str | None]]:
        discovered: list[dict[str, str | None]] = []
        self._collect_names_from_personnel_manager(seen, discovered)
        return discovered

    def _collect_names_from_mode(self, mode_record, seen: set[str], discovered: list[dict[str, str | None]]):
        schedule = mode_record.get("schedule", {})
        if isinstance(schedule, dict):
            self._collect_names_from_schedule(schedule, seen, discovered)

    def _collect_names_from_schedule(self, schedule, seen: set[str], discovered: list[dict[str, str | None]]):
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
                        employees = [line.strip() for line in cell.splitlines()]
                    for employee in employees:
                        record = self._record_from_name(employee)
                        if not record:
                            continue
                        key = record["full_name"].casefold()
                        if key not in seen:
                            discovered.append(record)
                            seen.add(key)

    def _collect_names_from_personnel_manager(self, seen: set[str], discovered: list[dict[str, str | None]]):
        try:
            from logic.personnel_manager import PersonnelManager
        except ImportError:
            return

        try:
            pm = PersonnelManager()
            for rec in pm.get_all():
                record = self._record_from_profile(
                    rec.get("nume", ""),
                    rec.get("prenume", ""),
                    rec.get("departament"),
                )
                if not record:
                    continue
                key = record["full_name"].casefold()
                if key not in seen:
                    discovered.append(record)
                    seen.add(key)
        except (AttributeError, OSError, ValueError):
            pass

    def _serialize(self) -> dict[str, list[dict[str, str | None]]]:
        payload = []
        for record in self.data.get("employees", []):
            if not isinstance(record, dict):
                continue
            payload.append(
                {
                    "nume": record.get("nume", ""),
                    "prenume": record.get("prenume", ""),
                    "departament": record.get("departament"),
                }
            )
        return {"employees": payload}

    def _find_record_index(self, full_name: str) -> int:
        key = _clean_text(full_name).casefold()
        for idx, record in enumerate(self.data.get("employees", [])):
            if isinstance(record, dict) and _clean_text(record.get("full_name", "")).casefold() == key:
                return idx
        return -1

    def save(self):
        EMPLOYEES_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_json(EMPLOYEES_PATH, self._serialize())
        except OSError as exc:
            log_exception("employee_store_save", exc)
            raise

    def get_all(self):
        return [record["full_name"] for record in self.data.get("employees", []) if isinstance(record, dict)]

    def get_profiles(self):
        return [
            {
                "nume": record.get("nume", ""),
                "prenume": record.get("prenume", ""),
                "departament": record.get("departament"),
                "full_name": record.get("full_name", ""),
            }
            for record in self.data.get("employees", [])
            if isinstance(record, dict)
        ]

    def get_department_map(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for record in self.get_profiles():
            full_name = _clean_text(record.get("full_name", ""))
            if full_name:
                result[full_name] = record.get("departament")
        return result

    def search(self, query: str):
        query = query.strip().casefold()
        employees = self.get_all()
        if not query:
            return employees[:30]
        return [e for e in employees if query in e.casefold()][:30]

    def add_employee(self, employee_name: str):
        record = self._record_from_name(employee_name)
        if not record:
            raise ValueError("Numele angajatului este obligatoriu.")

        employees = self.data.setdefault("employees", [])
        if any(existing.get("full_name", "").casefold() == record["full_name"].casefold() for existing in employees if isinstance(existing, dict)):
            return record["full_name"]

        employees.append(record)
        employees.sort(key=lambda item: item["full_name"].casefold())
        self.save()
        return record["full_name"]

    def upsert_profile(self, nume: str, prenume: str, departament: str | None) -> tuple[str, bool]:
        record = self._record_from_profile(nume, prenume, departament)
        if not record:
            raise ValueError("Numele angajatului este obligatoriu.")

        employees = self.data.setdefault("employees", [])
        index = self._find_record_index(record["full_name"])
        if index >= 0:
            employees[index]["departament"] = record["departament"]
            employees[index]["nume"] = record["nume"]
            employees[index]["prenume"] = record["prenume"]
            employees[index]["full_name"] = record["full_name"]
            employees.sort(key=lambda item: item["full_name"].casefold())
            self.save()
            return record["full_name"], False

        employees.append(record)
        employees.sort(key=lambda item: item["full_name"].casefold())
        self.save()
        return record["full_name"], True

    def delete_employee(self, employee_name: str):
        value = _clean_text(employee_name)
        if not value:
            return False

        employees = self.data.setdefault("employees", [])
        initial_len = len(employees)
        self.data["employees"] = [
            e for e in employees
            if not (isinstance(e, dict) and e.get("full_name", "").casefold() == value.casefold())
        ]

        if len(self.data["employees"]) < initial_len:
            self.save()
            return True
        return False

    def rename_employee(self, old_name: str, new_name: str):
        old_val = _clean_text(old_name).casefold()
        new_record = self._record_from_name(new_name)

        if not old_val or not new_record:
            raise ValueError("Ambele nume trebuie sa fie valide.")

        employees = self.data.setdefault("employees", [])

        if any(existing.get("full_name", "").casefold() == new_record["full_name"].casefold() for existing in employees if isinstance(existing, dict)):
            raise ValueError(f"Numele '{new_name}' exista deja.")

        renamed = False
        for idx, emp in enumerate(employees):
            if isinstance(emp, dict) and emp.get("full_name", "").casefold() == old_val:
                employees[idx]["nume"] = new_record["nume"]
                employees[idx]["prenume"] = new_record["prenume"]
                employees[idx]["full_name"] = new_record["full_name"]
                renamed = True
                break

        if renamed:
            employees.sort(key=lambda item: item["full_name"].casefold())
            self.save()
            return new_record["full_name"]

        raise ValueError(f"Angajatul '{old_name}' nu a fost gasit.")
