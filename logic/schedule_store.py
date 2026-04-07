import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import date, datetime, timedelta

from logic.app_logger import log_exception, log_warning, log_info
from logic.app_paths import BACKUP_DIR, ensure_runtime_file


SCHEDULE_PATH = ensure_runtime_file("data/schedule_data.json")

DAYS = [
    ("Luni", 0),
    ("Marti", 1),
    ("Miercuri", 2),
    ("Joi", 3),
    ("Vineri", 4),
    ("Sambata", 5),
    ("Duminica", 6),
]

DAY_NAMES = [item[0] for item in DAYS]
WEEKEND_DAYS = {"Sambata", "Duminica"}
SHIFTS = ["Sch1", "Sch2", "Sch3"]

TEMPLATES = {
    "Magazie": [
        "Sef Schimb",
        "Receptii",
        "Livrari",
        "Etichetare Scanare",
        "Retragere finite",
        "Balotare Ambalare",
    ],
    "Bucle": [
        "BUCLA RA + RB",
        "BUCLA TA + TB",
        "BUCLA 02",
        "BUCLA 03",
        "BUCLA 04",
        "BUCLA 05 + 07",
        "Ambalaje",
    ],
}

DEPARTMENT_COLORS = {
    "Sef Schimb": "5B9BD5",
    "Receptii": "4472C4",
    "Livrari": "A9D18E",
    "Etichetare Scanare": "C9B0D9",
    "Retragere finite": "D9A35F",
    "Balotare Ambalare": "D9E2F3",
    "BUCLA RA + RB": "D9A35F",
    "BUCLA TA + TB": "D9A35F",
    "BUCLA 02": "D9A35F",
    "BUCLA 03": "D9A35F",
    "BUCLA 04": "D9A35F",
    "BUCLA 05 + 07": "D9A35F",
    "Ambalaje": "D99694",
}


def get_week_start(selected_date: date):
    return selected_date - timedelta(days=selected_date.weekday())


def format_day_label(week_start: date, day_offset: int):
    current_day = week_start + timedelta(days=day_offset)
    day_name = DAYS[day_offset][0]
    return f"{day_name}\n{current_day.strftime('%d-%b-%y')}"


def _empty_cell():
    # `colors` stocheaza culoarea aleasa manual per angajat: {"Nume Prenume": "#FF0000"}
    return {"employees": [], "colors": {}}


def _empty_schedule_for_departments(departments):
    return {
        department: {
            day_name: {shift: _empty_cell() for shift in SHIFTS}
            for day_name in DAY_NAMES
        }
        for department in departments
    }


def _empty_mode_record(mode_name: str):
    departments = list(TEMPLATES[mode_name])
    return {
        "departments": departments,
        "schedule": _empty_schedule_for_departments(departments),
    }


def _empty_week_record(week_start: date):
    iso_week = week_start.isocalendar().week
    week_end = week_start + timedelta(days=6)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_label": f"Saptamana {iso_week}",
        "modes": {mode_name: _empty_mode_record(mode_name) for mode_name in TEMPLATES},
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _guess_mode_for_department(department: str):
    if department in TEMPLATES["Bucle"] or department.upper().startswith("BUCLA"):
        return "Bucle"
    return "Magazie"


