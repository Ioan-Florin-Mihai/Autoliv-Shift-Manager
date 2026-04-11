"""
logic/suggestion_engine.py
═══════════════════════════════════════════════════════════════════════════════
Smart suggestion ranking engine for Autoliv Shift Manager.

Public API
----------
    get_smart_suggestions(context, employees, history) -> list[SuggestionResult]

Scoring components (highest-to-lowest weight)
----------------------------------------------
    department_score  – frequency of employee in THIS department (history)
    rotation_score    – 8h A→B→C rotation: predicted next gets top bonus
    recency_score     – appearances in the last 1–3 weeks
    slot_score        – frequency in exact dept+day+shift combo
    pair_score        – 12h pair member detected in this slot
    compat_penalty    – employee never appeared in this department

Contract
--------
    ✔ Pure function: no side effects, no I/O, no randomness
    ✔ Deterministic: same inputs → same output
    ✔ O(n·W·D·S) time — n=employees, W=weeks, D=days, S=shifts
    ✔ Zero regression: invalid/missing data falls back to original order
    ✔ No auto-assignment, no filtering, no hiding
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from logic.constants import HOURS_12_COLOR as _HOURS_12_COLOR

# ─── Constants ────────────────────────────────────────────────────────────────

# Score weights — adjust here without touching the algorithm
_W_DEPT: float = 40.0    # frequency in this department
_W_SLOT: float = 15.0    # frequency in exact dept+day+shift
_W_RECENCY: float = 25.0  # recency over last 3 weeks
_W_ROTATION: float = 30.0  # correct next step in 8h rotation cycle
_W_PAIR: float = 20.0    # detected 12h pair member for this slot
_W_PENALTY: float = -20.0  # never worked in this department

# Minimum weekly occurrences for a 12h pair to be considered stable
_PAIR_MIN_APPEARANCES: int = 2


# ─── Public types ─────────────────────────────────────────────────────────────

@dataclass
class SuggestionResult:
    """Scored suggestion for one employee.

    Attributes
    ----------
    name            : original employee name string (unchanged)
    score           : computed ranking score (higher = better match)
    is_recommended  : True only on the single top-scoring employee when score > 0
    """
    name: str
    score: float
    is_recommended: bool = False


# ─── Public API ───────────────────────────────────────────────────────────────

def get_smart_suggestions(
    context: dict,
    employees: list[str],
    history: dict | None,
) -> list[SuggestionResult]:
    """Rank employees for a schedule slot using historical assignment data.

    Parameters
    ----------
    context : dict
        Must contain:
            department  (str) – department being edited
            shift       (str) – Sch1 / Sch2 / Sch3
            day         (str) – Romanian day name (Luni … Duminica)
            mode        (str) – Magazie or Bucle
            week_start  (str) – ISO date of the week currently being edited
                                (excluded from history to avoid self-reference)

    employees : list[str]
        Employee names to rank (already filtered by the search query from
        EmployeeStore.search). The original list is NEVER modified.

    history : dict
        Full ScheduleStore.data: ``{"weeks": {iso_date_key: week_record}}``.
        Read-only; never written to.

    Returns
    -------
    list[SuggestionResult]
        Same employees, re-ranked by score DESC. Alphabetical tiebreak.
        ``is_recommended=True`` on the single highest scorer (score > 0).
        Falls back to original order with score=0 on any error or empty history.
    """
    if not employees:
        return []

    # ── 1. Parse and validate context ────────────────────────────────────────
    try:
        department = str(context.get("department") or "").strip()
        shift      = str(context.get("shift")      or "").strip()
        day        = str(context.get("day")        or "").strip()
        mode       = str(context.get("mode")       or "").strip()
        cur_week   = str(context.get("week_start") or "").strip()
    except Exception:
        return _unchanged(employees)

    if not (department and shift and day and mode):
        return _unchanged(employees)

    # ── 2. Build sorted list of past weeks (exclude current) ─────────────────
    try:
        raw_weeks = history.get("weeks", {}) if isinstance(history, dict) else {}
        past_weeks = _sorted_past_weeks(raw_weeks, cur_week)
    except Exception:
        return _unchanged(employees)

    if not past_weeks:
        return _unchanged(employees)

    # ── 3. Build weeks_ago lookup (distance from cur_week in whole weeks) ─────
    cur_date: date | None = None
    try:
        if cur_week:
            cur_date = date.fromisoformat(cur_week)
    except ValueError:
        pass

    weeks_ago_map: dict[str, int] = {}
    if cur_date:
        for wkey, _ in past_weeks:
            try:
                diff = (cur_date - date.fromisoformat(wkey)).days
                weeks_ago_map[wkey] = max(1, diff // 7)
            except ValueError:
                pass

    # ── 4. Collect per-employee stats from all past weeks ────────────────────
    #   past_weeks is sorted ASC (oldest→newest) so that:
    #     • slot_sequence is in chronological order for rotation detection

    dept_count: dict[str, int]                = {}
    slot_count: dict[str, int]                = {}
    # cf_name → set of week keys where employee appeared in this department
    dept_weeks: dict[str, set[str]]           = {}
    slot_sequence: list[str]                  = []   # cf_names in target slot, chronological

    for wkey, week_rec in past_weeks:
        schedule = _safe_schedule(week_rec, mode)
        dept_sched = schedule.get(department, {})
        if not isinstance(dept_sched, dict):
            continue

        seen_in_dept: set[str] = set()

        for d_name, day_sched in dept_sched.items():
            if not isinstance(day_sched, dict):
                continue
            for s_name, cell in day_sched.items():
                emps, colors = _safe_cell(cell)
                is_target_slot = (d_name == day and s_name == shift)

                for emp in emps:
                    cf = _cf(emp)
                    if not cf:
                        continue
                    dept_count[cf] = dept_count.get(cf, 0) + 1
                    seen_in_dept.add(cf)
                    if is_target_slot:
                        slot_count[cf] = slot_count.get(cf, 0) + 1

        # Record which weeks each employee appeared in this department
        for cf in seen_in_dept:
            dept_weeks.setdefault(cf, set()).add(wkey)

        # Slot sequence: 8h employees only, chronological
        t_emps, t_colors = _safe_cell_from(dept_sched, day, shift)
        for emp in t_emps:
            cf = _cf(emp)
            if cf and not _is_12h(t_colors, emp, cf):
                slot_sequence.append(cf)

    # ── 5. Derive rotation prediction and 12h pair group ─────────────────────
    rotation_next = _detect_rotation_next(slot_sequence)
    pair_group    = _detect_12h_pair_group(past_weeks, mode, department, day, shift)

    # ── 6. Score every employee ───────────────────────────────────────────────
    max_dept = max(dept_count.values(), default=1) or 1
    max_slot = max(slot_count.values(), default=1) or 1

    results: list[SuggestionResult] = []
    for emp in employees:
        cf = _cf(emp)
        d  = dept_count.get(cf, 0)
        sl = slot_count.get(cf, 0)

        dept_score = (d / max_dept) * _W_DEPT
        slot_score = (sl / max_slot) * _W_SLOT

        # Recency: weight each week by actual distance from current week
        # 1 week ago → +3, 2 weeks ago → +2, 3 weeks ago → +1, older → 0
        # Maximum possible = 3+2+1 = 6 (appeared every one of the last 3 weeks)
        recency_raw = 0
        for wk in (dept_weeks.get(cf) or set()):
            wa = weeks_ago_map.get(wk, 99)
            if wa == 1:
                recency_raw += 3
            elif wa == 2:
                recency_raw += 2
            elif wa == 3:
                recency_raw += 1
        rec_score = (recency_raw / 6.0) * _W_RECENCY if recency_raw else 0.0

        rot_score  = _W_ROTATION if rotation_next and cf == rotation_next else 0.0
        pair_score = _W_PAIR if cf in pair_group else 0.0
        penalty    = _W_PENALTY if d == 0 else 0.0

        total = dept_score + slot_score + rec_score + rot_score + pair_score + penalty
        results.append(SuggestionResult(name=emp, score=total))

    # Sort DESC by score, then ASC by name for deterministic tiebreak
    results.sort(key=lambda r: (-r.score, r.name.casefold()))

    # Mark the single top recommendation (only if positively scored)
    if results and results[0].score > 0:
        results[0].is_recommended = True

    return results


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _unchanged(employees: list[str]) -> list[SuggestionResult]:
    """Return employees in their original order with score=0 (safe fallback)."""
    return [SuggestionResult(name=e, score=0.0) for e in employees]


def _cf(name: Any) -> str:
    """Normalise and casefold a name; empty string signals invalid input."""
    if not isinstance(name, str):
        return ""
    return " ".join(name.split()).strip().casefold()


def _is_12h(colors: dict, name: str, cf_name: str) -> bool:
    """Return True if *name* is marked with the 12h color in *colors*."""
    raw = colors.get(name, "")
    if raw and str(raw).strip().upper().lstrip("#") == _HOURS_12_COLOR:
        return True
    # Case-insensitive fallback for lousy data
    for k, v in colors.items():
        if isinstance(k, str) and k.casefold() == cf_name:
            return bool(v and str(v).strip().upper().lstrip("#") == _HOURS_12_COLOR)
    return False


def _sorted_past_weeks(raw_weeks: Any, exclude_key: str) -> list[tuple[str, dict]]:
    """Return (wkey, record) pairs sorted ASC, skipping the current week."""
    if not isinstance(raw_weeks, dict):
        return []
    items: list[tuple[str, dict]] = []
    for key, rec in raw_weeks.items():
        if not isinstance(key, str) or not isinstance(rec, dict):
            continue
        if key == exclude_key:
            continue
        try:
            date.fromisoformat(key)
        except ValueError:
            continue
        items.append((key, rec))
    items.sort(key=lambda x: x[0])
    return items


def _safe_schedule(week_rec: dict, mode: str) -> dict:
    """Safe extraction of schedule dict for *mode* from a week record."""
    try:
        sched = week_rec["modes"][mode]["schedule"]
        return sched if isinstance(sched, dict) else {}
    except (KeyError, TypeError):
        return {}


def _safe_cell(cell: Any) -> tuple[list, dict]:
    """Return (employees_list, colors_dict) tolerating None / wrong types."""
    if not isinstance(cell, dict):
        return [], {}
    emps   = cell.get("employees", [])
    colors = cell.get("colors", {})
    return (
        emps   if isinstance(emps,   list) else [],
        colors if isinstance(colors, dict) else {},
    )


def _safe_cell_from(dept_sched: dict, day: str, shift: str) -> tuple[list, dict]:
    """Extract cell from dept_sched[day][shift] safely."""
    try:
        day_sched = dept_sched.get(day, {})
        if not isinstance(day_sched, dict):
            return [], {}
        return _safe_cell(day_sched.get(shift))
    except Exception:
        return [], {}


def _detect_rotation_next(sequence: list[str]) -> str | None:
    """Predict the next employee in an A→B→C→A rotation cycle.

    Algorithm
    ---------
    1. Derive ``unique`` – ordered first occurrences from *sequence*.
    2. Require |unique| ≥ 2.
    3. Validate that the last observed transition (seq[-2]→seq[-1]) matches
       the cycle; return ``None`` if it does not (ambiguous data).
    4. Return the next employee after seq[-1] in the cycle.

    Returns ``None`` if the pattern cannot be confirmed (< 2 elements,
    single unique employee, or last transition is inconsistent).
    """
    if len(sequence) < 2:
        return None

    unique: list[str] = list(dict.fromkeys(sequence))
    if len(unique) < 2:
        return None  # only one employee ever assigned here

    last = sequence[-1]
    prev = sequence[-2]

    if last not in unique or prev not in unique:
        return None

    cycle_len = len(unique)
    last_idx  = unique.index(last)
    prev_idx  = unique.index(prev)

    # The observed transition must match the detected cycle order
    if (prev_idx + 1) % cycle_len != last_idx:
        return None  # pattern mismatch – don't predict

    next_idx = (last_idx + 1) % cycle_len
    return unique[next_idx]


def _detect_12h_pair_group(
    past_weeks: list[tuple[str, dict]],
    mode: str,
    department: str,
    day: str,
    shift: str,
    min_count: int = _PAIR_MIN_APPEARANCES,
) -> frozenset[str]:
    """Return casefolded names of employees who regularly work 12h in dept+day+shift.

    An employee qualifies when they appeared as a 12h worker in exactly
    *this* slot at least *min_count* times in the provided history window.
    """
    counts: dict[str, int] = {}
    for _wkey, week_rec in past_weeks:
        schedule  = _safe_schedule(week_rec, mode)
        dept_s    = schedule.get(department, {})
        if not isinstance(dept_s, dict):
            continue
        emps, colors = _safe_cell_from(dept_s, day, shift)
        for emp in emps:
            cf = _cf(emp)
            if cf and _is_12h(colors, emp, cf):
                counts[cf] = counts.get(cf, 0) + 1

    return frozenset(cf for cf, cnt in counts.items() if cnt >= min_count)
