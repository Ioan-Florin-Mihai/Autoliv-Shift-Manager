"""
Tests pentru logic/employee_store.py
Acopera: _normalize_names, search, add_employee, delete_employee, rename_employee.
Fara acces real la disc: EMPLOYEES_PATH este redirectata la tmp_path.
"""

import json
from pathlib import Path

import pytest

import logic.employee_store as emp_module
from logic.employee_store import EmployeeStore


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Redirecteaza calea fisierului si dezactiveaza colectarea din planificari."""
    fake_path = tmp_path / "employees.json"
    monkeypatch.setattr(emp_module, "EMPLOYEES_PATH", fake_path)
    # Dezactivam colectarea din schedule/cache — nu avem fisiere reale
    monkeypatch.setattr(
        EmployeeStore,
        "_collect_schedule_names",
        lambda self, seen: [],
    )


@pytest.fixture()
def populated_store(tmp_path, monkeypatch):
    """EmployeeStore preincärcat cu cateva angajati."""
    emp_path = tmp_path / "employees.json"
    emp_path.write_text(
        json.dumps({"employees": ["Andrei Pop", "Maria Ion", "Vasile Dan"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(emp_module, "EMPLOYEES_PATH", emp_path)
    monkeypatch.setattr(
        EmployeeStore,
        "_collect_schedule_names",
        lambda self, seen: [],
    )
    return EmployeeStore()


# ── _normalize_names ──────────────────────────────────────────────────────────

class TestNormalizeNames:
    def test_removes_duplicates_case_insensitive(self, populated_store):
        result, seen = populated_store._normalize_names(["Ana Pop", "ana pop", "ANA POP"])
        assert len(result) == 1

    def test_strips_extra_spaces(self, populated_store):
        result, _ = populated_store._normalize_names(["  Vasile   Dan  "])
        assert result[0] == "Vasile Dan"

    def test_sorted_alphabetically(self, populated_store):
        result, _ = populated_store._normalize_names(["Zara X", "Ana Y"])
        assert result[0].startswith("Ana")
        assert result[1].startswith("Zara")

    def test_non_string_entries_ignored(self, populated_store):
        result, _ = populated_store._normalize_names(["Valid Nume", None, 123, ""])
        assert result == ["Valid Nume"]


# ── search ────────────────────────────────────────────────────────────────────

class TestSearch:
    def test_empty_query_returns_all(self, populated_store):
        results = populated_store.search("")
        assert len(results) == 3

    def test_partial_match_case_insensitive(self, populated_store):
        results = populated_store.search("andrei")
        assert any("Andrei" in r for r in results)

    def test_no_match_returns_empty(self, populated_store):
        results = populated_store.search("xxxxxxxxx")
        assert results == []

    def test_search_returns_list(self, populated_store):
        assert isinstance(populated_store.search(""), list)


# ── add_employee ──────────────────────────────────────────────────────────────

class TestAddEmployee:
    def test_add_new_employee(self, populated_store):
        populated_store.add_employee("Ionescu Radu")
        assert "Ionescu Radu" in populated_store.data["employees"]

    def test_duplicate_not_added(self, populated_store):
        count_before = len(populated_store.data["employees"])
        populated_store.add_employee("andrei pop")   # duplicat case-insensitive
        assert len(populated_store.data["employees"]) == count_before

    def test_empty_string_raises(self, populated_store):
        with pytest.raises(ValueError):
            populated_store.add_employee("   ")


# ── delete_employee ───────────────────────────────────────────────────────────

class TestDeleteEmployee:
    def test_delete_existing(self, populated_store):
        populated_store.delete_employee("Maria Ion")
        assert "Maria Ion" not in populated_store.data["employees"]

    def test_delete_case_insensitive(self, populated_store):
        populated_store.delete_employee("maria ion")
        assert "Maria Ion" not in populated_store.data["employees"]

    def test_delete_nonexistent_returns_false(self, populated_store):
        result = populated_store.delete_employee("Nimeni Altcineva")
        assert result is False

    def test_delete_count(self, populated_store):
        count_before = len(populated_store.data["employees"])
        populated_store.delete_employee("Andrei Pop")
        assert len(populated_store.data["employees"]) == count_before - 1


# ── rename_employee ───────────────────────────────────────────────────────────

class TestRenameEmployee:
    def test_rename_updates_name(self, populated_store):
        populated_store.rename_employee("Andrei Pop", "Andrei Popescu")
        assert "Andrei Popescu" in populated_store.data["employees"]
        assert "Andrei Pop"     not in populated_store.data["employees"]

    def test_rename_to_existing_raises(self, populated_store):
        with pytest.raises(ValueError):
            populated_store.rename_employee("Andrei Pop", "Maria Ion")

    def test_rename_empty_old_raises(self, populated_store):
        with pytest.raises(ValueError):
            populated_store.rename_employee("", "Alt Nume")

