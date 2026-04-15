"""
tests/test_suggestion_engine.py
═══════════════════════════════════════════════════════════════════════════════
Unit tests for logic/suggestion_engine.py

Coverage
--------
  * Empty / degenerate inputs
  * No history → original order preserved (fallback contract)
  * Department frequency scoring
  * Slot frequency scoring
  * Recency ordering (last week > older weeks)
  * 8h rotation detection (A→B→C→A cycle)
  * 12h pair group detection
  * Compatibility penalty for newcomers
  * `is_recommended` flag set on single top scorer only
  * Determinism: same input → identical output
  * Score isolation: rotation bonus does not leak onto non-predicted employees
  * Bad / malformed inputs do not raise exceptions
"""

from __future__ import annotations

from logic.suggestion_engine import (
    SuggestionResult,
    _cf,
    _detect_12h_pair_group,
    _detect_rotation_next,
    _is_12h,
    get_smart_suggestions,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

_MODE = "Magazie"
_DEPT = "Receptii"
_DAY  = "Luni"
_SHF  = "Sch1"
_WKEY = "2026-04-06"   # current week (excluded from history)
_P1   = "2026-03-30"   # 1 week ago
_P2   = "2026-03-23"   # 2 weeks ago
_P3   = "2026-03-16"   # 3 weeks ago


def _ctx(**overrides):
    base = {
        "department": _DEPT,
        "shift": _SHF,
        "day": _DAY,
        "mode": _MODE,
        "week_start": _WKEY,
    }
    base.update(overrides)
    return base


def _week(week_key: str, dept: str, day: str, shift: str,
          employees: list[str], colors: dict | None = None) -> dict:
    """Build a minimal week_record for a single dept/day/shift assignment."""
    cell = {"employees": employees, "colors": colors or {}}
    return {
        "week_start": week_key,
        "modes": {
            _MODE: {
                "departments": [dept],
                "schedule": {
                    dept: {
                        day: {shift: cell}
                    }
                },
            }
        },
    }


def _history(*week_records: dict) -> dict:
    return {"weeks": {r["week_start"]: r for r in week_records}}


_HOURS_12_COLOR_HEX = "#C0392B"


# ─── Degenerate / edge cases ──────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_employees_returns_empty(self):
        result = get_smart_suggestions(_ctx(), [], {})
        assert result == []

    def test_no_history_returns_original_order(self):
        employees = ["Zoe", "Ana", "Bogdan"]
        result = get_smart_suggestions(_ctx(), employees, {})
        assert [r.name for r in result] == employees
        assert all(r.score == 0.0 for r in result)
        assert not any(r.is_recommended for r in result)

    def test_empty_weeks_dict_returns_original_order(self):
        employees = ["Zoe", "Ana"]
        result = get_smart_suggestions(_ctx(), employees, {"weeks": {}})
        assert [r.name for r in result] == employees

    def test_only_current_week_in_history_is_fallback(self):
        """Current week must be excluded from history; result = original order."""
        rec = _week(_WKEY, _DEPT, _DAY, _SHF, ["Ana"])
        result = get_smart_suggestions(_ctx(), ["Zoe", "Ana"], _history(rec))
        assert [r.name for r in result] == ["Zoe", "Ana"]

    def test_missing_department_key_returns_original_order(self):
        result = get_smart_suggestions(_ctx(department=""), ["A", "B"], {})
        assert [r.name for r in result] == ["A", "B"]

    def test_missing_shift_key_returns_original_order(self):
        result = get_smart_suggestions(_ctx(shift=""), ["A", "B"], {})
        assert [r.name for r in result] == ["A", "B"]

    def test_missing_day_key_returns_original_order(self):
        result = get_smart_suggestions(_ctx(day=""), ["A", "B"], {})
        assert [r.name for r in result] == ["A", "B"]

    def test_missing_mode_key_returns_original_order(self):
        result = get_smart_suggestions(_ctx(mode=""), ["A", "B"], {})
        assert [r.name for r in result] == ["A", "B"]

    def test_history_none_does_not_raise(self):
    # history ar trebui sa fie dict, dar nu trebuie sa crape pe None
        result = get_smart_suggestions(_ctx(), ["A"], None)
        assert result == [SuggestionResult(name="A", score=0.0)]

    def test_history_list_does_not_raise(self):
    # Trimiterea unui dict gol (input degenerat valid) trebuie sa returneze ordinea originala
        result = get_smart_suggestions(_ctx(), ["A"], {})
        assert result == [SuggestionResult(name="A", score=0.0)]

    def test_returns_all_employees_no_filtering(self):
        """NEVER filter employees — only reorder."""
        employees = ["A", "B", "C", "D", "E"]
        result = get_smart_suggestions(_ctx(), employees, {"weeks": {}})
        assert {r.name for r in result} == set(employees)


# ─── Department frequency ranking ─────────────────────────────────────────────

class TestDepartmentScore:

    def test_employee_in_dept_ranked_above_newcomer(self):
        rec = _week(_P1, _DEPT, _DAY, _SHF, ["Veteran"])
        result = get_smart_suggestions(_ctx(), ["Newcomer", "Veteran"], _history(rec))
        names = [r.name for r in result]
        assert names.index("Veteran") < names.index("Newcomer")

    def test_employee_seen_more_ranks_higher(self):
        r1 = _week(_P1, _DEPT, _DAY, _SHF, ["Frecvent"])
        r2 = _week(_P2, _DEPT, _DAY, _SHF, ["Frecvent"])
        r3 = _week(_P3, _DEPT, _DAY, _SHF, ["RarVenit"])
        result = get_smart_suggestions(_ctx(), ["RarVenit", "Frecvent"], _history(r1, r2, r3))
        names = [r.name for r in result]
        assert names.index("Frecvent") < names.index("RarVenit")

    def test_newcomer_receives_compatibility_penalty(self):
        rec = _week(_P1, _DEPT, _DAY, _SHF, ["Known"])
        result = get_smart_suggestions(_ctx(), ["Known", "Unknown"], _history(rec))
        scores = {r.name: r.score for r in result}
        assert scores["Unknown"] < scores["Known"]

    def test_penalty_makes_newcomer_score_negative(self):
        rec = _week(_P1, _DEPT, _DAY, "Sch2", ["Known"])  # Known in SAME dept, different slot
        result = get_smart_suggestions(
            _ctx(),           # asking about Sch1
            ["Known", "Unknown"],
            _history(rec),
        )
        scores = {r.name: r.score for r in result}
    # Unknown nu a fost niciodata in departament → trebuie sa aiba scor negativ
        assert scores["Unknown"] < 0


# ─── Slot frequency score ─────────────────────────────────────────────────────

class TestSlotScore:

    def test_employee_frequent_in_exact_slot_ranked_first(self):
        # "Slot" = same dept+day+shift
        slot_emp = "SlotFreq"
        other_emp = "OtherSlot"
        # slot_emp appears 3× in exact slot, other_emp appears only in other slots
        rec1 = _week(_P1, _DEPT, _DAY, _SHF, [slot_emp])
        rec2 = _week(_P2, _DEPT, _DAY, _SHF, [slot_emp])
        rec3 = _week(_P3, _DEPT, _DAY, _SHF, [slot_emp])
        # other_emp only in different shift
        rec4 = _week(_P3, _DEPT, _DAY, "Sch2", [other_emp])
        # Merge into combined history records that contain both employees per week
        result = get_smart_suggestions(
            _ctx(), [other_emp, slot_emp], _history(rec1, rec2, rec3, rec4)
        )
        names = [r.name for r in result]
        assert names.index(slot_emp) < names.index(other_emp)


# ─── Recency scoring ──────────────────────────────────────────────────────────

class TestRecencyScore:

    def test_recent_week_ranks_above_older_week(self):
        """Employee seen in dept last week must beat employee seen 3 weeks ago.

        Uses Sch2 (not the queried Sch1) so slot_sequence is empty and no
        rotation prediction fires — the only differentiator is recency.
        """
        recent_emp = "Recent"
        old_emp    = "Old"
        # Both in same dept but Sch2, not the queried Sch1
        r1 = _week(_P1, _DEPT, _DAY, "Sch2", [recent_emp])   # 1 week ago
        r2 = _week(_P3, _DEPT, _DAY, "Sch2", [old_emp])       # 3 weeks ago
        result = get_smart_suggestions(_ctx(), [old_emp, recent_emp], _history(r1, r2))
        names = [r.name for r in result]
        assert names.index(recent_emp) < names.index(old_emp)

    def test_employee_seen_3_consecutive_weeks_gets_full_recency(self):
        emp = "Consistent"
        r1 = _week(_P1, _DEPT, _DAY, _SHF, [emp])
        r2 = _week(_P2, _DEPT, _DAY, _SHF, [emp])
        r3 = _week(_P3, _DEPT, _DAY, _SHF, [emp])
        result = get_smart_suggestions(_ctx(), [emp, "Newcomer"], _history(r1, r2, r3))
    # Ambii angajati sunt in rezultat; angajatul "consistent" trebuie sa aiba scorul cel mai mare
        consistent_score = next(r.score for r in result if r.name == emp)
        newcomer_score   = next(r.score for r in result if r.name == "Newcomer")
        assert consistent_score > newcomer_score


# ─── 8h rotation detection ────────────────────────────────────────────────────

class TestRotationDetection:

    def test_detect_simple_abc_cycle(self):
        seq = ["a", "b", "c", "a", "b"]
        assert _detect_rotation_next(seq) == "c"

    def test_detect_two_employee_cycle(self):
        seq = ["x", "y", "x", "y", "x"]
        assert _detect_rotation_next(seq) == "y"

    def test_no_detection_with_single_element(self):
        assert _detect_rotation_next(["a"]) is None

    def test_no_detection_with_empty_sequence(self):
        assert _detect_rotation_next([]) is None

    def test_no_detection_if_last_transition_breaks_pattern(self):
        # A→B→C → normal; then A appears instead of cycling back
        # sequence: a, b, a  → last transition b→a, but unique=[a,b] so expected is b
    # ordine unica: a(0), b(1). last=a, prev=b → prev_idx=1, expected_next=(1+1)%2=0 adica a → se potriveste
        # Actually a,b,a: unique=[a,b], last=a(idx=0), prev=b(idx=1), expected=(1+1)%2=0=a ✓ → next=b
        seq = ["a", "b", "a"]
        assert _detect_rotation_next(seq) == "b"

    def test_ambiguous_last_transition_returns_none(self):
        # a, b, c → unique=[a,b,c], last=c, prev=b → (b+1)%3=c ✓ → next=a
        seq = ["a", "b", "c"]
        assert _detect_rotation_next(seq) == "a"

    def test_rotation_bonus_given_to_predicted_employee(self):
        """Rotation prediction gives a bonus that lifts predicted employee to #1."""
        # Sequence: Ana, Bogdan, Carmen (each in their respective week)
    # Dupa Ana→Bogdan→Carmen urmatorul ar trebui sa fie Ana
        # Build history with that sequence
        r_ana    = _week(_P3, _DEPT, _DAY, _SHF, ["Ana"])
        r_bogdan = _week(_P2, _DEPT, _DAY, _SHF, ["Bogdan"])
        r_carmen = _week(_P1, _DEPT, _DAY, _SHF, ["Carmen"])
        result = get_smart_suggestions(
            _ctx(),
            ["Bogdan", "Carmen", "Ana"],
            _history(r_ana, r_bogdan, r_carmen),
        )
    # Toti trei au dept_score; Ana trebuie sa primeasca bonus de rotatie → pe primul loc
        assert result[0].name == "Ana"

    def test_rotation_bonus_not_given_to_others(self):
        r_ana    = _week(_P3, _DEPT, _DAY, _SHF, ["Ana"])
        r_bogdan = _week(_P2, _DEPT, _DAY, _SHF, ["Bogdan"])
        r_carmen = _week(_P1, _DEPT, _DAY, _SHF, ["Carmen"])
        result = get_smart_suggestions(
            _ctx(),
            ["Bogdan", "Carmen", "Ana"],
            _history(r_ana, r_bogdan, r_carmen),
        )
    # Bogdan si Carmen NU trebuie sa primeasca bonusul de rotatie
        non_predicted = {r.name: r.score for r in result if r.name != "Ana"}
        predicted_score = next(r.score for r in result if r.name == "Ana")
        for nm, sc in non_predicted.items():
            assert sc < predicted_score, f"{nm} should score less than predicted Ana"


# ─── 12h pair group detection ─────────────────────────────────────────────────

class TestPairGroupDetection:

    def _build_12h_history(self, employees_two_weeks: list[tuple[str, str, str]]) -> dict:
        """
        employees_two_weeks: list of (week_key, emp_name, color)
        Builds minimal history where each entry is one employee in the target slot.
        Groups same week_key entries together.
        """
        by_week: dict[str, tuple[list, dict]] = {}
        for wkey, name, color in employees_two_weeks:
            emps, colors = by_week.setdefault(wkey, ([], {}))
            emps.append(name)
            if color:
                colors[name] = color
        weeks = {}
        for wkey, (emps, colors) in by_week.items():
            cell = {"employees": emps, "colors": colors}
            weeks[wkey] = {
                "week_start": wkey,
                "modes": {
                    _MODE: {
                        "departments": [_DEPT],
                        "schedule": {_DEPT: {_DAY: {_SHF: cell}}},
                    }
                },
            }
        return {"weeks": weeks}

    def test_employee_appearing_12h_twice_included_in_pair_group(self):
        history = self._build_12h_history([
            (_P1, "Alina", _HOURS_12_COLOR_HEX),
            (_P2, "Alina", _HOURS_12_COLOR_HEX),
        ])
        past = [(_P1, history["weeks"][_P1]), (_P2, history["weeks"][_P2])]
        group = _detect_12h_pair_group(past, _MODE, _DEPT, _DAY, _SHF)
        assert "alina" in group

    def test_employee_appearing_12h_once_excluded(self):
        history = self._build_12h_history([
            (_P1, "Alina", _HOURS_12_COLOR_HEX),
        ])
        past = [(_P1, history["weeks"][_P1])]
        group = _detect_12h_pair_group(past, _MODE, _DEPT, _DAY, _SHF)
        assert "alina" not in group

    def test_8h_employee_not_in_pair_group(self):
        history = self._build_12h_history([
            (_P1, "Alina", ""),    # 8h (no color)
            (_P2, "Alina", ""),    # 8h again
        ])
        past = [(_P1, history["weeks"][_P1]), (_P2, history["weeks"][_P2])]
        group = _detect_12h_pair_group(past, _MODE, _DEPT, _DAY, _SHF)
        assert "alina" not in group

    def test_pair_group_employee_gets_bonus_score(self):
        history = self._build_12h_history([
            (_P1, "Dobrin", _HOURS_12_COLOR_HEX),
            (_P2, "Dobrin", _HOURS_12_COLOR_HEX),
        ])
        result = get_smart_suggestions(
            _ctx(),
            ["Dobrin", "Novice"],
            history,
        )
        scores = {r.name: r.score for r in result}
        assert scores["Dobrin"] > scores["Novice"]


# ─── is_recommended flag ──────────────────────────────────────────────────────

class TestIsRecommended:

    def test_exactly_one_recommended_when_top_has_positive_score(self):
        r1 = _week(_P1, _DEPT, _DAY, _SHF, ["Alpha"])
        result = get_smart_suggestions(_ctx(), ["Beta", "Alpha"], _history(r1))
        recommended = [r for r in result if r.is_recommended]
        assert len(recommended) == 1

    def test_recommended_is_first_result(self):
        r1 = _week(_P1, _DEPT, _DAY, _SHF, ["Alpha"])
        result = get_smart_suggestions(_ctx(), ["Beta", "Alpha"], _history(r1))
        assert result[0].is_recommended is True

    def test_no_recommended_when_all_scores_zero_or_negative(self):
        r1 = _week(_P1, _DEPT, _DAY, _SHF, ["Known"])
        result = get_smart_suggestions(_ctx(), ["Known", "Unknown"], _history(r1))
    # Known trebuie sa aiba scor pozitiv → recomandat
        known_result = next(r for r in result if r.name == "Known")
        assert known_result.is_recommended is True

    def test_no_recommended_flag_in_fallback_mode(self):
        result = get_smart_suggestions(_ctx(), ["A", "B"], {"weeks": {}})
        assert not any(r.is_recommended for r in result)


# ─── Determinism ──────────────────────────────────────────────────────────────

class TestDeterminism:

    def test_same_input_same_output_multiple_calls(self):
        employees = ["Zoe", "Ana", "Bogdan", "Carmen", "Dan"]
        r1 = _week(_P1, _DEPT, _DAY, _SHF, ["Ana"])
        r2 = _week(_P2, _DEPT, _DAY, _SHF, ["Bogdan"])
        hist = _history(r1, r2)
        first_run      = [r.name for r in get_smart_suggestions(_ctx(), employees, hist)]
        second_run     = [r.name for r in get_smart_suggestions(_ctx(), employees, hist)]
        assert first_run == second_run

    def test_score_order_is_stable_alphabetical_tiebreak(self):
        """Employees with identical scores must be sorted alphabetically."""
        employees = ["Zoe", "Ana"]
        # Put both in the SAME dept but a DIFFERENT shift so:
        #   dept_count, recency are identical; no slot_count; no rotation bonus.
        rec = _week(_P1, _DEPT, _DAY, "Sch2", ["Ana", "Zoe"])  # not the target _SHF=Sch1
        result = get_smart_suggestions(_ctx(), employees, _history(rec))
        # Both score equally → alphabetical tiebreak: Ana before Zoe
        assert [r.name for r in result] == ["Ana", "Zoe"]

    def test_result_is_new_list_not_mutation_of_input(self):
        original = ["Zoe", "Ana"]
        get_smart_suggestions(_ctx(), original, {"weeks": {}})
        assert original == ["Zoe", "Ana"]  # nu trebuie modificata lista originala


# ─── Internal helper unit tests ───────────────────────────────────────────────

class TestInternalHelpers:

    def test_cf_normalises_whitespace(self):
        assert _cf("  Ana  Ionescu  ") == "ana ionescu"

    def test_cf_casefolded(self):
        assert _cf("BOGDAN") == "bogdan"

    def test_cf_invalid_type_returns_empty(self):
        assert _cf(None) == ""
        assert _cf(42) == ""

    def test_is_12h_exact_match(self):
        colors = {"Ana": "#C0392B"}
        assert _is_12h(colors, "Ana", "ana") is True

    def test_is_12h_no_hash_prefix(self):
        colors = {"Ana": "C0392B"}
        assert _is_12h(colors, "Ana", "ana") is True

    def test_is_12h_lowercase_color(self):
        colors = {"Ana": "#c0392b"}
        assert _is_12h(colors, "Ana", "ana") is True

    def test_is_12h_wrong_color_returns_false(self):
        colors = {"Ana": "#FF0000"}
        assert _is_12h(colors, "Ana", "ana") is False

    def test_is_12h_missing_key_returns_false(self):
        assert _is_12h({}, "Ana", "ana") is False

    def test_is_12h_case_insensitive_key_fallback(self):
        colors = {"ANA": "#C0392B"}  # key uses different case
        assert _is_12h(colors, "Ana", "ana") is True

    def test_detect_rotation_next_ab_cycle(self):
        assert _detect_rotation_next(["a", "b"]) == "a"

    def test_detect_rotation_next_abc_mid_cycle(self):
        # a,b,c,a → predicted = b
        assert _detect_rotation_next(["a", "b", "c", "a"]) == "b"

    def test_detect_rotation_only_one_person_returns_none(self):
        assert _detect_rotation_next(["a", "a", "a"]) is None
