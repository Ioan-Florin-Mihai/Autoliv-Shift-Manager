"""Right panel builder mixin for PlannerDashboard."""

from __future__ import annotations

import customtkinter as ctk

from logic.suggestion_engine import get_smart_suggestions
from logic.unplanned_employees import find_unplanned_employees
from ui.common_ui import (
    BODY_TEXT,
    CARD_WHITE,
    ENTRY_BG,
    LINE_BLUE,
    MUTED_TEXT,
    PANEL_BG,
    PRIMARY_BLUE,
)
from ui.components.constants import (
    ACCENT_BLUE,
    BODY_FONT_SIZE,
    BUTTON_FONT_SIZE,
    DANGER_RED,
    DANGER_RED_HOVER,
    EMPLOYEE_NAME_TEXT,
    HOURS_COLOR_MAP,
    HOVER_BLUE,
    META_FONT_SIZE,
    OUTER_PAD,
    PANEL_NAME_MAX_CHARS,
    RIGHT_PANEL_WIDTH,
    SECTION_TITLE_FONT_SIZE,
    UTILITY_BUTTON_TEXT,
)


class RightPanelMixin:
    """Right panel builder, assignment panel, and suggestions for PlannerDashboard."""

    def _build_right(self):
        frame = ctk.CTkFrame(
            self,
            width=RIGHT_PANEL_WIDTH,
            fg_color=CARD_WHITE,
            corner_radius=18,
            border_width=1,
            border_color=LINE_BLUE,
        )
        frame.grid(row=0, column=2, sticky="nsew")
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=2, minsize=250)
        frame.grid_rowconfigure(2, weight=1, minsize=170)
        frame.grid_rowconfigure(3, weight=0)

        header_section = ctk.CTkFrame(frame, fg_color="transparent")
        header_section.grid(row=0, column=0, sticky="ew", padx=16, pady=(OUTER_PAD, 10))
        header_section.grid_columnconfigure(0, weight=1)

        quick_add_section = ctk.CTkFrame(header_section, fg_color="transparent")
        quick_add_section.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        quick_add_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(quick_add_section, "QUICK ADD").grid(row=0, column=0, sticky="w", pady=(0, 4))
        entry = ctk.CTkEntry(
            quick_add_section,
            textvariable=self.employee_search_var,
            placeholder_text="Scrie numele angajatului",
            height=34,
            fg_color=ENTRY_BG,
            border_width=2,
            border_color=LINE_BLUE,
            text_color=BODY_TEXT,
            font=ctk.CTkFont(size=BODY_FONT_SIZE),
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        entry.bind("<KeyRelease>", self._on_search_change)
        entry.bind("<Return>", lambda _e: self.add_employee_from_search())
        self._search_entry = entry
        self._bind_entry_focus_style(entry)
        self._add_button = ctk.CTkButton(
            quick_add_section,
            text="Adauga",
            command=self.add_employee_from_search,
            fg_color=ACCENT_BLUE,
            hover_color=HOVER_BLUE,
            text_color="white",
            height=34,
            corner_radius=12,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        )
        self._add_button.grid(row=2, column=0, sticky="ew")

        more_actions_section = ctk.CTkFrame(header_section, fg_color="transparent")
        more_actions_section.grid(row=1, column=0, sticky="ew", pady=(6, 2))
        more_actions_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(more_actions_section, "MORE ACTIONS").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._create_secondary_button(more_actions_section, "Angajat Nou", self.add_new_employee, height=24).grid(row=1, column=0, sticky="ew", pady=(0, 2))
        self._create_secondary_button(more_actions_section, "Redenumeste", self.rename_employee_global, height=24).grid(row=2, column=0, sticky="ew", pady=(0, 2))
        self._delete_global_button = ctk.CTkButton(
            more_actions_section,
            text="Sterge global",
            command=self.delete_employee_global,
            fg_color=DANGER_RED,
            hover_color=DANGER_RED_HOVER,
            text_color="white",
            height=24,
            corner_radius=10,
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        )
        self._delete_global_button.grid(row=3, column=0, sticky="ew")

        employees_section = ctk.CTkFrame(frame, fg_color="transparent")
        employees_section.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        employees_section.grid_columnconfigure(0, weight=1)
        employees_section.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            employees_section,
            text="Angajati in celula",
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=SECTION_TITLE_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.assignment_frame = ctk.CTkScrollableFrame(
            employees_section,
            width=RIGHT_PANEL_WIDTH - 32,
            height=250,
            fg_color=PANEL_BG,
        )
        self.assignment_frame.grid(row=1, column=0, sticky="nsew")

        suggestions_section = ctk.CTkFrame(frame, fg_color="transparent")
        suggestions_section.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, OUTER_PAD))
        suggestions_section.grid_columnconfigure(0, weight=1)
        suggestions_section.grid_rowconfigure(1, weight=1, minsize=88)
        self._create_section_label(suggestions_section, "SUGESTII").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.suggestion_frame = ctk.CTkScrollableFrame(
            suggestions_section,
            width=RIGHT_PANEL_WIDTH - 32,
            height=100,
            fg_color=PANEL_BG,
        )
        self.suggestion_frame.grid(row=1, column=0, sticky="nsew")

        self._unplanned_expanded = False
        self._unplanned_missing: list[str] = []
        self.unplanned_section = ctk.CTkFrame(
            frame,
            fg_color=PANEL_BG,
            corner_radius=12,
            border_width=1,
            border_color=LINE_BLUE,
        )
        self.unplanned_section.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, OUTER_PAD))
        self.unplanned_section.grid_columnconfigure(0, weight=1)
        self.unplanned_toggle = ctk.CTkButton(
            self.unplanned_section,
            text="",
            command=self.toggle_unplanned_section,
            fg_color="transparent",
            hover_color=("#EBF3FA", "#2B3643"),
            text_color=UTILITY_BUTTON_TEXT,
            border_width=0,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        )
        self.unplanned_toggle.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        self.unplanned_body = ctk.CTkScrollableFrame(
            self.unplanned_section,
            width=RIGHT_PANEL_WIDTH - 44,
            height=120,
            fg_color=("#F8FBFE", "#202A35"),
            corner_radius=10,
        )
        self.unplanned_body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.unplanned_body.grid_remove()
        self.unplanned_section.grid_remove()

    def render_assignment_panel(self):
        for widget in self.assignment_frame.winfo_children():
            widget.destroy()
        employees = self.current_cell()["employees"]
        cell_colors = self.current_cell().get("colors", {})
        if not employees:
            ctk.CTkLabel(
                self.assignment_frame,
                text=(
                    f"Nu exista angajati in {self.selected_shift}.\n"
                    "1. Click pe o celula din tabel.\n"
                    "2. Cauta angajatul in dreapta.\n"
                    "3. Apasa pe 'Adauga din cautare' sau pe o sugestie."
                ),
                text_color=MUTED_TEXT,
                justify="left",
                wraplength=RIGHT_PANEL_WIDTH - 72,
                font=ctk.CTkFont(size=BODY_FONT_SIZE),
            ).pack(anchor="w", padx=8, pady=8)
            return

        for employee in employees:
            current_color = self._lookup_color(cell_colors, employee)
            hours_label = self._hours_for_employee(cell_colors, employee)
            shown_name = self._display_employee_name(employee, PANEL_NAME_MAX_CHARS)

            card = ctk.CTkFrame(
                self.assignment_frame,
                fg_color=CARD_WHITE,
                border_width=2 if current_color else 1,
                border_color=current_color if current_color else LINE_BLUE,
                corner_radius=10,
            )
            card.pack(fill="x", padx=4, pady=3)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=8, pady=(6, 1))
            top_row.grid_columnconfigure(1, weight=1)

            badge = self._create_hours_badge(top_row, cell_colors, employee)
            badge.grid(row=0, column=0, sticky="w", padx=(0, 8))

            name_label = ctk.CTkLabel(
                top_row,
                text=shown_name,
                text_color=EMPLOYEE_NAME_TEXT,
                font=ctk.CTkFont(size=SECTION_TITLE_FONT_SIZE, weight="bold"),
                anchor="w",
            )
            name_label.grid(row=0, column=1, sticky="ew")
            self._attach_tooltip_if_truncated(name_label, employee, shown_name)

            actions = ctk.CTkFrame(top_row, fg_color="transparent")
            actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
            is_locked = self.store.is_week_locked(self.week_record)
            up_btn = self._create_utility_button(actions, "Sus", lambda e=employee: self.reorder_employee(e, -1), width=36, height=24, font=ctk.CTkFont(size=META_FONT_SIZE))
            down_btn = self._create_utility_button(actions, "Jos", lambda e=employee: self.reorder_employee(e, 1), width=36, height=24, font=ctk.CTkFont(size=META_FONT_SIZE))
            move_btn = self._create_utility_button(actions, "Mut", lambda e=employee: self.move_employee_to_shift(e), width=36, height=24, font=ctk.CTkFont(size=META_FONT_SIZE))
            remove_btn = ctk.CTkButton(actions, text="x", width=26, height=24, fg_color=DANGER_RED, hover_color=DANGER_RED_HOVER, text_color="white", font=ctk.CTkFont(size=META_FONT_SIZE), command=lambda e=employee: self.remove_employee(e))
            if is_locked:
                for btn in (up_btn, down_btn, move_btn, remove_btn):
                    btn.configure(state="disabled")
            up_btn.pack(side="left", padx=(0, 3))
            down_btn.pack(side="left", padx=3)
            move_btn.pack(side="left", padx=3)
            remove_btn.pack(side="left", padx=(3, 0))

            palette_row = ctk.CTkFrame(card, fg_color="transparent")
            palette_row.pack(fill="x", padx=8, pady=(1, 5))
            ctk.CTkLabel(
                palette_row,
                text="Program:",
                text_color=MUTED_TEXT,
                font=ctk.CTkFont(size=META_FONT_SIZE),
            ).pack(side="left", padx=(0, 6))
            for label in ("8h", "12h"):
                is_active = hours_label == label
                bg = HOURS_COLOR_MAP[label]
                ctk.CTkButton(
                    palette_row,
                    text=label,
                    width=42,
                    height=22,
                    corner_radius=6,
                    fg_color=bg,
                    hover_color=bg,
                    border_width=2 if is_active else 0,
                    border_color="white",
                    text_color="white",
                    font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
                    command=lambda e=employee, h=label: self._set_employee_hours(e, h),
                ).pack(side="left", padx=2)

    def refresh_suggestions(self):
        for widget in self.suggestion_frame.winfo_children():
            widget.destroy()
        suggestions = self.employee_store.search(self.employee_search_var.get())
        if not suggestions:
            ctk.CTkLabel(
                self.suggestion_frame,
                text="Nicio sugestie.",
                text_color=MUTED_TEXT,
                font=ctk.CTkFont(size=BODY_FONT_SIZE),
            ).pack(anchor="w", padx=8, pady=8)
            return
        try:
            context = {
                "department": self.selected_department,
                "shift": self.selected_shift,
                "day": self.selected_day,
                "mode": self.current_mode,
                "week_start": self.week_record.get("week_start", ""),
                "employee_departments": self.employee_store.get_department_map(),
            }
            ranked = get_smart_suggestions(context, suggestions, self.store.data)
            suggestions = [r.name for r in ranked]
        except (OSError, ValueError, RuntimeError):
            pass
        is_locked = self.store.is_week_locked(self.week_record)
        for employee in suggestions:
            btn = ctk.CTkButton(
                self.suggestion_frame,
                text=employee,
                anchor="w",
                height=26,
                fg_color=("#F8FBFE", "#202A35"),
                text_color=UTILITY_BUTTON_TEXT,
                hover_color=("#EBF3FA", "#2B3A4B"),
                border_width=1,
                border_color=LINE_BLUE,
                corner_radius=10,
                font=ctk.CTkFont(size=META_FONT_SIZE),
                command=lambda e=employee: self.add_employee_to_selected_cell(e),
            )
            if is_locked:
                btn.configure(state="disabled")
            btn.pack(fill="x", padx=4, pady=2)

    def render_unplanned_warning(self):
        if not hasattr(self, "unplanned_section"):
            return
        try:
            missing = find_unplanned_employees(self.employee_store.get_all(), self.week_record)
        except (OSError, ValueError, RuntimeError):
            missing = []

        if not missing:
            self._unplanned_missing = []
            self._unplanned_expanded = False
            self.unplanned_section.grid_remove()
            return

        self._unplanned_missing = list(missing)
        self._refresh_unplanned_section()
        self.unplanned_section.grid()

    def toggle_unplanned_section(self):
        self._unplanned_expanded = not self._unplanned_expanded
        self._refresh_unplanned_section()

    def _refresh_unplanned_section(self):
        if not hasattr(self, "unplanned_toggle"):
            return
        count = len(self._unplanned_missing)
        arrow = "▲" if self._unplanned_expanded else "▼"
        self.unplanned_toggle.configure(text=f"Neplanificati ({count}) {arrow}")

        for widget in self.unplanned_body.winfo_children():
            widget.destroy()

        if not self._unplanned_expanded:
            self.unplanned_body.grid_remove()
            return

        self.unplanned_body.grid()
        for employee in self._unplanned_missing:
            ctk.CTkLabel(
                self.unplanned_body,
                text=employee,
                text_color=BODY_TEXT,
                anchor="w",
                justify="left",
                font=ctk.CTkFont(size=META_FONT_SIZE),
            ).pack(fill="x", padx=8, pady=2)

    def _on_search_change(self, _event=None):
        """Debounce 200 ms: evita refresh la fiecare tasta."""
        if hasattr(self, "_search_debounce_id"):
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(200, self.refresh_suggestions)
