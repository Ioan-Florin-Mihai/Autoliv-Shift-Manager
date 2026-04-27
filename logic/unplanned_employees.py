from __future__ import annotations


def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _planned_employee_keys(week_record: dict) -> set[str]:
    planned: set[str] = set()
    modes = week_record.get("modes", {}) if isinstance(week_record, dict) else {}
    if not isinstance(modes, dict):
        return planned

    for mode_record in modes.values():
        if not isinstance(mode_record, dict):
            continue
        schedule = mode_record.get("schedule", {})
        if not isinstance(schedule, dict):
            continue
        for department_schedule in schedule.values():
            if not isinstance(department_schedule, dict):
                continue
            for day_schedule in department_schedule.values():
                if not isinstance(day_schedule, dict):
                    continue
                for cell in day_schedule.values():
                    employees = cell.get("employees", []) if isinstance(cell, dict) else []
                    if not isinstance(employees, list):
                        continue
                    for employee in employees:
                        name = _clean_name(employee)
                        if name:
                            planned.add(name.casefold())
    return planned


def find_unplanned_employees(master_employees: list[str], week_record: dict) -> list[str]:
    """Returneaza angajatii din lista master care nu apar deloc in saptamana."""
    if not isinstance(master_employees, list) or not master_employees:
        return []

    planned = _planned_employee_keys(week_record)
    unique_master: dict[str, str] = {}
    for employee in master_employees:
        name = _clean_name(employee)
        if name:
            unique_master.setdefault(name.casefold(), name)

    missing = [name for key, name in unique_master.items() if key not in planned]
    return sorted(missing, key=str.casefold)
