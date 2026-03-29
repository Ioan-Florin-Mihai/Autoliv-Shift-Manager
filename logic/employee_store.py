import json
from pathlib import Path

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file


EMPLOYEES_PATH = ensure_runtime_file("data/employees.json")


class EmployeeStore:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if not EMPLOYEES_PATH.exists():
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

        normalized, seen = self._normalize_names(employees)
        migrated = self._collect_schedule_names(seen)
        if migrated:
            normalized.extend(migrated)
            normalized.sort(key=str.casefold)

        return {"employees": normalized}

    def _normalize_names(self, employees):
        normalized = []
        seen = set()
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
        try:
            from logic.schedule_store import SCHEDULE_PATH
        except Exception:
            return []

        if not SCHEDULE_PATH.exists():
            return []

        try:
            with SCHEDULE_PATH.open("r", encoding="utf-8") as file:
                schedule_data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return []

        weeks = schedule_data.get("weeks", {})
        if not isinstance(weeks, dict):
            return []

        discovered = []
        for week_record in weeks.values():
            if not isinstance(week_record, dict):
                continue
            if isinstance(week_record.get("modes"), dict):
                for mode_record in week_record["modes"].values():
                    self._collect_names_from_mode(mode_record, seen, discovered)
            elif isinstance(week_record.get("schedule"), dict):
                self._collect_names_from_schedule(week_record["schedule"], seen, discovered)
        return discovered

    def _collect_names_from_mode(self, mode_record, seen, discovered):
        schedule = mode_record.get("schedule", {})
        if isinstance(schedule, dict):
            self._collect_names_from_schedule(schedule, seen, discovered)

    def _collect_names_from_schedule(self, schedule, seen, discovered):
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
                        if not isinstance(employee, str):
                            continue
                        value = " ".join(employee.split()).strip()
                        if value and value.casefold() not in seen:
                            discovered.append(value)
                            seen.add(value.casefold())

        # Extrage si din noul sistem de management personnel (data/cache.json)
        try:
            from logic.personnel_manager import PersonnelManager
            pm = PersonnelManager()
            for rec in pm.get_all():
                fullname = f"{rec.get('nume', '').strip()} {rec.get('prenume', '').strip()}"
                if fullname and fullname.casefold() not in seen:
                    discovered.append(fullname)
                    seen.add(fullname.casefold())
        except Exception:
            pass

    def save(self):
        EMPLOYEES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EMPLOYEES_PATH.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def get_all(self):
        return list(self.data.get("employees", []))

    def search(self, query: str):
        query = query.strip().casefold()
        employees = self.get_all()
        if not query:
            return employees[:30]
        return [employee for employee in employees if query in employee.casefold()][:30]

    def add_employee(self, employee_name: str):
        value = " ".join(employee_name.split()).strip()
        if not value:
            raise ValueError("Numele angajatului este obligatoriu.")

        employees = self.data.setdefault("employees", [])
        if any(existing.casefold() == value.casefold() for existing in employees):
            return value

        employees.append(value)
        employees.sort(key=str.casefold)
        self.save()
        return value

    def delete_employee(self, employee_name: str):
        value = " ".join(employee_name.split()).strip()
        if not value:
            return False
            
        employees = self.data.setdefault("employees", [])
        initial_len = len(employees)
        self.data["employees"] = [e for e in employees if e.casefold() != value.casefold()]
        
        if len(self.data["employees"]) < initial_len:
            self.save()
            return True
        return False

    def rename_employee(self, old_name: str, new_name: str):
        old_val = " ".join(old_name.split()).strip().casefold()
        new_val = " ".join(new_name.split()).strip()
        
        if not old_val or not new_val:
            raise ValueError("Ambele nume trebuie să fie valide.")
            
        employees = self.data.setdefault("employees", [])
        if any(existing.casefold() == new_val.casefold() for existing in employees):
            raise ValueError(f"Numele '{new_name}' există deja.")
            
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
