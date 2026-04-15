"""Right panel builder mixin for PlannerDashboard."""

from __future__ import annotations

import customtkinter as ctk

from logic.suggestion_engine import get_smart_suggestions
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
    DANGER_RED,
    DANGER_RED_HOVER,
    EMPLOYEE_NAME_TEXT,
    HOURS_COLOR_MAP,
    HOVER_BLUE,
    OUTER_PAD,
    PANEL_NAME_MAX_CHARS,
    RIGHT_PANEL_WIDTH,
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

        header_section = ctk.CTkFrame(frame, fg_color="transparent")
        header_section.grid(row=0, column=0, sticky="ew", padx=20, pady=(OUTER_PAD, 8))
        header_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(header_section, "CONTEXT").grid(row=0, column=0, sticky="w", pady=(0, 4))
        department_nav = ctk.CTkFrame(header_section, fg_color="transparent")
        department_nav.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        department_nav.grid_columnconfigure(1, weight=1)
        self.department_prev_button = self._create_utility_button(
            department_nav,
            "◀",
            self.prev_department,
            width=36,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.department_prev_button.grid(row=0, column=0, sticky="w")
        self.department_name_label = ctk.CTkLabel(
            department_nav,
            textvariable=self.department_name_var,
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="center",
        )
        self.department_name_label.grid(row=0, column=1, sticky="ew", padx=8)
        self.department_next_button = self._create_utility_button(
            department_nav,
            "▶",
            self.next_department,
            width=36,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.department_next_button.grid(row=0, column=2, sticky="e")
        self.cell_title = ctk.CTkLabel(header_section, text="Celula selectata", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=20, weight="bold"))
        self.cell_title.grid(row=2, column=0, sticky="w")
        self.cell_meta = ctk.CTkLabel(header_section, text="", text_color=MUTED_TEXT, justify="left")
        self.cell_meta.grid(row=3, column=0, sticky="w", pady=(2, 4))

        quick_add_section = ctk.CTkFrame(header_section, fg_color="transparent")
        quick_add_section.grid(row=4, column=0, sticky="ew", pady=(4, 4))
        quick_add_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(quick_add_section, "QUICK ADD").grid(row=0, column=0, sticky="w", pady=(0, 3))
        entry = ctk.CTkEntry(
            quick_add_section,
            textvariable=self.employee_search_var,
            placeholder_text="Scrie numele angajatului",
            height=30,
            fg_color=ENTRY_BG,
            border_width=2,
            border_color=LINE_BLUE,
            text_color=BODY_TEXT,
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(0, 3))
        entry.bind("<KeyRelease>", self._on_search_change)
        entry.bind("<Return>", lambda _e: self.add_employee_from_search())
        self._search_entry = entry
        self._bind_entry_focus_style(entry)
        self._add_button = ctk.CTkButton(
            quick_add_section,
            text="Adaugă",
            command=self.add_employee_from_search,
            fg_color=ACCENT_BLUE,
            hover_color=HOVER_BLUE,
            text_color="white",
            height=32,
            corner_radius=12,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._add_button.grid(row=2, column=0, sticky="ew")

        more_actions_section = ctk.CTkFrame(header_section, fg_color="transparent")
        more_actions_section.grid(row=5, column=0, sticky="ew", pady=(4, 2))
        more_actions_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(more_actions_section, "MORE ACTIONS").grid(row=0, column=0, sticky="w", pady=(0, 3))
        self._create_secondary_button(more_actions_section, "Angajat Nou", self.add_new_employee, height=24).grid(row=1, column=0, sticky="ew", pady=(0, 2))
        self._create_secondary_button(more_actions_section, "Redenumește", self.rename_employee_global, height=24).grid(row=2, column=0, sticky="ew", pady=(0, 2))
        self._delete_global_button = ctk.CTkButton(
            more_actions_section,
            text="Șterge global",
            command=self.delete_employee_global,
            fg_color=DANGER_RED,
            hover_color=DANGER_RED_HOVER,
            text_color="white",
            height=24,
            corner_radius=10,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self._delete_global_button.grid(row=3, column=0, sticky="ew")

        employees_section = ctk.CTkFrame(frame, fg_color="transparent")
        employees_section.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        employees_section.grid_columnconfigure(0, weight=1)
        employees_section.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(employees_section, text="Angajati in celula", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.assignment_frame = ctk.CTkScrollableFrame(employees_section, width=370, height=250, fg_color=PANEL_BG)
        self.assignment_frame.grid(row=1, column=0, sticky="nsew")

        suggestions_section = ctk.CTkFrame(frame, fg_color="transparent")
        suggestions_section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, OUTER_PAD))
        suggestions_section.grid_columnconfigure(0, weight=1)
        suggestions_section.grid_rowconfigure(1, weight=1, minsize=88)
        self._create_section_label(suggestions_section, "SUGESTII").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.suggestion_frame = ctk.CTkScrollableFrame(suggestions_section, width=370, height=100, fg_color=PANEL_BG)
        self.suggestion_frame.grid(row=1, column=0, sticky="nsew")

    def render_assignment_panel(self):
        for widget in self.assignment_frame.winfo_children():
            widget.destroy()
        employees   = self.current_cell()["employees"]
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
            ).pack(anchor="w", padx=8, pady=8)
            return

        for employee in employees:
            current_color = self._lookup_color(cell_colors, employee)
            hours_label = self._hours_for_employee(cell_colors, employee)
            shown_name = self._display_employee_name(employee, PANEL_NAME_MAX_CHARS)

            # Card angajat
            card = ctk.CTkFrame(
                self.assignment_frame,
                fg_color=CARD_WHITE,
                border_width=2 if current_color else 1,
                border_color=current_color if current_color else LINE_BLUE,
                corner_radius=10,
            )
            card.pack(fill="x", padx=4, pady=3)

            # Randul de sus: indicator culoare + nume + butoane actiune
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=8, pady=(6, 1))
            top_row.grid_columnconfigure(1, weight=1)

            badge = self._create_hours_badge(top_row, cell_colors, employee)
            badge.grid(row=0, column=0, sticky="w", padx=(0, 8))

            name_label = ctk.CTkLabel(
                top_row,
                text=shown_name,
                text_color=EMPLOYEE_NAME_TEXT,
                font=ctk.CTkFont(size=15, weight="bold"),
                anchor="w",
            )
            name_label.grid(row=0, column=1, sticky="ew")
            self._attach_tooltip_if_truncated(name_label, employee, shown_name)

            actions = ctk.CTkFrame(top_row, fg_color="transparent")
            actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
            is_locked = self.store.is_week_locked(self.week_record)
            up_btn = self._create_utility_button(actions, "Sus", lambda e=employee: self.reorder_employee(e, -1), width=36, height=24, font=ctk.CTkFont(size=10))
            down_btn = self._create_utility_button(actions, "Jos", lambda e=employee: self.reorder_employee(e, 1), width=36, height=24, font=ctk.CTkFont(size=10))
            move_btn = self._create_utility_button(actions, "Mut", lambda e=employee: self.move_employee_to_shift(e), width=36, height=24, font=ctk.CTkFont(size=10))
            remove_btn = ctk.CTkButton(actions, text="✕", width=26, height=24, fg_color=DANGER_RED, hover_color=DANGER_RED_HOVER, text_color="white", font=ctk.CTkFont(size=11), command=lambda e=employee: self.remove_employee(e))
            if is_locked:
                for btn in (up_btn, down_btn, move_btn, remove_btn):
                    btn.configure(state="disabled")
            up_btn.pack(side="left", padx=(0, 3))
            down_btn.pack(side="left", padx=3)
            move_btn.pack(side="left", padx=3)
            remove_btn.pack(side="left", padx=(3, 0))

            # Randul de jos: selector ore (comportament radio)
            palette_row = ctk.CTkFrame(card, fg_color="transparent")
            palette_row.pack(fill="x", padx=8, pady=(1, 5))
            ctk.CTkLabel(palette_row, text="Program:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
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
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda e=employee, h=label: self._set_employee_hours(e, h),
                ).pack(side="left", padx=2)

    def refresh_suggestions(self):
        for widget in self.suggestion_frame.winfo_children():
            widget.destroy()
        suggestions = self.employee_store.search(self.employee_search_var.get())
        if not suggestions:
            ctk.CTkLabel(self.suggestion_frame, text="Nicio sugestie.", text_color=MUTED_TEXT).pack(anchor="w", padx=8, pady=8)
            return
        # Aplica ranking inteligent – doar reordonare, fara filtrare (risc zero de regresie)
        try:
            context = {
                "department": self.selected_department,
                "shift":      self.selected_shift,
                "day":        self.selected_day,
                "mode":       self.current_mode,
                "week_start": self.week_record.get("week_start", ""),
            }
            ranked = get_smart_suggestions(context, suggestions, self.store.data)
            suggestions = [r.name for r in ranked]
        except Exception:
            pass  # fallback: pastreaza ordinea alfabetica originala
        is_locked = self.store.is_week_locked(self.week_record)
        for employee in suggestions:
            btn = ctk.CTkButton(
                self.suggestion_frame,
                text=employee,
                anchor="w",
                height=24,
                fg_color=("#F8FBFE", "#202A35"),
                text_color=UTILITY_BUTTON_TEXT,
                hover_color=("#EBF3FA", "#2B3A4B"),
                border_width=1,
                border_color=LINE_BLUE,
                corner_radius=10,
                font=ctk.CTkFont(size=11),
                command=lambda e=employee: self.add_employee_to_selected_cell(e),
            )
            if is_locked:
                btn.configure(state="disabled")
            btn.pack(fill="x", padx=4, pady=2)

    def _on_search_change(self, _event=None):
        """Debounce 200 ms: evita refresh la fiecare tasta."""
        if hasattr(self, "_search_debounce_id"):
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(200, self.refresh_suggestions)
