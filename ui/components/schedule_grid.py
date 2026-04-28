"""Schedule grid rendering mixin for PlannerDashboard."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from logic.schedule_store import SHIFTS, format_day_label
from ui.common_ui import LINE_BLUE, PRIMARY_BLUE
from ui.components.constants import (
    ACCENT_BLUE,
    BADGE_HEIGHT,
    BADGE_WIDTH,
    CELL_MIN_HEIGHT,
    EMPLOYEE_NAME_TEXT,
    EMPLOYEE_ROW_PADY,
    GRID_BORDER_DARK,
    GRID_BORDER_LIGHT,
    GRID_CELL_BG,
    GRID_CELL_PAD,
    GRID_HEADER_HEIGHT,
    GRID_HOVER_DARK,
    GRID_HOVER_LIGHT,
    GRID_INNER_PAD,
    GRID_NAME_MAX_CHARS,
    HEADER_FONT_SIZE,
    HOURS_COLOR_MAP,
    META_FONT_SIZE,
    SECTION_TITLE_FONT_SIZE,
    SELECTED_BG,
    SHIFT_FONT_SIZE,
    SOFT_BLUE,
    SUBTLE_HINT_TEXT,
    VISIBLE_EMPLOYEE_ROWS,
)
from ui.components.dialogs import HoverTooltip


class ScheduleGridMixin:
    """Methods for rendering and interacting with the schedule grid."""

    # Coloane de zi mai compacte pentru a afisa saptamana mai confortabil.
    _DAY_COLUMN_WIDTH = 136
    _GRID_PAD_X = 3
    _SHIFT_COLUMN_WIDTH = 68

    def _resolve_theme_color(self, color_value):
        if isinstance(color_value, (tuple, list)):
            return color_value[1] if ctk.get_appearance_mode() == "Dark" else color_value[0]
        return color_value

    def _hours_for_employee(self, colors: dict, employee: str) -> str:
        color = self._lookup_color(colors or {}, employee)
        return "12h" if (color or "").strip().upper() == HOURS_COLOR_MAP["12h"].upper() else "8h"

    def _hours_badge_value(self, colors: dict, employee: str) -> str:
        return "12" if self._hours_for_employee(colors, employee) == "12h" else "8"

    def _display_employee_name(self, employee: str, max_chars: int) -> str:
        clean = " ".join(employee.split()).strip()
        if len(clean) <= max_chars:
            return clean
        cutoff = max(14, max_chars - 3)
        return clean[:cutoff].rstrip() + "..."

    def _attach_tooltip_if_truncated(self, widget, full_text: str, shown_text: str):
        if full_text != shown_text:
            HoverTooltip(widget, full_text)

    def _on_cell_mousewheel(self, event, canvas: tk.Canvas):
        if not canvas or not canvas.winfo_exists():
            return "break"
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
        if delta:
            canvas.yview_scroll(delta, "units")
        return "break"

    def _bind_cell_mousewheel(self, widget, canvas: tk.Canvas):
        if not widget:
            return
        widget.bind("<MouseWheel>", lambda event, target=canvas: self._on_cell_mousewheel(event, target), add="+")
        widget.bind("<Button-4>", lambda event, target=canvas: self._on_cell_mousewheel(event, target), add="+")
        widget.bind("<Button-5>", lambda event, target=canvas: self._on_cell_mousewheel(event, target), add="+")

    def _create_hours_badge(self, parent, colors: dict, employee: str):
        hours_label = self._hours_for_employee(colors, employee)
        badge_color = self._lookup_color(colors or {}, employee) or HOURS_COLOR_MAP[hours_label]
        badge = ctk.CTkLabel(
            parent,
            text=self._hours_badge_value(colors, employee),
            width=BADGE_WIDTH,
            height=BADGE_HEIGHT,
            corner_radius=13,
            fg_color=badge_color,
            text_color="white",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="center",
        )
        return badge

    def _set_employee_hours(self, employee: str, hours_label: str):
        if hours_label not in HOURS_COLOR_MAP:
            return
        self.set_employee_color(employee, HOURS_COLOR_MAP[hours_label])

    def _grid_border_theme(self) -> tuple[str, str, str]:
        is_dark = ctk.get_appearance_mode() == "Dark"
        normal = GRID_BORDER_DARK if is_dark else GRID_BORDER_LIGHT
        hover = GRID_HOVER_DARK if is_dark else GRID_HOVER_LIGHT
        selected = "#8EB8E5" if is_dark else ACCENT_BLUE
        return normal, hover, selected

    def _grid_border_width(self, is_selected: bool = False) -> int:
        if is_selected:
            return 2
        return 2 if ctk.get_appearance_mode() == "Dark" else 1

    def _apply_cell_frame_style(self, day_name: str, shift: str, hover: bool = False):
        frame = self._grid_cell_frames.get((day_name, shift))
        if not frame or not frame.winfo_exists():
            return
        normal_border, hover_border, selected_border = self._grid_border_theme()
        is_selected = self.selected_day == day_name and self.selected_shift == shift
        if is_selected:
            fg_color = SELECTED_BG
            border_color = selected_border
        else:
            fg_color = GRID_CELL_BG
            border_color = hover_border if hover else normal_border
        frame.configure(fg_color=fg_color, border_width=self._grid_border_width(is_selected), border_color=border_color)
        canvas = self._grid_cell_canvases.get((day_name, shift))
        if canvas:
            resolved = self._resolve_theme_color(fg_color)
            canvas.configure(bg=resolved)
            host = canvas.master
            if host and isinstance(host, tk.Frame):
                host.configure(bg=resolved)

    def _get_cell_colors(self, day_name: str, shift: str) -> dict:
        """Returneaza dict-ul de culori al celulei curente {nume: hex_color}."""
        cell = self.current_mode_record()["schedule"][self.selected_department][day_name][shift]
        colors = cell.get("colors", {})
        return colors if isinstance(colors, dict) else {}

    def _lookup_color(self, colors: dict, employee: str):
        """Cauta culoarea unui angajat in colors dict (case-insensitive)."""
        for k, v in colors.items():
            if k.casefold() == employee.casefold():
                return v
        return None

    def render_grid(self):
        left_parent = getattr(self, "grid_left", None)
        days_parent = getattr(self, "grid_days_frame", None)
        if not left_parent or not days_parent:
            return

        for widget in left_parent.winfo_children():
            widget.destroy()
        for widget in days_parent.winfo_children():
            widget.destroy()
        self._grid_cell_frames = {}   # reseteaza cache-ul la rebuild complet
        self._grid_cell_canvases = {}
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        visible_days = self._visible_days()
        left_parent.grid_columnconfigure(0, weight=0, minsize=self._SHIFT_COLUMN_WIDTH)
        left_parent.grid_rowconfigure(0, weight=0, minsize=GRID_HEADER_HEIGHT)
        days_parent.grid_rowconfigure(0, weight=0, minsize=GRID_HEADER_HEIGHT)
        for idx in range(len(visible_days)):
            days_parent.grid_columnconfigure(idx, weight=0, minsize=self._DAY_COLUMN_WIDTH)

        ctk.CTkLabel(
            left_parent,
            text="Schimb",
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=SECTION_TITLE_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=0, padx=(6, 10), pady=10, sticky="w")

        for day_idx, (_day_name, day_offset) in enumerate(visible_days, start=0):
            header_fg = SOFT_BLUE
            cell = ctk.CTkFrame(
                days_parent,
                fg_color=header_fg,
                corner_radius=12,
                border_width=1,
                border_color=LINE_BLUE,
                width=self._DAY_COLUMN_WIDTH,
                height=GRID_HEADER_HEIGHT,
            )
            cell.grid(row=0, column=day_idx, padx=self._GRID_PAD_X, pady=GRID_CELL_PAD, sticky="ew")
            cell.grid_propagate(False)
            ctk.CTkLabel(
                cell,
                text=format_day_label(start, day_offset),
                text_color=PRIMARY_BLUE,
                font=ctk.CTkFont(size=HEADER_FONT_SIZE, weight="bold"),
            ).pack(padx=12, pady=10)

        for row_idx, shift in enumerate(SHIFTS, start=1):
            left_parent.grid_rowconfigure(row_idx, weight=0, minsize=CELL_MIN_HEIGHT + 12)
            days_parent.grid_rowconfigure(row_idx, weight=0, minsize=CELL_MIN_HEIGHT + 12)
            ctk.CTkLabel(
                left_parent,
                text=shift,
                text_color=PRIMARY_BLUE,
                font=ctk.CTkFont(size=SHIFT_FONT_SIZE, weight="bold"),
            ).grid(row=row_idx, column=0, padx=(6, 10), pady=10, sticky="nw")

            for day_idx, (day_name, _) in enumerate(visible_days, start=0):
                cell_data  = self.current_mode_record()["schedule"][self.selected_department][day_name][shift]
                employees  = cell_data.get("employees", [])
                cell_colors = cell_data.get("colors", {})
                normal_border, _hover_border, selected_border = self._grid_border_theme()
                is_selected = self.selected_day == day_name and self.selected_shift == shift
                if is_selected:
                    cell_bg = SELECTED_BG
                else:
                    cell_bg = GRID_CELL_BG
                border_color_active = selected_border if is_selected else normal_border

                # Celula — frame clickabil
                cell_frame = ctk.CTkFrame(
                    days_parent,
                    fg_color=cell_bg,
                    corner_radius=16,
                    border_width=self._grid_border_width(is_selected),
                    border_color=border_color_active,
                    width=self._DAY_COLUMN_WIDTH,
                    height=CELL_MIN_HEIGHT,
                )
                cell_frame.grid(row=row_idx, column=day_idx, padx=self._GRID_PAD_X, pady=GRID_CELL_PAD, sticky="nsew")
                cell_frame.grid_propagate(False)
                cell_frame.pack_propagate(False)
                cell_frame.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                cell_frame.bind("<Enter>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=True))
                cell_frame.bind("<Leave>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=False))
                self._grid_cell_frames[(day_name, shift)] = cell_frame

                # ── Scroll container: tk.Frame → Canvas + Scrollbar → inner_frame ──
                resolved_bg = self._resolve_theme_color(cell_bg)
                scroll_host = tk.Frame(cell_frame, bg=resolved_bg, highlightthickness=0)
                scroll_host.pack(fill="both", expand=True, padx=GRID_INNER_PAD, pady=(GRID_INNER_PAD, GRID_INNER_PAD - 1))

                content_canvas = tk.Canvas(
                    scroll_host, highlightthickness=0, bd=0, bg=resolved_bg,
                )
                scrollbar = tk.Scrollbar(
                    scroll_host, orient="vertical", command=content_canvas.yview, width=8,
                )
                content_canvas.configure(yscrollcommand=scrollbar.set)

                content_frame = tk.Frame(content_canvas, bg=resolved_bg)
                canvas_window = content_canvas.create_window((0, 0), window=content_frame, anchor="nw")

                content_frame.bind(
                    "<Configure>",
                    lambda _e, c=content_canvas: c.configure(scrollregion=c.bbox("all")),
                )
                content_canvas.bind(
                    "<Configure>",
                    lambda e, c=content_canvas, wid=canvas_window: c.itemconfigure(wid, width=e.width),
                )

                content_canvas.pack(side="left", fill="both", expand=True)
                if len(employees) > VISIBLE_EMPLOYEE_ROWS:
                    scrollbar.pack(side="right", fill="y")

                self._grid_cell_canvases[(day_name, shift)] = content_canvas
                self._bind_cell_mousewheel(content_canvas, content_canvas)
                self._bind_cell_mousewheel(content_frame, content_canvas)
                content_canvas.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                content_frame.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                if employees:
                    # ── Contor angajați în celulă ──────────────────────────────
                    count_row = tk.Frame(content_frame, bg=resolved_bg)
                    count_row.pack(fill="x", padx=6, pady=(2, 0))
                    self._bind_cell_mousewheel(count_row, content_canvas)
                    count_row.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                    count_lbl = tk.Label(
                        count_row,
                        text=f"\u2191 {len(employees)}",
                        bg=resolved_bg,
                        fg=self._resolve_theme_color(SUBTLE_HINT_TEXT),
                        font=("Segoe UI", 8, "bold"),
                    )
                    count_lbl.pack(anchor="e")
                    self._bind_cell_mousewheel(count_lbl, content_canvas)
                    count_lbl.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                    for emp in employees:
                        emp_row = tk.Frame(content_frame, bg=resolved_bg)
                        emp_row.pack(fill="x", padx=6, pady=EMPLOYEE_ROW_PADY)
                        self._bind_cell_mousewheel(emp_row, content_canvas)
                        emp_row.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                        badge = self._create_hours_badge(emp_row, cell_colors, emp)
                        badge.pack(side="left", padx=(0, 8))
                        self._bind_cell_mousewheel(badge, content_canvas)
                        badge.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                        shown_name = self._display_employee_name(emp, GRID_NAME_MAX_CHARS)
                        lbl = tk.Label(
                            emp_row,
                            text=shown_name,
                            bg=resolved_bg,
                            fg=self._resolve_theme_color(EMPLOYEE_NAME_TEXT),
                            font=("Segoe UI", 10, "bold"),
                            anchor="w",
                        )
                        lbl.pack(side="left", fill="x", expand=True)
                        self._bind_cell_mousewheel(lbl, content_canvas)
                        lbl.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                        self._attach_tooltip_if_truncated(lbl, emp, shown_name)
                else:
                    add_lbl = tk.Label(
                        content_frame,
                        text="+ adaugare",
                        bg=resolved_bg,
                        fg=self._resolve_theme_color(SUBTLE_HINT_TEXT),
                        font=("Segoe UI", META_FONT_SIZE),
                    )
                    add_lbl.pack(expand=True, pady=16)
                    self._bind_cell_mousewheel(add_lbl, content_canvas)
                    add_lbl.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                self._apply_cell_frame_style(day_name, shift, hover=False)

        try:
            if getattr(self, "grid_days_canvas", None) and self.grid_days_canvas.winfo_exists():
                self.grid_days_canvas.configure(scrollregion=self.grid_days_canvas.bbox("all"))
        except tk.TclError:
            pass

    def render_day_toggle_buttons(self):
        return
