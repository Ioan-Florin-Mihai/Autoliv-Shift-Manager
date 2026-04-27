from datetime import date

import pytest

from logic.schedule_store import ScheduleStore
from logic.unplanned_employees import find_unplanned_employees


@pytest.fixture()
def store(tmp_path, monkeypatch):
    import logic.schedule_store as store_module

    monkeypatch.setattr(store_module, "SCHEDULE_PATH", tmp_path / "schedule_data.json")
    monkeypatch.setattr(store_module, "BACKUP_DIR", tmp_path / "backups")
    return ScheduleStore()


def test_find_unplanned_employees_ignores_duplicates_and_case(store):
    week = store.get_or_create_week(date(2026, 4, 20))
    week["modes"]["Magazie"]["schedule"]["Sef schimb"]["Luni"]["Sch1"]["employees"] = [
        " Popescu Ion ",
        "Șerban Ana",
    ]

    missing = find_unplanned_employees(
        ["popescu ion", "Popescu Ion", "Șerban Ana", "Ionescu Mihai"],
        week,
    )

    assert missing == ["Ionescu Mihai"]


def test_find_unplanned_employees_empty_master_returns_empty(store):
    week = store.get_or_create_week(date(2026, 4, 20))
    assert find_unplanned_employees([], week) == []


def test_find_unplanned_employees_empty_week_returns_all_master(store):
    week = store.get_or_create_week(date(2026, 4, 20))
    assert find_unplanned_employees(["Badea Ion", "Ana Maria"], week) == ["Ana Maria", "Badea Ion"]
