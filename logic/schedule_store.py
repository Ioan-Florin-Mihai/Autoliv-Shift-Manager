import json
from copy import deepcopy
from datetime import date, datetime, timedelta

from logic.app_config import get_config
from logic.app_logger import log_exception, log_info, log_warning
from logic.app_paths import BACKUP_DIR, SCHEDULE_DRAFT, SCHEDULE_LEGACY, SCHEDULE_LIVE
from logic.audit_logger import log_event
from logic.auth import is_admin as auth_is_admin
from logic.constants import HOURS_12_COLOR
from logic.tv_update import trigger_tv_update
from logic.utils.io import atomic_write_json

DRAFT_SCHEDULE_PATH = SCHEDULE_DRAFT
LIVE_SCHEDULE_PATH = SCHEDULE_LIVE
LEGACY_SCHEDULE_PATH = SCHEDULE_LEGACY

# Alias de compatibilitate inversa folosit de teste si importuri legacy.
SCHEDULE_PATH = DRAFT_SCHEDULE_PATH


def _write_empty_schedule(path):
    if path.exists():
        return
    _write_json_atomic(path, {"weeks": {}})


def _write_json_atomic(path, payload: dict):
    log_info("[STORE] Writing data to: %s", path)
    atomic_write_json(path, payload)


