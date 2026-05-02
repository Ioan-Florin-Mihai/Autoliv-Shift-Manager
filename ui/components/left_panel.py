"""Left panel builder mixin for PlannerDashboard."""

from __future__ import annotations

import customtkinter as ctk

from ui.common_ui import BODY_TEXT, CARD_WHITE, LINE_BLUE, MUTED_TEXT, PRIMARY_BLUE
from ui.components.constants import (
    ACCENT_BLUE,
    BODY_FONT_SIZE,
    BUTTON_FONT_SIZE,
    BUTTON_STRONG_FONT_SIZE,
    HOVER_BLUE,
    LEFT_PANEL_WIDTH,
    META_FONT_SIZE,
    PANEL_GAP,
    PANEL_HEADER_FONT_SIZE,
    SECONDARY_BUTTON_FG,
    SECONDARY_BUTTON_HOVER,
    SECTION_LABEL_FONT_SIZE,
    SECTION_TITLE_FONT_SIZE,
    UTILITY_BUTTON_FG,
    UTILITY_BUTTON_HOVER,
    UTILITY_BUTTON_TEXT,
)

LEFT_PANEL_OUTER_PAD = 12
LEFT_PANEL_SECTION_GAP = 18
LEFT_PANEL_SECTION_INNER_GAP = 8
LEFT_PANEL_PRIMARY_HEIGHT = 34
LEFT_PANEL_SECONDARY_HEIGHT = 30
LEFT_PANEL_UTILITY_HEIGHT = 28


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
            height=kwargs.pop("height", LEFT_PANEL_SECONDARY_HEIGHT),
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=kwargs.pop("fg_color", SECONDARY_BUTTON_FG),
            hover_color=kwargs.pop("hover_color", SECONDARY_BUTTON_HOVER),
            text_color=kwargs.pop("text_color", UTILITY_BUTTON_TEXT),
            border_width=kwargs.pop("border_width", 1),
            border_color=kwargs.pop("border_color", LINE_BLUE),
            font=kwargs.pop("font", ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold")),
            **kwargs,
        )

    def _create_utility_button(self, parent, text: str, command, **kwargs):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", LEFT_PANEL_UTILITY_HEIGHT),
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=kwargs.pop("fg_color", UTILITY_BUTTON_FG),
            hover_color=kwargs.pop("hover_color", UTILITY_BUTTON_HOVER),
            text_color=kwargs.pop("text_color", UTILITY_BUTTON_TEXT),
            border_width=kwargs.pop("border_width", 1),
            border_color=kwargs.pop("border_color", LINE_BLUE),
            font=kwargs.pop("font", ctk.CTkFont(size=META_FONT_SIZE, weight="bold")),
            **kwargs,
        )

    def _create_primary_button(self, parent, text: str, command, **kwargs):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=kwargs.pop("height", LEFT_PANEL_PRIMARY_HEIGHT),
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=kwargs.pop("fg_color", ACCENT_BLUE),
            hover_color=kwargs.pop("hover_color", HOVER_BLUE),
            text_color=kwargs.pop("text_color", "white"),
            border_width=kwargs.pop("border_width", 0),
            font=kwargs.pop("font", ctk.CTkFont(size=BUTTON_STRONG_FONT_SIZE, weight="bold")),
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
        frame.grid_rowconfigure(0, weight=1)

        content = ctk.CTkFrame(
            frame,
            fg_color="transparent",
            corner_radius=0,
        )
        content.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        content.grid_columnconfigure(0, weight=1)

        plan_section = ctk.CTkFrame(content, fg_color="transparent")
        plan_section.grid(row=0, column=0, sticky="ew", padx=LEFT_PANEL_OUTER_PAD, pady=(LEFT_PANEL_OUTER_PAD, LEFT_PANEL_SECTION_GAP))
        plan_section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            plan_section,
            text="Saptamana",
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=PANEL_HEADER_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            plan_section,
            textvariable=self.week_var,
            text_color=MUTED_TEXT,
            justify="left",
            font=ctk.CTkFont(size=BODY_FONT_SIZE),
        ).grid(row=1, column=0, sticky="w", pady=(2, LEFT_PANEL_SECTION_INNER_GAP + 1))

        week_nav = ctk.CTkFrame(plan_section, fg_color="transparent")
        week_nav.grid(row=2, column=0, sticky="ew", pady=(0, LEFT_PANEL_SECTION_INNER_GAP + 2))
        week_nav.grid_columnconfigure((0, 1, 2), weight=1)
        self._create_utility_button(
            week_nav,
            "<",
            lambda: self.shift_week(-1),
            width=42,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._create_secondary_button(
            week_nav,
            "Sapt. curenta",
            self.go_to_current_week,
            height=LEFT_PANEL_UTILITY_HEIGHT,
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=1, sticky="ew", padx=4)
        self._create_utility_button(
            week_nav,
            ">",
            lambda: self.shift_week(1),
            width=42,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self._create_primary_button(
            plan_section,
            "Salveaza",
            self.save_week,
            font=ctk.CTkFont(size=BUTTON_STRONG_FONT_SIZE, weight="bold"),
        ).grid(row=3, column=0, sticky="ew")

        action_row = ctk.CTkFrame(plan_section, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        action_row.grid_columnconfigure(0, weight=1)
        self._dirty_indicator = ctk.CTkLabel(
            action_row,
            text="",
            text_color="#9B241A",
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        )
        self._dirty_indicator.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            plan_section,
            textvariable=self._last_saved_var,
            text_color=MUTED_TEXT,
            font=ctk.CTkFont(size=META_FONT_SIZE),
        ).grid(row=5, column=0, sticky="w", pady=(2, 0))

        nav_section = ctk.CTkFrame(content, fg_color="transparent")
        nav_section.grid(row=1, column=0, sticky="ew", padx=LEFT_PANEL_OUTER_PAD, pady=(0, LEFT_PANEL_SECTION_GAP))
        nav_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(nav_section, "NAVIGATION").grid(row=0, column=0, sticky="w", pady=(0, LEFT_PANEL_SECTION_INNER_GAP))
        self._create_secondary_button(nav_section, "Calendar", self.pick_week).grid(row=1, column=0, sticky="ew", pady=(0, LEFT_PANEL_SECTION_INNER_GAP))
        ctk.CTkLabel(
            nav_section,
            text="Istoric",
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=SECTION_TITLE_FONT_SIZE, weight="bold"),
        ).grid(row=2, column=0, sticky="w", pady=(2, 5))
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
            height=LEFT_PANEL_SECONDARY_HEIGHT,
            corner_radius=10,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE),
            dropdown_font=ctk.CTkFont(size=BUTTON_FONT_SIZE),
        )
        self.history_menu.grid(row=3, column=0, sticky="ew", pady=(0, LEFT_PANEL_SECTION_INNER_GAP))

        self._lock_button = ctk.CTkButton(
            nav_section,
            text="Saptamana deschisa",
            command=self.lock_week_toggle,
            height=LEFT_PANEL_UTILITY_HEIGHT,
            corner_radius=10,
            fg_color="#145C32",
            hover_color="#0F4A28",
            text_color="white",
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        )
        self._lock_button.grid(row=4, column=0, sticky="ew", pady=(LEFT_PANEL_SECTION_INNER_GAP, 0))
        ctk.CTkLabel(
            nav_section,
            textvariable=self._lock_state_var,
            text_color=("#8A1F17", "#FFB3AD"),
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(5, 2))
        self._publish_button = self._create_primary_button(
            nav_section,
            "PUBLICA PE ECRANE",
            self.publish_to_tv,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        )
        self._publish_button.grid(row=6, column=0, sticky="ew", pady=(LEFT_PANEL_SECTION_INNER_GAP, 0))

        self._export_pdf_button = self._create_primary_button(
            nav_section,
            "Export PDF",
            self.export_pdf_dialog,
            height=LEFT_PANEL_PRIMARY_HEIGHT,
        )
        self._export_pdf_button.grid(row=7, column=0, sticky="ew", pady=(6, 0))

        self._export_excel_button = self._create_primary_button(
            nav_section,
            "Export Excel",
            self.export_excel_dialog,
            height=LEFT_PANEL_PRIMARY_HEIGHT,
        )
        self._export_excel_button.grid(row=8, column=0, sticky="ew", pady=(6, 0))

        settings_section = ctk.CTkFrame(content, fg_color="transparent")
        settings_section.grid(row=2, column=0, sticky="ew", padx=LEFT_PANEL_OUTER_PAD, pady=(42, LEFT_PANEL_OUTER_PAD))
        settings_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(settings_section, "SETTINGS").grid(row=0, column=0, sticky="w", pady=(0, LEFT_PANEL_SECTION_INNER_GAP))
        self.theme_switch = ctk.CTkSwitch(
            settings_section,
            text="Dark Mode",
            command=self.toggle_theme,
            onvalue="Dark",
            offvalue="Light",
            progress_color=ACCENT_BLUE,
            button_color="#F7FAFD",
            button_hover_color="#E8F1FB",
            text_color=BODY_TEXT,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE),
        )
        self.theme_switch.grid(row=1, column=0, sticky="w", pady=(0, 0))
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
