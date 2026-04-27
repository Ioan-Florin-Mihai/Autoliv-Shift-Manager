import json

import pytest

import logic.employee_store as emp_module
from logic.employee_store import EmployeeStore


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    fake_path = tmp_path / "employees.json"
    monkeypatch.setattr(emp_module, "EMPLOYEES_PATH", fake_path)
    monkeypatch.setattr(EmployeeStore, "_collect_schedule_names", lambda self, seen: [])


@pytest.fixture()
def populated_store(tmp_path, monkeypatch):
    emp_path = tmp_path / "employees.json"
    emp_path.write_text(
        json.dumps(
            {
                "employees": [
                    {"nume": "Andrei", "prenume": "Pop", "departament": "Livrari"},
                    {"nume": "Maria", "prenume": "Ion", "departament": "Receptii"},
                    "Vasile Dan",
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(emp_module, "EMPLOYEES_PATH", emp_path)
    monkeypatch.setattr(EmployeeStore, "_collect_schedule_names", lambda self, seen: [])
    return EmployeeStore()


class TestNormalizeEmployeeRecords:
    def test_removes_duplicates_case_insensitive(self, populated_store):
        result, seen = populated_store._normalize_employee_records(
            [
                {"nume": "Ana", "prenume": "Pop", "departament": "Livrari"},
                {"nume": "ana", "prenume": "pop", "departament": "Receptii"},
                "ANA POP",
            ]
        )
        assert len(result) == 1
        assert len(seen) == 1

    def test_strips_extra_spaces(self, populated_store):
        result, _ = populated_store._normalize_employee_records(["  Vasile   Dan  "])
        assert result[0]["full_name"] == "Vasile Dan"

    def test_old_string_record_gets_empty_department(self, populated_store):
        result, _ = populated_store._normalize_employee_records(["Vasile Dan"])
        assert result[0]["departament"] is None


class TestReadCompatibility:
    def test_get_all_returns_full_names(self, populated_store):
        assert populated_store.get_all() == ["Andrei Pop", "Maria Ion", "Vasile Dan"]

    def test_get_profiles_returns_department_for_new_records(self, populated_store):
        profiles = populated_store.get_profiles()
        maria = next(item for item in profiles if item["full_name"] == "Maria Ion")
        assert maria["departament"] == "Receptii"

    def test_old_data_without_department_still_loads(self, populated_store):
        profiles = populated_store.get_profiles()
        vasile = next(item for item in profiles if item["full_name"] == "Vasile Dan")
        assert vasile["departament"] is None


class TestSearch:
    def test_empty_query_returns_all(self, populated_store):
        results = populated_store.search("")
        assert len(results) == 3

    def test_partial_match_case_insensitive(self, populated_store):
        assert populated_store.search("andrei") == ["Andrei Pop"]

    def test_no_match_returns_empty(self, populated_store):
        assert populated_store.search("xxxxxxxxx") == []


class TestAddAndUpdateProfiles:
    def test_add_new_employee_string_path(self, populated_store):
        populated_store.add_employee("Ionescu Radu")
        assert "Ionescu Radu" in populated_store.get_all()

    def test_duplicate_not_added_case_insensitive(self, populated_store):
        count_before = len(populated_store.get_all())
        populated_store.add_employee("andrei pop")
        assert len(populated_store.get_all()) == count_before

    def test_empty_string_raises(self, populated_store):
        with pytest.raises(ValueError):
            populated_store.add_employee("   ")

    def test_upsert_profile_saves_department(self, populated_store):
        full_name, created = populated_store.upsert_profile("Boatca", "D", "Sef schimb")
        assert full_name == "Boatca D"
        assert created is True
        assert populated_store.get_department_map()["Boatca D"] == "Sef schimb"

    def test_upsert_profile_updates_department_without_duplicate(self, populated_store):
        full_name, created = populated_store.upsert_profile("Andrei", "Pop", "Sef schimb")
        assert full_name == "Andrei Pop"
        assert created is False
        assert populated_store.get_all().count("Andrei Pop") == 1
        assert populated_store.get_department_map()["Andrei Pop"] == "Sef schimb"

    def test_duplicate_detection_is_case_insensitive_on_update(self, populated_store):
        full_name, created = populated_store.upsert_profile("andrei", "pop", "Sef schimb")
        assert full_name == "andrei pop"
        assert created is False
        assert len([name for name in populated_store.get_all() if name.casefold() == "andrei pop"]) == 1

    def test_save_writes_structured_records(self, populated_store):
        populated_store.upsert_profile("Boatca", "D", "Sef schimb")
        payload = json.loads(emp_module.EMPLOYEES_PATH.read_text(encoding="utf-8"))
        assert isinstance(payload["employees"][0], dict)
        assert {"nume", "prenume", "departament"} <= set(payload["employees"][0])


class TestDeleteAndRename:
    def test_delete_existing(self, populated_store):
        assert populated_store.delete_employee("Maria Ion") is True
        assert "Maria Ion" not in populated_store.get_all()

    def test_delete_case_insensitive(self, populated_store):
        populated_store.delete_employee("maria ion")
        assert "Maria Ion" not in populated_store.get_all()

    def test_delete_nonexistent_returns_false(self, populated_store):
        assert populated_store.delete_employee("Nimeni Altcineva") is False

    def test_rename_updates_name(self, populated_store):
        populated_store.rename_employee("Andrei Pop", "Andrei Popescu")
        assert "Andrei Popescu" in populated_store.get_all()
        assert "Andrei Pop" not in populated_store.get_all()

    def test_rename_to_existing_raises(self, populated_store):
        with pytest.raises(ValueError):
            populated_store.rename_employee("Andrei Pop", "Maria Ion")
