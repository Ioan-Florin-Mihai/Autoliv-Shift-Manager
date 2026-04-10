"""
ui/tv_mode.py
─────────────────────────────────────────────────────────────
TV MODE — Autoliv Shift Manager
Display read-only, full-screen, auto-refresh every 5 seconds.

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
    DAYS,
    SHIFTS,
    TEMPLATES,
    WEEKEND_DAYS,
    ScheduleStore,
    get_week_start,
)
from ui.common_ui import apply_window_icon

# ─── Colour palette (Autoliv brand, high visibility) ─────────────────────────
_BG            = "#EEF3FB"    # page background
_TOPBAR_BG     = "#0A4D9B"    # Autoliv dark navy
_TOPBAR_FG     = "#FFFFFF"
_TOPBAR_WEEK   = "#B8D4F4"    # subdued blue for week label
_TOPBAR_MODE   = "#FFD700"    # gold for mode name
_COL_HDR_BG    = "#1A5EC4"    # column-header row
_COL_HDR_FG    = "#FFFFFF"
_TODAY_COL     = "#D4E8FF"    # today column tint
_TODAY_FG      = "#0A2A60"
_DEPT_BG       = "#1F6CC4"    # department name cell
_DEPT_FG       = "#FFFFFF"
_SHIFT_BG_A    = "#F4F8FF"    # alternating shift rows
_SHIFT_BG_B    = "#E9F1FF"
_SHIFT_FG      = "#1A2D4A"
_SEP_COLOR     = "#C0D0E8"    # row separator
_MUTED         = "#9AAABF"
_BOTTOM_BG     = "#0A4D9B"
_BOTTOM_FG     = "#8DB6E0"

# ─── Layout constants ─────────────────────────────────────────────────────────
DEPT_W      = 200    # department column width (px)
SHIFT_W     = 86     # shift label column width (px)
SHIFT_H     = 62     # each shift row height (px)
COL_HDR_H   = 60     # column-header row height (px)
TOP_H       = 72     # top bar height (px)
BOTTOM_H    = 36     # bottom bar height (px)

# ─── Timing ───────────────────────────────────────────────────────────────────
REFRESH_MS  = 5_000   # data refresh interval
CLOCK_MS    = 1_000   # clock tick interval

SHIFT_LABELS = {"Sch1": "Sch. 1", "Sch2": "Sch. 2", "Sch3": "Sch. 3"}
MODE_NAMES   = list(TEMPLATES.keys())   # ["Magazie", "Bucle"]


# ─── Main window ──────────────────────────────────────────────────────────────

class TVModeWindow(ctk.CTk):
    """Full-screen read-only schedule display for factory TVs."""

    def __init__(self):
        super().__init__()
        self.title("Autoliv Shift Manager — TV Mode")
        self.configure(fg_color=_BG)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        apply_window_icon(self)

        self._mode_idx: int = 0
        self._store: ScheduleStore | None = None
        self._week_record: dict | None = None
        self._refresh_job: str | None = None
        self._clock_job:   str | None = None

        self.attributes("-fullscreen", True)
        self._bind_keys()
        self._build_skeleton()
        self._load_data()
        self._render_grid()
        self._start_clock()
        self._schedule_refresh()

    # ── Key bindings ──────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.bind("<Escape>",  lambda _e: self.destroy())
        self.bind("<q>",       lambda _e: self.destroy())
        self.bind("<Q>",       lambda _e: self.destroy())
        self.bind("<Left>",    lambda _e: self._cycle_mode(-1))
        self.bind("<Right>",   lambda _e: self._cycle_mode(+1))
        self.bind("<r>",       lambda _e: self._force_refresh())
        self.bind("<R>",       lambda _e: self._force_refresh())

    # ── Skeleton (chrome that never changes) ──────────────────────────────────

    def _build_skeleton(self):
        """Build the non-data chrome: top bar, scroll area, bottom bar."""

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

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_data(self):
        try:
            self._store = ScheduleStore()
            today = date.today()
            self._week_record = self._store.get_or_create_week(today)
        except Exception as exc:  # noqa: BLE001
            log_exception("tv_load_data", exc)
            self._week_record = None

    # ── Grid rendering ────────────────────────────────────────────────────────

    def _render_grid(self):
        """Clear and rebuild the entire data grid."""
        for widget in self._scroll.winfo_children():
            widget.destroy()

        mode_name = MODE_NAMES[self._mode_idx]
        self._mode_lbl.configure(text=mode_name.upper())

        if self._week_record is None:
            tk.Label(
                self._scroll,
                text="Nu există date disponibile.",
                font=("Arial", 26, "bold"),
                bg=_BG, fg="#C0392B",
            ).pack(pady=80)
            return

        week_start = date.fromisoformat(self._week_record["week_start"])
        self._week_lbl.configure(text=self._week_record.get("week_label", ""))

        mode_record  = self._week_record["modes"].get(mode_name, {})
        departments  = mode_record.get("departments", [])
        schedule     = mode_record.get("schedule", {})

        # Which days to show (weekdays only)
        visible_days = [(name, offset) for name, offset in DAYS if name not in WEEKEND_DAYS]
        today_offset = (date.today() - week_start).days   # 0=Mon … 6=Sun; OOB if other week

        # ── Column header row ─────────────────────────────────────────────────
        hdr_row = tk.Frame(self._scroll, bg=_COL_HDR_BG, height=COL_HDR_H)
        hdr_row.pack(fill="x", pady=(0, 3))
        hdr_row.pack_propagate(False)

        # Dept placeholder
        tk.Frame(hdr_row, bg=_COL_HDR_BG, width=DEPT_W).pack(side="left", fill="y")
        # Shift placeholder
        tk.Frame(hdr_row, bg=_COL_HDR_BG, width=SHIFT_W).pack(side="left", fill="y")

        for day_name, day_offset in visible_days:
            is_today = (day_offset == today_offset)
            cell_bg  = _TODAY_COL if is_today else _COL_HDR_BG
            cell_fg  = _TODAY_FG  if is_today else _COL_HDR_FG
            day_date = week_start + timedelta(days=day_offset)
            txt      = f"{'★  ' if is_today else ''}{day_name.upper()}\n{day_date.strftime('%d %b')}"
            cell = tk.Frame(hdr_row, bg=cell_bg)
            cell.pack(side="left", fill="both", expand=True)
            tk.Label(
                cell, text=txt,
                bg=cell_bg, fg=cell_fg,
                font=("Arial", 13, "bold"),
                justify="center", anchor="center",
            ).pack(expand=True, fill="both")

        # ── Department blocks ─────────────────────────────────────────────────
        for dept_idx, department in enumerate(departments):
            dept_schedule = schedule.get(department, {})

            dept_block = tk.Frame(self._scroll, bg=_BG)
            dept_block.pack(fill="x", pady=(0, 2))

            # Left: department name (spans all 3 shift rows)
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

            # Right: 3 shift rows stacked vertically
            dept_right = tk.Frame(dept_block, bg=_BG)
            dept_right.pack(side="left", fill="both", expand=True)

            for shift_idx, shift in enumerate(SHIFTS):
                shift_bg = _SHIFT_BG_A if shift_idx % 2 == 0 else _SHIFT_BG_B

                shift_row = tk.Frame(dept_right, bg=shift_bg, height=SHIFT_H)
                shift_row.pack(fill="x")
                shift_row.pack_propagate(False)

                # Shift label cell
                shift_cell = tk.Frame(shift_row, bg=shift_bg, width=SHIFT_W)
                shift_cell.pack(side="left", fill="y")
                shift_cell.pack_propagate(False)
                tk.Label(
                    shift_cell,
                    text=SHIFT_LABELS.get(shift, shift),
                    bg=shift_bg, fg=_SHIFT_FG,
                    font=("Arial", 13, "bold"),
                    anchor="center",
                ).pack(expand=True, fill="both")

                # One cell per day
                for day_name, day_offset in visible_days:
                    is_today = (day_offset == today_offset)
                    cell_bg  = _TODAY_COL if is_today else shift_bg
                    cell_fg  = _TODAY_FG  if is_today else _SHIFT_FG

                    cell_data = (
                        dept_schedule.get(day_name, {}).get(shift, {})
                    )
                    employees = (
                        cell_data.get("employees", [])
                        if isinstance(cell_data, dict) else []
                    )

                    day_cell = tk.Frame(
                        shift_row, bg=cell_bg,
                        bd=1, relief="flat",
                        padx=6, pady=3,
                    )
                    day_cell.pack(side="left", fill="both", expand=True)

                    if employees:
                        for emp in employees:
                            name = " ".join(emp.split())
                            display = name if len(name) <= 20 else name[:17].rstrip() + "…"
                            tk.Label(
                                day_cell, text=display,
                                bg=cell_bg, fg=cell_fg,
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

            # Separator after each department
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