class ScheduleStore:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if not SCHEDULE_PATH.exists():
            return {"weeks": {}}

        # Prima incercare: fisierul principal
        try:
            with SCHEDULE_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict) and isinstance(data.get("weeks", {}), dict):
                return {"weeks": data.get("weeks", {})}
            log_warning("schedule_store: structura invalida in fisierul principal, se incearca recovery")
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("schedule_store_load_main", exc)
            log_warning("schedule_store: fisierul principal corupt, se incearca recovery din backup")

        # Recovery automat: cel mai recent backup valid
        return self._load_from_backup()

    def _load_from_backup(self) -> dict:
        """
        Incearca sa incarce datele din cel mai recent backup valid.
        Returneaza {"weeks": {}} daca nu exista niciun backup valid.
        """
        if not BACKUP_DIR.exists():
            return {"weeks": {}}

        backups = sorted(BACKUP_DIR.glob("schedule_backup_*.json"), reverse=True)
        for backup_path in backups:
            try:
                with backup_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("weeks", {}), dict):
                    log_warning(
                        "schedule_store: recovery reusit din backup '%s'",
                        backup_path.name,
                    )
                    return {"weeks": data.get("weeks", {})}
            except (OSError, json.JSONDecodeError) as exc:
                log_exception(f"schedule_store_load_backup_{backup_path.name}", exc)
                continue

        log_warning("schedule_store: niciun backup valid gasit, se porneste gol")
        return {"weeks": {}}

    def save(self):
        """Salveaza datele folosind scriere atomica (temp + os.replace)."""
        SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=SCHEDULE_PATH.parent, suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    json.dump(self.data, tmp, ensure_ascii=False, indent=2)
            except Exception:
                os.unlink(tmp_path)
                raise
            os.replace(tmp_path, SCHEDULE_PATH)
        except OSError as exc:
            log_exception("schedule_store_save", exc)
            raise

    def backup(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if not SCHEDULE_PATH.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(SCHEDULE_PATH, BACKUP_DIR / f"schedule_backup_{timestamp}.json")
        self._rotate_backups()

    def _rotate_backups(self, max_backups: int = 20):
        """Pastreaza doar ultimele max_backups fisiere. Sterge restul."""
        backups = sorted(BACKUP_DIR.glob("schedule_backup_*.json"))
        for old in backups[:-max_backups]:
            try:
                old.unlink()
            except OSError as exc:
                from logic.app_logger import log_warning
                log_warning("schedule_store: nu s-a putut sterge backup vechi %s: %s", old.name, exc)

    def get_week_history(self):
        weeks = self.data.get("weeks", {})
        items = []
        for key, week_record in weeks.items():
            items.append((key, week_record.get("week_label", key), week_record.get("week_end", key)))
        items.sort(key=lambda item: item[0], reverse=True)
        return items

    def get_or_create_week(self, selected_date: date):
        week_start = get_week_start(selected_date)
        week_key = week_start.isoformat()
        weeks = self.data.setdefault("weeks", {})

        if week_key not in weeks:
            weeks[week_key] = _empty_week_record(week_start)
            self.save()

        week_record = deepcopy(weeks[week_key])
        self._normalize_week_record(week_record)
        return week_record

    def update_week(self, week_record):
        self._normalize_week_record(week_record)
        week_record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.backup()
        self.data.setdefault("weeks", {})[week_record["week_start"]] = deepcopy(week_record)
        self.save()

    def duplicate_previous_week(self, selected_date: date):
        current_start = get_week_start(selected_date)
        previous_start = current_start - timedelta(days=7)
        previous_key = previous_start.isoformat()
        weeks = self.data.setdefault("weeks", {})
        if previous_key not in weeks:
            raise ValueError("Nu exista saptamana anterioara pentru duplicare.")

        new_record = deepcopy(weeks[previous_key])
        new_record["week_start"] = current_start.isoformat()
        new_record["week_end"] = (current_start + timedelta(days=6)).isoformat()
        new_record["week_label"] = f"Saptamana {current_start.isocalendar().week}"
        self.update_week(new_record)
        return deepcopy(self.data["weeks"][current_start.isoformat()])

    def clear_weekend(self, week_record, mode_name: str):
        mode_record = week_record["modes"][mode_name]
        for department in mode_record["departments"]:
            for day_name in WEEKEND_DAYS:
                for shift in SHIFTS:
                    mode_record["schedule"][department][day_name][shift] = _empty_cell()

    def clear_department(self, week_record, mode_name: str, department: str):
        mode_record = week_record["modes"][mode_name]
        for day_name in DAY_NAMES:
            for shift in SHIFTS:
                mode_record["schedule"][department][day_name][shift] = _empty_cell()

    def build_assignment_map(self, week_record, mode_name: str):
        result = {}
        mode_record = week_record["modes"][mode_name]
        for department in mode_record["departments"]:
            for day_name in DAY_NAMES:
                for shift in SHIFTS:
                    employees = mode_record["schedule"][department][day_name][shift]["employees"]
                    for employee in employees:
                        key = employee.casefold()
                        result.setdefault(key, []).append(
                            {"employee": employee, "department": department, "day": day_name, "shift": shift}
                        )
        return result

    def validate_assignment(self, week_record, mode_name: str, department: str, day_name: str, shift: str, employee: str):
        mode_record = week_record["modes"][mode_name]
        target_cell = mode_record["schedule"][department][day_name][shift]["employees"]
        if any(existing.casefold() == employee.casefold() for existing in target_cell):
            raise ValueError("Angajatul exista deja in aceasta celula.")

        for other_department in mode_record["departments"]:
            for other_shift in SHIFTS:
                other_cell = mode_record["schedule"][other_department][day_name][other_shift]["employees"]
                for existing in other_cell:
                    if existing.casefold() != employee.casefold():
                        continue
                    if other_department == department and other_shift == shift:
                        raise ValueError("Angajatul exista deja in aceasta celula.")
                    if other_shift == shift:
                        raise ValueError(
                            f"{employee} este deja planificat in {other_department}, {day_name}, {other_shift}."
                        )

    def _normalize_week_record(self, week_record):
        modes = week_record.get("modes")
        if not isinstance(modes, dict) or not modes:
            modes = self._migrate_legacy_week_record(week_record)
            week_record["modes"] = modes

        for mode_name in TEMPLATES:
            mode_record = modes.setdefault(mode_name, _empty_mode_record(mode_name))
            departments = mode_record.get("departments", [])
            if not isinstance(departments, list):
                departments = list(TEMPLATES[mode_name])

            ordered_departments = []
            for department in TEMPLATES[mode_name] + departments:
                if department and department not in ordered_departments:
                    ordered_departments.append(department)
            mode_record["departments"] = ordered_departments

            schedule = mode_record.setdefault("schedule", {})
            for department in ordered_departments:
                department_schedule = schedule.setdefault(department, {})
                for day_name in DAY_NAMES:
                    day_schedule = department_schedule.setdefault(day_name, {})
                    for shift in SHIFTS:
                        cell = day_schedule.get(shift, _empty_cell())
                        if isinstance(cell, str):
                            employees = [line.strip() for line in cell.splitlines() if line.strip()]
                            cell = {"employees": employees, "colors": {}}
                        elif not isinstance(cell, dict):
                            cell = _empty_cell()
                        cell.setdefault("employees", [])
                        # Pastreaza culorile existente si elimina culorile pentru angajati stearsi
                        existing_colors = cell.get("colors", {})
                        if not isinstance(existing_colors, dict):
                            existing_colors = {}
                        unique = []
                        seen = set()
                        for employee in cell["employees"]:
                            if not isinstance(employee, str):
                                continue
                            value = " ".join(employee.split()).strip()
                            if value and value.casefold() not in seen:
                                unique.append(value)
                                seen.add(value.casefold())
                        cell["employees"] = unique
                        # Pastram doar culorile angajatilor ramasi
                        cell["colors"] = {k: v for k, v in existing_colors.items() if any(k.casefold() == e.casefold() for e in unique)}
                        day_schedule[shift] = cell

        week_record.pop("departments", None)
        week_record.pop("schedule", None)

    def _migrate_legacy_week_record(self, week_record):
        legacy_departments = week_record.get("departments", [])
        legacy_schedule = week_record.get("schedule", {})
        migrated_modes = {mode_name: _empty_mode_record(mode_name) for mode_name in TEMPLATES}

        if not isinstance(legacy_departments, list):
            legacy_departments = []
        if not isinstance(legacy_schedule, dict):
            legacy_schedule = {}

        for department in legacy_departments:
            if not isinstance(department, str):
                continue
            name = " ".join(department.split()).strip()
            if not name:
                continue
            mode_name = _guess_mode_for_department(name)
            mode_record = migrated_modes[mode_name]
            if name not in mode_record["departments"]:
                mode_record["departments"].append(name)
            mode_record["schedule"][name] = legacy_schedule.get(name, _empty_schedule_for_departments([name])[name])

        for department, department_schedule in legacy_schedule.items():
            if not isinstance(department, str):
                continue
            name = " ".join(department.split()).strip()
            if not name:
                continue
            mode_name = _guess_mode_for_department(name)
            mode_record = migrated_modes[mode_name]
            if name not in mode_record["departments"]:
                mode_record["departments"].append(name)
            mode_record["schedule"][name] = department_schedule

        return migrated_modes
