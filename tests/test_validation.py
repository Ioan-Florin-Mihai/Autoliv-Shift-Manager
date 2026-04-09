"""
Tests pentru logic/validation.py
Acopera: _parse_hours() si validate_employee_data()
"""

import pytest

from logic.validation import _parse_hours, validate_employee_data

# ── _parse_hours ─────────────────────────────────────────────────────────────

class TestParseHours:
    def test_valid_integer(self):
        assert _parse_hours("Ore", "8") == 8

    def test_valid_float(self):
        assert _parse_hours("Ore", "7.5") == 7.5

    def test_valid_max_boundary(self):
        assert _parse_hours("Ore", "12") == 12

    def test_empty_not_allowed_raises(self):
        with pytest.raises(ValueError, match="obligatoriu"):
            _parse_hours("Ore", "")

    def test_empty_allowed_returns_none(self):
        assert _parse_hours("Ore", "", allow_empty=True) is None

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="mai mare"):
            _parse_hours("Ore", "0")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="mai mare"):
            _parse_hours("Ore", "-1")

    def test_over_12_raises(self):
        with pytest.raises(ValueError, match="nu poate depasi"):
            _parse_hours("Ore", "13")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="numar"):
            _parse_hours("Ore", "abc")

    def test_whitespace_stripped(self):
        assert _parse_hours("Ore", "  8  ") == 8

    def test_integer_float_returned_as_int(self):
        result = _parse_hours("Ore", "8.0")
        assert result == 8
        assert isinstance(result, int)


# ── validate_employee_data ───────────────────────────────────────────────────

class TestValidateEmployeeData:
    def test_valid_single_assignment(self):
        result = validate_employee_data("Popescu", "Ion", "Dep A", "8")
        assert result["nume"]    == "Popescu"
        assert result["prenume"] == "Ion"
        assert result["repartizari"][0]["departament"] == "Dep A"
        assert result["repartizari"][0]["ore"] == 8
        assert len(result["repartizari"]) == 1

    def test_valid_double_assignment(self):
        result = validate_employee_data("Ionescu", "Maria", "Dep A", "4", "Dep B", "4")
        assert result["repartizari"][0]["ore"] == 4
        assert result["repartizari"][1]["ore"] == 4
        assert result["split_activ"] is True

    def test_missing_name_raises(self):
        with pytest.raises(ValueError):
            validate_employee_data("", "Ion", "Dep A", "8")

    def test_missing_department_raises(self):
        with pytest.raises(ValueError):
            validate_employee_data("Popescu", "Ion", "", "8")

    def test_second_dept_without_hours_raises(self):
        """Departamentul 2 completat fara ore 2 trebuie sa arunce eroare."""
        with pytest.raises(ValueError):
            validate_employee_data("Popescu", "Ion", "Dep A", "8", "Dep B", "")

    def test_total_hours_not_over_12(self):
        """8 + 8 = 16 > 12 trebuie respins."""
        with pytest.raises(ValueError, match="12"):
            validate_employee_data("Popescu", "Ion", "Dep A", "8", "Dep B", "8")

    def test_whitespace_stripped_from_strings(self):
        result = validate_employee_data("  Vasile ", "  Gheorghe  ", "  Dep C  ", "8")
        assert result["nume"]    == "Vasile"
        assert result["prenume"] == "Gheorghe"