def _bootstrap_schedule_files():
    """
        Initializeaza stocarea draft/live la pornire.
        Ordinea migrarii:
            1. schedule_data.json legacy -> schedule_draft.json (o singura data)
            2. schedule_draft.json -> schedule_live.json (daca live lipseste)
            3. fallback la structuri goale
    """
    DRAFT_SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DRAFT_SCHEDULE_PATH.exists():
        if LEGACY_SCHEDULE_PATH.exists():
            try:
                legacy_data = json.loads(LEGACY_SCHEDULE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                legacy_data = {"weeks": {}}
            if not isinstance(legacy_data, dict) or not isinstance(legacy_data.get("weeks", {}), dict):
                legacy_data = {"weeks": {}}
            _write_json_atomic(DRAFT_SCHEDULE_PATH, legacy_data)
        else:
            _write_empty_schedule(DRAFT_SCHEDULE_PATH)

    if not LIVE_SCHEDULE_PATH.exists():
        if DRAFT_SCHEDULE_PATH.exists():
            try:
                draft_data = json.loads(DRAFT_SCHEDULE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                draft_data = {"weeks": {}}
            if not isinstance(draft_data, dict) or not isinstance(draft_data.get("weeks", {}), dict):
                draft_data = {"weeks": {}}
            _write_json_atomic(LIVE_SCHEDULE_PATH, draft_data)
        else:
            _write_empty_schedule(LIVE_SCHEDULE_PATH)


_bootstrap_schedule_files()

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

CORE_DEPARTMENTS = [
    "Sef schimb",
    "Retragere finite",
    "Balotare ambalare",
    "Etichetare scanare",
    "Livrari",
    "Receptii",
]

BUCLE_DEPARTMENTS = [
    "BUCLA 01",
    "BUCLA 02",
    "BUCLA 03",
    "BUCLA 04",
    "BUCLA 05",
    "BUCLA TA+TB",
    "BUCLA RA+RB",
    "Ambalaje",
]

TEMPLATES = {
    "Magazie": CORE_DEPARTMENTS,
    "Bucle": BUCLE_DEPARTMENTS,
}

DEPARTMENT_COLORS = {
    "Sef schimb": "5B9BD5",
    "Retragere finite": "D9A35F",
    "Balotare ambalare": "D9E2F3",
    "Etichetare scanare": "C9B0D9",
    "Livrari": "A9D18E",
    "Receptii": "4472C4",
    "BUCLA 01": "D9A35F",
    "BUCLA 02": "D9A35F",
    "BUCLA 03": "D9A35F",
    "BUCLA 04": "D9A35F",
    "BUCLA 05": "D9A35F",
    "BUCLA TA+TB": "D9A35F",
    "BUCLA RA+RB": "D9A35F",
    "Ambalaje": "D99694",
}

DEPARTMENT_ALIASES = {
    "Sef Schimb": "Sef schimb",
    "Etichetare Scanare": "Etichetare scanare",
    "Balotare Ambalare": "Balotare ambalare",
    "BUCLA TA + TB": "BUCLA TA+TB",
    "BUCLA RA + RB": "BUCLA RA+RB",
    "BUCLA 05 + 07": "BUCLA 05",
}

# Tipuri de absență — nu se validează pentru double-booking
ABSENCE_TYPE_NAMES: frozenset[str] = frozenset({"CO", "CM", "ABSENT"})


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


def _canonical_department_name(department: str) -> str:
    normalized = " ".join(department.split()).strip()
    if not normalized:
        return ""
    return DEPARTMENT_ALIASES.get(normalized, normalized)


def _merge_department_order(mode_name: str, departments: list[str]) -> list[str]:
    ordered_departments: list[str] = []
    for department in list(TEMPLATES[mode_name]) + list(departments):
        canonical_department = _canonical_department_name(department) if isinstance(department, str) else ""
        if canonical_department and canonical_department not in ordered_departments:
            ordered_departments.append(canonical_department)
    return ordered_departments


def _ensure_mode_schedule_structure(mode_name: str, mode_record: dict):
    departments = mode_record.get("departments", [])
    if not isinstance(departments, list):
        departments = list(TEMPLATES[mode_name])

    ordered_departments = _merge_department_order(mode_name, departments)
    mode_record["departments"] = ordered_departments

    schedule = mode_record.setdefault("schedule", {})
    if not isinstance(schedule, dict):
        schedule = {}
        mode_record["schedule"] = schedule

    aliased_schedule: dict[str, dict] = {}
    for department, department_schedule in list(schedule.items()):
        if not isinstance(department, str):
            continue
        canonical_department = _canonical_department_name(department)
        if not canonical_department:
            continue
        if canonical_department in aliased_schedule and isinstance(aliased_schedule[canonical_department], dict) and not aliased_schedule[canonical_department]:
            aliased_schedule[canonical_department] = department_schedule
        elif canonical_department not in aliased_schedule:
            aliased_schedule[canonical_department] = department_schedule
    schedule.clear()
    schedule.update(aliased_schedule)

    for department in ordered_departments:
        department_schedule = schedule.setdefault(department, {})
        if not isinstance(department_schedule, dict):
            department_schedule = {}
            schedule[department] = department_schedule
        for day_name in DAY_NAMES:
            day_schedule = department_schedule.setdefault(day_name, {})
            if not isinstance(day_schedule, dict):
                day_schedule = {}
                department_schedule[day_name] = day_schedule
            for shift in SHIFTS:
                cell = day_schedule.get(shift, _empty_cell())
                if isinstance(cell, str):
                    employees = [line.strip() for line in cell.splitlines() if line.strip()]
                    cell = {"employees": employees, "colors": {}}
                elif not isinstance(cell, dict):
                    cell = _empty_cell()
                cell.setdefault("employees", [])
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
                cell["colors"] = {k: v for k, v in existing_colors.items() if any(k.casefold() == e.casefold() for e in unique)}
                day_schedule[shift] = cell

    return ordered_departments


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
    canonical_department = _canonical_department_name(department)
    if canonical_department in TEMPLATES["Bucle"] or canonical_department.upper().startswith("BUCLA"):
        return "Bucle"
    return "Magazie"


class ScheduleStore:
    def __init__(self):
        self.schedule_path = SCHEDULE_PATH
        self.data = self._load()

    def _assert_not_locked(self, week_record):
        if week_record.get("locked"):
            raise ValueError("Săptămâna este publicată (read-only). Deblocă înainte de a edita.")

    def is_admin(self, user: str | None) -> bool:
        return bool(user) and auth_is_admin(str(user))

    def _require_admin(self, user: str | None) -> None:
        if not self.is_admin(user):
            raise PermissionError("Unauthorized")

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
        self.schedule_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_json(self.schedule_path, self.data)
        except OSError as exc:
            log_exception("schedule_store_save", exc)
            raise

    def _save_live_snapshot(self):
        """Scrie snapshot-ul publicat (read-only pentru TV) in schedule_live.json."""
        try:
            _write_json_atomic(LIVE_SCHEDULE_PATH, self.data)
        except OSError as exc:
            log_exception("schedule_store_save_live", exc)
            raise

    def _publish_and_notify(self) -> None:
        """Scrie live snapshot și incrementează versiunea TV în aceeași secvență atomică."""
        self._save_live_snapshot()
        trigger_tv_update()

    def backup(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _write_json_atomic(BACKUP_DIR / f"schedule_backup_{timestamp}.json", self.data)
        daily_name = datetime.now().strftime("schedule_daily_%Y%m%d.json")
        daily_path = BACKUP_DIR / daily_name
        if not daily_path.exists():
            _write_json_atomic(daily_path, self.data)
        self._rotate_backups()

    def _rotate_backups(self, max_backups: int | None = None):
        """Pastreaza doar ultimele backup-uri rapide conform configuratiei. Snapshot-urile zilnice raman separate."""
        if max_backups is None:
            max_backups = int(get_config().get("max_backups", 20))
        backups = sorted(BACKUP_DIR.glob("schedule_backup_*.json"))
        for old in backups[:-max_backups]:
            try:
                old.unlink()
            except OSError as exc:
                from logic.app_logger import log_warning
                log_warning("schedule_store: nu s-a putut sterge backup vechi %s: %s", old.name, exc)

    def get_backup_history(self):
        if not BACKUP_DIR.exists():
            return []
        items = []
        for backup_path in sorted(BACKUP_DIR.glob("schedule_*.json"), reverse=True):
            items.append((backup_path.name, backup_path.stat().st_mtime))
        return items

    def restore_backup(self, backup_name: str):
        backup_path = BACKUP_DIR / backup_name
        if not backup_path.exists():
            raise ValueError("Backup-ul selectat nu exista.")
        try:
            with backup_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict) or not isinstance(data.get("weeks", {}), dict):
                raise ValueError("Backup invalid.")
            self.data = {"weeks": data.get("weeks", {})}
            self.save()
            self._save_live_snapshot()
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("schedule_store_restore_backup", exc)
            raise ValueError("Backup-ul nu a putut fi restaurat.") from exc

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
        self._assert_not_locked(week_record)
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

    def clear_weekend(self, week_record, mode_name: str, user: str):
        self._require_admin(user)
        self._assert_not_locked(week_record)
        mode_record = week_record["modes"][mode_name]
        for department in mode_record["departments"]:
            for day_name in WEEKEND_DAYS:
                for shift in SHIFTS:
                    mode_record["schedule"][department][day_name][shift] = _empty_cell()

    def clear_department(self, week_record, mode_name: str, department: str, user: str):
        self._require_admin(user)
        self._assert_not_locked(week_record)
        mode_record = week_record["modes"][mode_name]
        for day_name in DAY_NAMES:
            for shift in SHIFTS:
                mode_record["schedule"][department][day_name][shift] = _empty_cell()

    def lock_week(self, week_ref, user: str | None = None) -> None:
        """Blocheaza saptamana dupa key ISO (YYYY-MM-DD) sau dupa week_record."""
        self._require_admin(user)
        if isinstance(week_ref, str):
            week_record = deepcopy(self.data.get("weeks", {}).get(week_ref) or {})
            if not week_record:
                raise ValueError("Săptămâna nu există.")
        else:
            week_record = deepcopy(week_ref)
        self._normalize_week_record(week_record)
        week_record["locked"] = True
        week_record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.data.setdefault("weeks", {})[week_record["week_start"]] = deepcopy(week_record)
        self.save()

    def publish_week(self, week_key: str, user: str) -> None:
        """
        Publica atomic o saptamana in fluxul draft -> live.
        Pasii sunt executati integral in store:
          1) valideaza saptamana
          2) salveaza draft
          3) scrie live cu temp file
          4) replace live cu os.replace
          5) blocheaza saptamana
          6) adauga eveniment in audit log
        """
        self._require_admin(user)

        week_record = deepcopy(self.data.get("weeks", {}).get(week_key) or {})
        if not week_record:
            raise ValueError("Săptămâna nu există.")

        self._normalize_week_record(week_record)
        if week_record.get("week_start") != week_key:
            raise ValueError("Săptămâna are date invalide pentru publicare.")
        if not isinstance(week_record.get("modes"), dict) or not week_record.get("modes"):
            raise ValueError("Datele săptămânii sunt incomplete.")
        week_record["locked"] = True
        week_record["published_at"] = datetime.now().isoformat(timespec="seconds")
        week_record["published_by"] = user

        previous_data = deepcopy(self.data)
        self.data.setdefault("weeks", {})[week_record["week_start"]] = deepcopy(week_record)
        try:
            # Draft write (atomic)
            self.save()
            # Live write + TV version bump (atomic sequence)
            self._publish_and_notify()
        except Exception:
            self.data = previous_data
            self.save()
            raise

        log_event(
            action="publish",
            user=user,
            week=week_key,
            details={"week_start": week_record["week_start"]},
        )

    def unlock_week(self, week_record: dict, user: str | None = None) -> None:
        """Deblocă săptămâna pentru editare."""
        self._require_admin(user)
        self._normalize_week_record(week_record)
        week_record["locked"] = False
        week_record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.data.setdefault("weeks", {})[week_record["week_start"]] = deepcopy(week_record)
        self.save()

    def delete_employee(self, employee: str, user: str) -> int:
        """Sterge global un angajat din toate celulele de planificare draft."""
        self._require_admin(user)
        removed = 0
        employee_cf = employee.casefold()
        for week_rec in self.data.get("weeks", {}).values():
            if not isinstance(week_rec, dict):
                continue
            self._normalize_week_record(week_rec)
            for mode_rec in week_rec.get("modes", {}).values():
                if not isinstance(mode_rec, dict):
                    continue
                for dept_sched in mode_rec.get("schedule", {}).values():
                    for day_sched in dept_sched.values():
                        for cell in day_sched.values():
                            if not isinstance(cell, dict):
                                continue
                            employees = cell.get("employees", [])
                            before = len(employees)
                            cell["employees"] = [
                                value for value in employees
                                if not isinstance(value, str) or value.casefold() != employee_cf
                            ]
                            removed += before - len(cell["employees"])
                            colors = cell.get("colors", {})
                            if isinstance(colors, dict):
                                for key in list(colors.keys()):
                                    if isinstance(key, str) and key.casefold() == employee_cf:
                                        colors.pop(key, None)
        if removed > 0:
            self.save()
        return removed

    def is_week_locked(self, week_ref) -> bool:
        if isinstance(week_ref, str):
            week_record = self.data.get("weeks", {}).get(week_ref) or {}
            return bool(week_record.get("locked", False))
        return bool((week_ref or {}).get("locked", False))

    def build_assignment_map(self, week_record, mode_name: str):
        result: dict[str, list[dict[str, str]]] = {}
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

    def _employee_shift_assignments_for_day(
        self,
        week_record,
        mode_name: str,
        day_name: str,
        employee: str,
        ignore_assignment: tuple[str, str] | None = None,
    ):
        mode_record = week_record["modes"][mode_name]
        assignments = []
        for other_department in mode_record["departments"]:
            for other_shift in SHIFTS:
                if ignore_assignment and ignore_assignment == (other_department, other_shift):
                    continue
                cell = mode_record["schedule"][other_department][day_name][other_shift]
                employees = cell.get("employees", [])
                if any(existing.casefold() == employee.casefold() for existing in employees):
                    assignments.append((other_department, other_shift, cell))
        return assignments

    def _employee_hours_for_day(self, assignments: list[tuple[str, str, dict]], employee: str) -> str:
        for _department, _shift, cell in assignments:
            colors = cell.get("colors", {}) if isinstance(cell, dict) else {}
            if not isinstance(colors, dict):
                continue
            for key, value in colors.items():
                if isinstance(key, str) and key.casefold() == employee.casefold():
                    if str(value or "").strip().upper().lstrip("#") == HOURS_12_COLOR:
                        return "12h"
        return "8h"

    def validate_assignment(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        shift: str,
        employee: str,
        ignore_assignment: tuple[str, str] | None = None,
    ):
        self._assert_not_locked(week_record)

        mode_record = week_record["modes"][mode_name]
        target_cell = mode_record["schedule"][department][day_name][shift]["employees"]
        if any(existing.casefold() == employee.casefold() for existing in target_cell):
            raise ValueError("Angajatul exista deja in aceasta celula.")

        # Absențele (CO/CM/ABSENT) nu sunt validate pentru double-booking
        if employee.strip().upper() in ABSENCE_TYPE_NAMES:
            return

        assignments = self._employee_shift_assignments_for_day(
            week_record,
            mode_name,
            day_name,
            employee,
            ignore_assignment=ignore_assignment,
        )
        existing_shifts = {assigned_shift for _dept, assigned_shift, _cell in assignments}

        if shift in existing_shifts:
            raise ValueError(f"{employee} este deja planificat in {day_name}, {shift}.")

        if not assignments:
            return

        hours_type = self._employee_hours_for_day(assignments, employee)
        candidate_shifts = existing_shifts | {shift}

        if hours_type == "8h":
            raise ValueError("Angajatul are deja 8h alocat in aceasta zi.")

        if len(candidate_shifts) > 2:
            raise ValueError("Angajatul cu 12h poate avea maximum doua schimburi in aceeasi zi.")

        shift_indexes = sorted(SHIFTS.index(value) for value in candidate_shifts)
        if len(shift_indexes) == 2 and shift_indexes[1] - shift_indexes[0] != 1:
            raise ValueError("12h trebuie sa fie pe schimburi consecutive.")

    def add_employee_assignment(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        shift: str,
        employee: str,
        default_color: str | None = None,
    ):
        self._assert_not_locked(week_record)
        self.validate_assignment(week_record, mode_name, department, day_name, shift, employee)
        cell = week_record["modes"][mode_name]["schedule"][department][day_name][shift]
        cell.setdefault("employees", []).append(employee)
        if default_color:
            cell.setdefault("colors", {})[employee] = default_color

    def remove_employee_assignment(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        shift: str,
        employee: str,
    ):
        self._assert_not_locked(week_record)
        cell = week_record["modes"][mode_name]["schedule"][department][day_name][shift]
        cell["employees"] = [value for value in cell.get("employees", []) if value.casefold() != employee.casefold()]
        colors = cell.get("colors", {})
        if isinstance(colors, dict):
            for key in list(colors.keys()):
                if isinstance(key, str) and key.casefold() == employee.casefold():
                    colors.pop(key, None)

    def reorder_employee_assignment(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        shift: str,
        employee: str,
        direction: int,
    ):
        self._assert_not_locked(week_record)
        employees = week_record["modes"][mode_name]["schedule"][department][day_name][shift]["employees"]
        index = next((i for i, value in enumerate(employees) if value.casefold() == employee.casefold()), None)
        if index is None:
            return
        target = index + direction
        if target < 0 or target >= len(employees):
            return
        employees[index], employees[target] = employees[target], employees[index]

    def move_employee_assignment(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        source_shift: str,
        target_shift: str,
        employee: str,
    ):
        self._assert_not_locked(week_record)
        source_cell = week_record["modes"][mode_name]["schedule"][department][day_name][source_shift]
        source_colors = source_cell.get("colors", {}) if isinstance(source_cell, dict) else {}
        carry_color = None
        if isinstance(source_colors, dict):
            for key, value in source_colors.items():
                if isinstance(key, str) and key.casefold() == employee.casefold():
                    carry_color = value
                    break

        self.validate_assignment(
            week_record,
            mode_name,
            department,
            day_name,
            target_shift,
            employee,
            ignore_assignment=(department, source_shift),
        )

        self.remove_employee_assignment(week_record, mode_name, department, day_name, source_shift, employee)
        target_cell = week_record["modes"][mode_name]["schedule"][department][day_name][target_shift]
        target_cell.setdefault("employees", []).append(employee)
        if carry_color:
            target_cell.setdefault("colors", {})[employee] = carry_color

    def set_employee_color(
        self,
        week_record,
        mode_name: str,
        department: str,
        day_name: str,
        shift: str,
        employee: str,
        color: str | None,
    ):
        self._assert_not_locked(week_record)
        cell = week_record["modes"][mode_name]["schedule"][department][day_name][shift]
        colors = cell.setdefault("colors", {})
        existing_key = next(
            (key for key in colors if isinstance(key, str) and key.casefold() == employee.casefold()),
            None,
        )
        if color is None:
            if existing_key:
                colors.pop(existing_key, None)
            return
        colors[existing_key or employee] = color

    def add_department(self, week_record, mode_name: str, department: str):
        self._assert_not_locked(week_record)
        mode_record = week_record["modes"][mode_name]
        if department in mode_record["departments"]:
            raise ValueError("Departamentul exista deja in modul curent.")
        mode_record["departments"].append(department)
        mode_record["schedule"][department] = {
            day: {shift: _empty_cell() for shift in SHIFTS}
            for day in DAY_NAMES
        }

    def rename_employee_everywhere(self, old_name: str, new_name: str, skip_locked: bool = True) -> int:
        """
        Redenumeste un angajat in toate saptamanile draft si actualizeaza cheile de culoare.
        Implicit, saptamanile blocate raman neschimbate.
        """
        count = 0
        old_cf = old_name.casefold()
        for week_rec in self.data.get("weeks", {}).values():
            if not isinstance(week_rec, dict):
                continue
            if skip_locked and self.is_week_locked(week_rec):
                continue
            self._normalize_week_record(week_rec)
            for mode_rec in week_rec.get("modes", {}).values():
                if not isinstance(mode_rec, dict):
                    continue
                for dept_sched in mode_rec.get("schedule", {}).values():
                    for day_sched in dept_sched.values():
                        for cell in day_sched.values():
                            if not isinstance(cell, dict):
                                continue
                            employees = cell.get("employees", [])
                            for i, emp in enumerate(employees):
                                if isinstance(emp, str) and emp.casefold() == old_cf:
                                    employees[i] = new_name
                                    count += 1
                            colors = cell.get("colors", {})
                            if isinstance(colors, dict):
                                for k in list(colors.keys()):
                                    if isinstance(k, str) and k.casefold() == old_cf:
                                        colors[new_name] = colors.pop(k)
        if count > 0:
            self.save()
        return count

    def _normalize_week_record(self, week_record):
        modes = week_record.get("modes")
        if not isinstance(modes, dict) or not modes:
            modes = self._migrate_legacy_week_record(week_record)
            week_record["modes"] = modes

        for mode_name in TEMPLATES:
            mode_record = modes.setdefault(mode_name, _empty_mode_record(mode_name))
            _ensure_mode_schedule_structure(mode_name, mode_record)

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
            name = _canonical_department_name(department)
            if not name:
                continue
            mode_name = _guess_mode_for_department(name)
            mode_record = migrated_modes[mode_name]
            if name not in mode_record["departments"]:
                mode_record["departments"].append(name)
            source_schedule = legacy_schedule.get(department, legacy_schedule.get(name, _empty_schedule_for_departments([name])[name]))
            mode_record["schedule"][name] = source_schedule

        for department, department_schedule in legacy_schedule.items():
            if not isinstance(department, str):
                continue
            name = _canonical_department_name(department)
            if not name:
                continue
            mode_name = _guess_mode_for_department(name)
            mode_record = migrated_modes[mode_name]
            if name not in mode_record["departments"]:
                mode_record["departments"].append(name)
            mode_record["schedule"][name] = department_schedule

        return migrated_modes
