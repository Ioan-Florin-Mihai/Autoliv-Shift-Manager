"""
Tests pentru logic/schedule_store.py
Acopera: get_or_create_week, validate_assignment, backup recovery.
"""

import json
from datetime import date

import pytest

import logic.schedule_store as store_module
from logic.schedule_store import (
    BUCLE_DEPARTMENTS,
    CORE_DEPARTMENTS,
    DAY_NAMES,
    SHIFTS,
    TEMPLATES,
    ScheduleStore,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirecteaza caile fisierelor catre un director temporar."""
    monkeypatch.setattr(store_module, "SCHEDULE_PATH", tmp_path / "schedule_data.json")
    monkeypatch.setattr(store_module, "BACKUP_DIR",    tmp_path / "backups")


@pytest.fixture()
def store():
    return ScheduleStore()


# ── get_or_create_week ────────────────────────────────────────────────────────

class TestGetOrCreateWeek:
    def test_creates_new_week(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        assert "week_start" in week
        assert "modes" in week

    def test_week_start_is_monday(self, store):
        # 9 April 2026 = Thursday
        week = store.get_or_create_week(date(2026, 4, 9))
        monday = date.fromisoformat(week["week_start"])
        assert monday.weekday() == 0   # Monday = 0

    def test_same_week_returns_same_record(self, store):
        d1 = date(2026, 4, 7)   # Monday
        d2 = date(2026, 4, 10)  # Thursday same week
        w1 = store.get_or_create_week(d1)
        w2 = store.get_or_create_week(d2)
        assert w1["week_start"] == w2["week_start"]

    def test_week_has_all_modes(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        for mode_name in TEMPLATES:
            assert mode_name in week["modes"]

    def test_all_days_present_in_mode(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        for mode_name in TEMPLATES:
            mode = week["modes"][mode_name]
            for dept in mode["departments"]:
                sched = mode["schedule"][dept]
                for day in DAY_NAMES:
                    assert day in sched

    def test_requested_departments_exist_in_templates(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        assert week["modes"]["Magazie"]["departments"][:len(CORE_DEPARTMENTS)] == CORE_DEPARTMENTS
        assert week["modes"]["Bucle"]["departments"][:len(BUCLE_DEPARTMENTS)] == BUCLE_DEPARTMENTS

    def test_each_department_has_full_schedule_structure(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        for mode in week["modes"].values():
            for department in mode["departments"]:
                for day in DAY_NAMES:
                    for shift in SHIFTS:
                        cell = mode["schedule"][department][day][shift]
                        assert cell == {"employees": [], "colors": {}}

    def test_new_week_does_not_copy_previous_week_assignments(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        cell = week["modes"]["Magazie"]["schedule"]["Sef schimb"]["Luni"]["Sch1"]
        cell["employees"].append("Ion Pop")
        cell["colors"]["Ion Pop"] = "#C0392B"
        store.update_week(week)

        next_week = store.get_or_create_week(date(2026, 4, 14))

        for mode in next_week["modes"].values():
            for department in mode["departments"]:
                for day in DAY_NAMES:
                    for shift in SHIFTS:
                        cell = mode["schedule"][department][day][shift]
                        assert cell == {"employees": [], "colors": {}}

    def test_missing_departments_are_restored_for_existing_week(self, store):
        week = store.get_or_create_week(date(2026, 4, 7))
        week["modes"]["Bucle"]["departments"] = ["BUCLA 02"]
        week["modes"]["Bucle"]["schedule"] = {
            "BUCLA 02": week["modes"]["Bucle"]["schedule"]["BUCLA 02"]
        }

        store._normalize_week_record(week)

        for department in BUCLE_DEPARTMENTS:
            assert department in week["modes"]["Bucle"]["departments"]
            assert department in week["modes"]["Bucle"]["schedule"]
            for day in DAY_NAMES:
                for shift in SHIFTS:
                    assert "employees" in week["modes"]["Bucle"]["schedule"][department][day][shift]
                    assert "colors" in week["modes"]["Bucle"]["schedule"][department][day][shift]

    def test_legacy_department_names_are_mapped_to_requested_names(self, store):
        legacy_week = {
            "week_start": "2026-04-06",
            "week_end": "2026-04-12",
            "week_label": "Saptamana 15",
            "departments": ["Sef Schimb", "BUCLA RA + RB"],
            "schedule": {
                "Sef Schimb": {
                    day: {shift: {"employees": [], "colors": {}} for shift in SHIFTS}
                    for day in DAY_NAMES
                },
                "BUCLA RA + RB": {
                    day: {shift: {"employees": [], "colors": {}} for shift in SHIFTS}
                    for day in DAY_NAMES
                },
            },
        }

        store._normalize_week_record(legacy_week)

        assert "Sef schimb" in legacy_week["modes"]["Magazie"]["departments"]
        assert "BUCLA RA+RB" in legacy_week["modes"]["Bucle"]["departments"]


# ── validate_assignment ───────────────────────────────────────────────────────

class TestValidateAssignment:
    def test_valid_assignment(self, store):
        week  = store.get_or_create_week(date(2026, 4, 7))
        mode  = list(TEMPLATES.keys())[0]
        dept  = week["modes"][mode]["departments"][0]
        day   = DAY_NAMES[0]
        shift = SHIFTS[0]
        # Nu ar trebui sa arunce exceptie
        store.validate_assignment(week, mode, dept, day, shift, "Andrei Pop")

    def test_duplicate_in_same_cell_raises(self, store):
        week  = store.get_or_create_week(date(2026, 4, 7))
        mode  = list(TEMPLATES.keys())[0]
        dept  = week["modes"][mode]["departments"][0]
        day   = DAY_NAMES[0]
        shift = SHIFTS[0]
        week["modes"][mode]["schedule"][dept][day][shift]["employees"].append("Maria Ion")
        with pytest.raises(ValueError, match="deja"):
            store.validate_assignment(week, mode, dept, day, shift, "Maria Ion")

    def test_8h_in_other_shift_same_day_raises(self, store):
        """8h nu poate fi alocat in doua schimburi in aceeasi zi."""
        week  = store.get_or_create_week(date(2026, 4, 7))
        mode  = list(TEMPLATES.keys())[0]
        dept  = week["modes"][mode]["departments"][0]
        day   = DAY_NAMES[0]
        shift1 = SHIFTS[0]
        shift2 = SHIFTS[1]
        week["modes"][mode]["schedule"][dept][day][shift1]["employees"].append("Vasile Dan")
        with pytest.raises(ValueError, match="8h"):
            store.validate_assignment(week, mode, dept, day, shift2, "Vasile Dan")

    def test_8h_same_shift_multiple_departments_allowed(self, store):
        """8h poate fi alocat pe mai multe functii/zone in acelasi schimb."""
        week = store.get_or_create_week(date(2026, 4, 7))
        mode = list(TEMPLATES.keys())[0]
        departments = week["modes"][mode]["departments"]
        assert len(departments) >= 2
        dept1, dept2 = departments[0], departments[1]
        day = DAY_NAMES[0]
        shift = SHIFTS[0]
        week["modes"][mode]["schedule"][dept1][day][shift]["employees"].append("Ion Pop")
        store.validate_assignment(week, mode, dept2, day, shift, "Ion Pop")

    def test_12h_consecutive_shifts_allowed(self, store):
        """12h poate avea doua schimburi consecutive in aceeasi zi."""
        week = store.get_or_create_week(date(2026, 4, 7))
        mode = list(TEMPLATES.keys())[0]
        dept = week["modes"][mode]["departments"][0]
        day = DAY_NAMES[0]
        shift1 = SHIFTS[0]
        shift2 = SHIFTS[1]
        cell1 = week["modes"][mode]["schedule"][dept][day][shift1]
        cell1["employees"].append("Vasile Dan")
        cell1.setdefault("colors", {})["Vasile Dan"] = "#C0392B"
        store.validate_assignment(week, mode, dept, day, shift2, "Vasile Dan")

    def test_12h_non_consecutive_shifts_raise(self, store):
        """12h pe Sch1 + Sch3 este invalid (neconsecutiv)."""
        week = store.get_or_create_week(date(2026, 4, 7))
        mode = list(TEMPLATES.keys())[0]
        dept = week["modes"][mode]["departments"][0]
        day = DAY_NAMES[0]
        shift1 = SHIFTS[0]
        shift3 = SHIFTS[2]
        cell1 = week["modes"][mode]["schedule"][dept][day][shift1]
        cell1["employees"].append("Vasile Dan")
        cell1.setdefault("colors", {})["Vasile Dan"] = "#C0392B"
        with pytest.raises(ValueError, match="consecutive"):
            store.validate_assignment(week, mode, dept, day, shift3, "Vasile Dan")


# ── Backup recovery ───────────────────────────────────────────────────────────

class TestBackupRecovery:
    def test_corrupt_main_file_loads_from_backup(self, store, tmp_path, monkeypatch):
        # Creeaza o saptamana salvata ca backup manual
        week = store.get_or_create_week(date(2026, 4, 7))
        store.save()   # salveaza fisierul principal

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(exist_ok=True)
        good_data  = {"weeks": {week["week_start"]: week}}
        (backup_dir / "schedule_backup_20260407_120000.json").write_text(
            json.dumps(good_data), encoding="utf-8"
        )

        # Corupe fisierul principal
        corrupt_path = tmp_path / "schedule_data.json"
        corrupt_path.write_text("{corrupt}", encoding="utf-8")

        # Incarcam un store nou — trebuie sa faca recovery
        recovered = ScheduleStore()
        assert week["week_start"] in recovered.data["weeks"]

    def test_missing_main_returns_empty(self, store):
        # Niciun fisier, niciun backup
        fresh = ScheduleStore()
        assert fresh.data == {"weeks": {}}


# ── Atomic save ───────────────────────────────────────────────────────────────

class TestAtomicSave:
    def test_save_creates_file(self, store):
        store.get_or_create_week(date(2026, 4, 7))
        assert store_module.SCHEDULE_PATH.exists()

    def test_save_produces_valid_json(self, store):
        store.get_or_create_week(date(2026, 4, 7))
        store.save()
        text = store_module.SCHEDULE_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        assert "weeks" in data
