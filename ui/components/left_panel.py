"""Left panel builder mixin for PlannerDashboard."""

from __future__ import annotations

import customtkinter as ctk

from ui.common_ui import BODY_TEXT, CARD_WHITE, LINE_BLUE, MUTED_TEXT, PRIMARY_BLUE
from ui.components.constants import (
    ACCENT_BLUE,
    HOVER_BLUE,
    LEFT_PANEL_WIDTH,
    OUTER_PAD,
    PANEL_GAP,
    PRIMARY_BUTTON_HEIGHT,
    SECONDARY_BUTTON_FG,
    SECONDARY_BUTTON_HEIGHT,
    SECONDARY_BUTTON_HOVER,
    SECTION_GAP,
    SECTION_INNER_GAP,
    SECTION_LABEL_FONT_SIZE,
    UTILITY_BUTTON_FG,
    UTILITY_BUTTON_HEIGHT,
    UTILITY_BUTTON_HOVER,
    UTILITY_BUTTON_TEXT,
)


class LeftPanelMixin:
    """UI factory helpers and left-panel builder for PlannerDashboard."""

    def _create_section_label(self, parent, text: str):
        return ctk.CTkLabel(
            parent,
            text=text,
            text_color=MUTED_TEXT,
            font=ctk.CTkFont(size=SECTION_LABEL_FONT_SIZE, weight="bold"),
        )

    def _create_secondary_button(self, parent, text: str, command, **kwargs):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", SECONDARY_BUTTON_HEIGHT),
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=kwargs.pop("fg_color", SECONDARY_BUTTON_FG),
            hover_color=kwargs.pop("hover_color", SECONDARY_BUTTON_HOVER),
            text_color=kwargs.pop("text_color", UTILITY_BUTTON_TEXT),
            border_width=kwargs.pop("border_width", 1),
            border_color=kwargs.pop("border_color", LINE_BLUE),
            font=kwargs.pop("font", ctk.CTkFont(size=13, weight="bold")),
            **kwargs,
        )

    def _create_utility_button(self, parent, text: str, command, **kwargs):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", UTILITY_BUTTON_HEIGHT),
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=kwargs.pop("fg_color", UTILITY_BUTTON_FG),
            hover_color=kwargs.pop("hover_color", UTILITY_BUTTON_HOVER),
            text_color=kwargs.pop("text_color", UTILITY_BUTTON_TEXT),
            border_width=kwargs.pop("border_width", 1),
            border_color=kwargs.pop("border_color", LINE_BLUE),
            font=kwargs.pop("font", ctk.CTkFont(size=12, weight="bold")),
            **kwargs,
        )

    def _bind_entry_focus_style(self, entry: ctk.CTkEntry):
        entry.bind("<FocusIn>", lambda _event, widget=entry: widget.configure(border_color=ACCENT_BLUE), add="+")
        entry.bind("<FocusOut>", lambda _event, widget=entry: widget.configure(border_color=LINE_BLUE), add="+")

    def _build_left(self):
        frame = ctk.CTkFrame(
            self,
            width=LEFT_PANEL_WIDTH,
            fg_color=CARD_WHITE,
            corner_radius=18,
            border_width=1,
            border_color=LINE_BLUE,
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, PANEL_GAP))
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        plan_section = ctk.CTkFrame(frame, fg_color="transparent")
        plan_section.grid(row=0, column=0, sticky="ew", padx=OUTER_PAD, pady=(OUTER_PAD, SECTION_GAP))
        plan_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(plan_section, "PLAN").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        ctk.CTkLabel(plan_section, text="Saptamana", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=19, weight="bold")).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(plan_section, textvariable=self.week_var, text_color=MUTED_TEXT, justify="left").grid(row=2, column=0, sticky="w", pady=(2, SECTION_INNER_GAP))
        week_nav = ctk.CTkFrame(plan_section, fg_color="transparent")
        week_nav.grid(row=3, column=0, sticky="ew", pady=(0, SECTION_INNER_GAP))
        week_nav.grid_columnconfigure((0, 1, 2), weight=1)
        self._create_utility_button(week_nav, "<", lambda: self.shift_week(-1), width=42, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._create_secondary_button(week_nav, "Sapt. curenta", self.go_to_current_week, height=UTILITY_BUTTON_HEIGHT, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, sticky="ew", padx=4)
        self._create_utility_button(week_nav, ">", lambda: self.shift_week(1), width=42, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        ctk.CTkButton(
            plan_section,
            text="Salveaza",
            command=self.save_week,
            fg_color=ACCENT_BLUE,
            hover_color=HOVER_BLUE,
            text_color="white",
            height=PRIMARY_BUTTON_HEIGHT,
            corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=4, column=0, sticky="ew")
        # Indicator pentru modificari nesalvate
        action_row = ctk.CTkFrame(plan_section, fg_color="transparent")
        action_row.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        action_row.grid_columnconfigure(0, weight=1)
        self._dirty_indicator = ctk.CTkLabel(
            action_row, text="", text_color="#E74C3C",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self._dirty_indicator.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            plan_section, textvariable=self._last_saved_var,
            text_color=MUTED_TEXT, font=ctk.CTkFont(size=10),
        ).grid(row=6, column=0, sticky="w", pady=(2, 0))

        nav_section = ctk.CTkFrame(frame, fg_color="transparent")
        nav_section.grid(row=1, column=0, sticky="ew", padx=OUTER_PAD, pady=(0, SECTION_GAP))
        nav_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(nav_section, "NAVIGATION").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        self._create_secondary_button(nav_section, "Calendar", self.pick_week).grid(row=1, column=0, sticky="ew", pady=(0, SECTION_INNER_GAP))
        ctk.CTkLabel(nav_section, text="Istoric", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.history_menu = ctk.CTkOptionMenu(
            nav_section,
            variable=self.history_var,
            values=[""],
            command=self.load_history_week,
            fg_color=SECONDARY_BUTTON_FG,
            button_color=SECONDARY_BUTTON_HOVER,
            button_hover_color=HOVER_BLUE,
            text_color=UTILITY_BUTTON_TEXT,
            dropdown_fg_color=CARD_WHITE,
            dropdown_text_color=BODY_TEXT,
        )
        self.history_menu.grid(row=3, column=0, sticky="ew")
        # Buton publicare / deblocare saptamana
        self._lock_button = ctk.CTkButton(
            nav_section,
            text="🔓 Saptamana deschisa",
            command=self.lock_week_toggle,
            height=UTILITY_BUTTON_HEIGHT,
            corner_radius=10,
            fg_color="#27AE60",
            hover_color="#1E8449",
            text_color="white",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self._lock_button.grid(row=4, column=0, sticky="ew", pady=(SECTION_INNER_GAP, 0))
        ctk.CTkLabel(
            nav_section,
            textvariable=self._lock_state_var,
            text_color=("#8A1F17", "#FFB3AD"),
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        self._publish_button = ctk.CTkButton(
            nav_section,
            text="PUBLICA PE ECRANE",
            command=self.publish_to_tv,
            height=PRIMARY_BUTTON_HEIGHT,
            corner_radius=12,
            fg_color=ACCENT_BLUE,
            hover_color=HOVER_BLUE,
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._publish_button.grid(row=6, column=0, sticky="ew", pady=(SECTION_INNER_GAP, 0))

        settings_section = ctk.CTkFrame(frame, fg_color="transparent")
        settings_section.grid(row=2, column=0, sticky="nsew", padx=OUTER_PAD, pady=(0, OUTER_PAD))
        settings_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(settings_section, "SETTINGS").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        self.theme_switch = ctk.CTkSwitch(settings_section, text="Dark Mode", command=self.toggle_theme, onvalue="Dark", offvalue="Light")
        self.theme_switch.grid(row=1, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        self._create_secondary_button(settings_section, "Status Sistem", self.open_system_status, height=SECONDARY_BUTTON_HEIGHT).grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._create_secondary_button(settings_section, "Restore backup", self.restore_backup_dialog, height=SECONDARY_BUTTON_HEIGHT).grid(row=3, column=0, sticky="ew")
