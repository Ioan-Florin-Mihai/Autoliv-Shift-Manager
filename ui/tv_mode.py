"""
ui/tv_mode.py
─────────────────────────────────────────────────────────────
TV MODE — Autoliv Shift Manager
Display read-only, full-screen, auto-refresh every 5 seconds.

Always shows FUTURE planning:
  • Normal (Mon–Thu):  next-week Mon–Fri
  • Weekend planned:   current-week Sat–Sun + next-week Mon–Fri
  • Weekend / next cycle: resets automatically when data changes

Usage:
  python main.py --tv
  Autoliv_Shift_Manager.exe --tv

Keyboard shortcuts:
  ESC / Q   — exit
  ← / →     — switch mode (Magazie ↔ Bucle)
  R         — force refresh now
"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta

import customtkinter as ctk

from logic.app_logger import log_exception
from logic.schedule_store import (
    ABSENCE_TYPE_NAMES,
    DAYS,
    SHIFTS,
    TEMPLATES,
    WEEKEND_DAYS,
    ScheduleStore,
)
from ui.common_ui import apply_window_icon

# ─── Colour palette (Autoliv brand, high visibility) ─────────────────────────
_BG          = "#EEF3FB"
_TOPBAR_BG   = "#0A4D9B"
_TOPBAR_FG   = "#FFFFFF"
_TOPBAR_WEEK = "#B8D4F4"
_TOPBAR_MODE = "#FFD700"
_COL_HDR_BG  = "#1A5EC4"
_COL_HDR_FG  = "#FFFFFF"
_WKND_HDR_BG = "#3D5A80"    # weekend column header — slightly darker
_WKND_HDR_FG = "#D0E8FF"
_DEPT_BG     = "#1F6CC4"
_DEPT_FG     = "#FFFFFF"
_SHIFT_BG_A  = "#F4F8FF"
_SHIFT_BG_B  = "#E9F1FF"
_WKND_BG_A   = "#EEF2FA"    # weekend data cell (even rows)
_WKND_BG_B   = "#E4ECF7"    # weekend data cell (odd rows)
_SHIFT_FG    = "#1A2D4A"
_SEP_COLOR   = "#C0D0E8"
_MUTED       = "#9AAABF"
_BOTTOM_BG   = "#0A4D9B"
_BOTTOM_FG   = "#8DB6E0"

# ─── Layout constants ─────────────────────────────────────────────────────────
DEPT_W    = 200
SHIFT_W   = 86
SHIFT_H   = 62
COL_HDR_H = 60
TOP_H     = 72
BOTTOM_H  = 36

# ─── Timing ───────────────────────────────────────────────────────────────────
REFRESH_MS = 5_000
CLOCK_MS   = 1_000

SHIFT_LABELS = {"Sch1": "Sch. 1", "Sch2": "Sch. 2", "Sch3": "Sch. 3"}
MODE_NAMES   = list(TEMPLATES.keys())   # ["Magazie", "Bucle"]

# Day name → offset within its week (Luni=0 … Duminica=6)
_DAY_OFFSETS: dict[str, int] = {name: offset for name, offset in DAYS}


# ─── Pure helpers (no UI dependency) ─────────────────────────────────────────

def _has_weekend_data(week_record: dict) -> bool:
    """Return True iff the week has at least one active employee on Sat or Sun.

    Checks all modes and departments so the result is mode-independent.
    "Active" means the employee name is not an absence code (CO / CM / ABSENT).
    """
    for mode_rec in week_record.get("modes", {}).values():
        for dept_sched in mode_rec.get("schedule", {}).values():
            for day_name in ("Sambata", "Duminica"):
                for shift in SHIFTS:
                    cell = dept_sched.get(day_name, {}).get(shift, {})
                    active = [
                        e for e in cell.get("employees", [])
                        if e.strip().upper() not in ABSENCE_TYPE_NAMES
                    ]
                    if active:
                        return True
    return False


def _active_employees(employees: list) -> list:
    """Return only employees that are actively working (no CO / CM / ABSENT)."""
    return [e for e in employees if e.strip().upper() not in ABSENCE_TYPE_NAMES]


# ─── Main window ──────────────────────────────────────────────────────────────

class TVModeWindow(ctk.CTk):
    """Full-screen read-only schedule display for factory TVs.

    Automatically determines what to show:
      • No weekend data  → display_days = Mon–Fri  (from next week)
      • Weekend planned  → display_days = Sat–Sun (current) + Mon–Fri (next)
    """

    def __init__(self):
        super().__init__()
        self.title("Autoliv Shift Manager — TV Mode")
        self.configure(fg_color=_BG)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        apply_window_icon(self)

        self._mode_idx: int = 0
        self._store: ScheduleStore | None = None
        self._current_week: dict | None = None
        self._next_week: dict | None = None
        self._display_days: list[str] = []
        self._data_map: dict[str, dict] = {}
        self._refresh_job: str | None = None
        self._clock_job: str | None = None

        self.attributes("-fullscreen", True)
        self._bind_keys()
        self._build_skeleton()
        self._load_data()
        self._render_grid()
        self._start_clock()
        self._schedule_refresh()

    # ── Key bindings ──────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<q>",      lambda _e: self.destroy())
        self.bind("<Q>",      lambda _e: self.destroy())
        self.bind("<Left>",   lambda _e: self._cycle_mode(-1))
        self.bind("<Right>",  lambda _e: self._cycle_mode(+1))
        self.bind("<r>",      lambda _e: self._force_refresh())
        self.bind("<R>",      lambda _e: self._force_refresh())

    # ── Skeleton (chrome that never changes) ──────────────────────────────────

    def _build_skeleton(self):
        # ── Top bar ───────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=_TOPBAR_BG, height=TOP_H)
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        inner = tk.Frame(top, bg=_TOPBAR_BG)
        inner.pack(fill="both", expand=True, padx=28, pady=8)

        tk.Label(
            inner, text="AUTOLIV — SHIFT MANAGER",
            bg=_TOPBAR_BG, fg=_TOPBAR_FG,
            font=("Arial", 21, "bold"), anchor="w",
        ).pack(side="left")

        self._mode_lbl = tk.Label(
            inner, text="",
            bg=_TOPBAR_BG, fg=_TOPBAR_MODE,
            font=("Arial", 24, "bold"), anchor="center",
        )
        self._mode_lbl.pack(side="left", padx=(36, 0))

        self._week_lbl = tk.Label(
            inner, text="",
            bg=_TOPBAR_BG, fg=_TOPBAR_WEEK,
            font=("Arial", 17), anchor="center",
        )
        self._week_lbl.pack(side="left", padx=(36, 0))

        self._clock_lbl = tk.Label(
            inner, text="",
            bg=_TOPBAR_BG, fg=_TOPBAR_FG,
            font=("Arial", 20, "bold"), anchor="e",
        )
        self._clock_lbl.pack(side="right")

        # ── Scrollable data area ──────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=_BG,
            scrollbar_button_color="#5A8EC0",
            scrollbar_button_hover_color="#7AAEE6",
        )
        self._scroll.pack(side="top", fill="both", expand=True, padx=10, pady=(6, 4))

        # ── Bottom bar ────────────────────────────────────────────────────────
        bottom = tk.Frame(self, bg=_BOTTOM_BG, height=BOTTOM_H)
        bottom.pack(side="top", fill="x")
        bottom.pack_propagate(False)
        tk.Label(
            bottom,
            text="ESC / Q = Ieșire     ←  → = Schimbă modul     R = Reîncărcare manuală",
            bg=_BOTTOM_BG, fg=_BOTTOM_FG,
            font=("Arial", 11),
        ).pack(expand=True)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_data(self):
        """Load current + next week from disk, then build display_days / data_map.

        A fresh ScheduleStore is created on every call so there is no in-memory
        caching — all TV instances always read the same file state.
        """
        try:
            self._store = ScheduleStore()
            today = date.today()
            current = self._store.get_or_create_week(today)
            nxt     = self._store.get_or_create_week(today + timedelta(days=7))
            self._current_week = current
            self._next_week    = nxt

            if _has_weekend_data(current):
                self._display_days = [
                    "Sambata", "Duminica",
                    "Luni", "Marti", "Miercuri", "Joi", "Vineri",
                ]
                self._data_map = {
                    "Sambata":  current,
                    "Duminica": current,
                    "Luni":     nxt,
                    "Marti":    nxt,
                    "Miercuri": nxt,
                    "Joi":      nxt,
                    "Vineri":   nxt,
                }
            else:
                self._display_days = ["Luni", "Marti", "Miercuri", "Joi", "Vineri"]
                self._data_map = {d: nxt for d in self._display_days}

        except Exception as exc:  # noqa: BLE001
            log_exception("tv_load_data", exc)
            self._current_week = None
            self._next_week    = None
            self._display_days = []
            self._data_map     = {}

    def _day_date(self, day_name: str) -> date:
        """Return the calendar date for a display day using its mapped week."""
        week_rec = self._data_map.get(day_name)
        if not week_rec:
            return date.today()
        week_start = date.fromisoformat(week_rec["week_start"])
        return week_start + timedelta(days=_DAY_OFFSETS[day_name])

    # ── Grid rendering ────────────────────────────────────────────────────────

    def _render_grid(self):
        """Clear and rebuild the data grid based on display_days + data_map."""
        for widget in self._scroll.winfo_children():
            widget.destroy()

        mode_name = MODE_NAMES[self._mode_idx]
        self._mode_lbl.configure(text=mode_name.upper())

        if self._next_week is None:
            tk.Label(
                self._scroll,
                text="Nu există date disponibile.",
                font=("Arial", 26, "bold"),
                bg=_BG, fg="#C0392B",
            ).pack(pady=80)
            self._week_lbl.configure(text="")
            return

        # ── Top bar label ─────────────────────────────────────────────────────
        next_label = self._next_week.get("week_label", "")
        has_wknd   = len(self._display_days) == 7
        self._week_lbl.configure(
            text=("Weekend + " + next_label) if has_wknd else next_label
        )

        # Department list comes from next week (primary planning target)
        departments = self._next_week["modes"].get(mode_name, {}).get("departments", [])

        # ── Column header row ─────────────────────────────────────────────────
        hdr_row = tk.Frame(self._scroll, bg=_COL_HDR_BG, height=COL_HDR_H)
        hdr_row.pack(fill="x", pady=(0, 3))
        hdr_row.pack_propagate(False)

        tk.Frame(hdr_row, bg=_COL_HDR_BG, width=DEPT_W).pack(side="left", fill="y")
        tk.Frame(hdr_row, bg=_COL_HDR_BG, width=SHIFT_W).pack(side="left", fill="y")

        for day_name in self._display_days:
            is_wknd  = day_name in WEEKEND_DAYS
            cell_bg  = _WKND_HDR_BG if is_wknd else _COL_HDR_BG
            cell_fg  = _WKND_HDR_FG if is_wknd else _COL_HDR_FG
            day_date = self._day_date(day_name)
            txt      = f"{day_name.upper()}\n{day_date.strftime('%d %b')}"
            cell = tk.Frame(hdr_row, bg=cell_bg)
            cell.pack(side="left", fill="both", expand=True)
            tk.Label(
                cell, text=txt,
                bg=cell_bg, fg=cell_fg,
                font=("Arial", 13, "bold"),
                justify="center", anchor="center",
            ).pack(expand=True, fill="both")

        # ── Department blocks ─────────────────────────────────────────────────
        for department in departments:
            dept_block = tk.Frame(self._scroll, bg=_BG)
            dept_block.pack(fill="x", pady=(0, 2))

            dept_left = tk.Frame(dept_block, bg=_DEPT_BG, width=DEPT_W)
            dept_left.pack(side="left", fill="y")
            dept_left.pack_propagate(False)
            tk.Label(
                dept_left, text=department,
                bg=_DEPT_BG, fg=_DEPT_FG,
                font=("Arial", 14, "bold"),
                justify="center", anchor="center",
                wraplength=DEPT_W - 12,
            ).pack(expand=True, fill="both")

            dept_right = tk.Frame(dept_block, bg=_BG)
            dept_right.pack(side="left", fill="both", expand=True)

            for shift_idx, shift in enumerate(SHIFTS):
                norm_bg  = _SHIFT_BG_A if shift_idx % 2 == 0 else _SHIFT_BG_B
                shift_row = tk.Frame(dept_right, bg=norm_bg, height=SHIFT_H)
                shift_row.pack(fill="x")
                shift_row.pack_propagate(False)

                # Shift label
                shift_cell = tk.Frame(shift_row, bg=norm_bg, width=SHIFT_W)
                shift_cell.pack(side="left", fill="y")
                shift_cell.pack_propagate(False)
                tk.Label(
                    shift_cell,
                    text=SHIFT_LABELS.get(shift, shift),
                    bg=norm_bg, fg=_SHIFT_FG,
                    font=("Arial", 13, "bold"),
                    anchor="center",
                ).pack(expand=True, fill="both")

                # One data cell per display day
                for day_name in self._display_days:
                    is_wknd  = day_name in WEEKEND_DAYS
                    wknd_bg  = _WKND_BG_A if shift_idx % 2 == 0 else _WKND_BG_B
                    cell_bg  = wknd_bg if is_wknd else norm_bg

                    week_rec  = self._data_map[day_name]
                    raw_cell  = (
                        week_rec["modes"]
                        .get(mode_name, {})
                        .get("schedule", {})
                        .get(department, {})
                        .get(day_name, {})
                        .get(shift, {})
                    )
                    all_emps = raw_cell.get("employees", []) if isinstance(raw_cell, dict) else []
                    employees = _active_employees(all_emps)

                    day_cell = tk.Frame(shift_row, bg=cell_bg, bd=1, relief="flat", padx=6, pady=3)
                    day_cell.pack(side="left", fill="both", expand=True)

                    if employees:
                        for emp in employees:
                            name    = " ".join(emp.split())
                            display = name if len(name) <= 20 else name[:17].rstrip() + "…"
                            tk.Label(
                                day_cell, text=display,
                                bg=cell_bg, fg=_SHIFT_FG,
                                font=("Arial", 12),
                                anchor="w", justify="left",
                            ).pack(anchor="w", fill="x")
                    else:
                        tk.Label(
                            day_cell, text="—",
                            bg=cell_bg, fg=_MUTED,
                            font=("Arial", 12),
                            anchor="center",
                        ).pack(expand=True, fill="both")

            tk.Frame(self._scroll, bg=_SEP_COLOR, height=2).pack(fill="x")

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _tick_clock(self):
        try:
            if not self.winfo_exists():
                return
            now = datetime.now().strftime("%H:%M:%S   %d/%m/%Y")
            self._clock_lbl.configure(text=now)
        except tk.TclError:
            return
        self._clock_job = self.after(CLOCK_MS, self._tick_clock)

    def _start_clock(self):
        self._tick_clock()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _force_refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        self._load_data()
        self._render_grid()
        self._schedule_refresh()

    def _schedule_refresh(self):
        if not self.winfo_exists():
            return
        self._refresh_job = self.after(REFRESH_MS, self._force_refresh)

    # ── Mode cycle ────────────────────────────────────────────────────────────

    def _cycle_mode(self, delta: int):
        self._mode_idx = (self._mode_idx + delta) % len(MODE_NAMES)
        self._render_grid()


# ─── Entry point ──────────────────────────────────────────────────────────────

def run_tv_mode() -> None:
    """Called from main.py when --tv flag is present."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    app = TVModeWindow()
    app.mainloop()
