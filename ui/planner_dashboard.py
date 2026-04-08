from copy import deepcopy
from datetime import date, datetime, timedelta
import tkinter.messagebox as messagebox
import tkinter as tk
import threading
from queue import Empty, Queue

import customtkinter as ctk
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from logic.app_logger import log_exception
from logic.app_paths import EXPORT_DIR
from logic.excel_exporter import ExcelExporter
from logic.employee_store import EmployeeStore
from logic.remote_control import RemoteChecker, RemoteControlService
from logic.schedule_store import DAYS, DAY_NAMES, SHIFTS, TEMPLATES, WEEKEND_DAYS, DEPARTMENT_COLORS, ScheduleStore, format_day_label
from logic.ui_state_store import UIStateStore
from ui.common_ui import BG_WHITE, BODY_TEXT, CARD_WHITE, DatePickerDialog, ENTRY_BG, LINE_BLUE, LOGO_PATH, MUTED_TEXT, PANEL_BG, PRIMARY_BLUE


ACCENT_BLUE = "#0067C8"
SOFT_BLUE = "#DCEBFA"
WEEKEND_BG = ("#FFE9CC", "#4A3A28")
SELECTED_BG = ("#B9D8FF", "#1A3A5C")
GRID_CELL_BG = ("#FFFFFF", "#2A2A2A")
SUGGESTION_BG = ("#D9E6F5", "#1E3A5F")
HOVER_BLUE = "#2E7FD2"
CELL_MIN_HEIGHT = 104
GRID_BORDER_LIGHT = "#D0D7E2"
GRID_BORDER_DARK = "#4A5C70"
GRID_HOVER_LIGHT = "#9EB6CF"
GRID_HOVER_DARK = "#6A7F97"
HOURS_COLOR_MAP = {"8h": "#1A1A1A", "12h": "#C0392B"}
BADGE_WIDTH = 28
BADGE_HEIGHT = 28
GRID_NAME_MAX_CHARS = 16
PANEL_NAME_MAX_CHARS = 28
VISIBLE_EMPLOYEE_ROWS = 4
EMPLOYEE_ROW_HEIGHT = 26
EMPLOYEE_ROW_PADY = 2
EMPLOYEE_NAME_TEXT = ("#15304B", "#F4F7FB")


class HoverTooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        self.widget.bind("<Enter>", self._show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            bg="#111827",
            fg="white",
            padx=8,
            pady=4,
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9, "normal"),
        )
        label.pack()

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# Paleta de culori disponibile pentru marcare manuala angajati
# Format: (eticheta, culoare_hex, culoare_text_pe_fundal_alb)
EMPLOYEE_COLOR_PALETTE = [
    ("8h",  "#1A1A1A", "#1A1A1A"),   # Negru — 8 ore
    ("12h", "#7B3FC4", "#7B3FC4"),   # Violet — 12 ore
    ("R",   "#C0392B", "#C0392B"),   # Rosu
    ("V",   "#27AE60", "#27AE60"),   # Verde
    ("P",   "#E67E22", "#E67E22"),   # Portocaliu
    ("AL",  "#2471A3", "#2471A3"),   # Albastru inchis
    ("-",   None,      None),         # Reset culoare
]


class PlannerDashboard(ctk.CTkFrame):
    def __init__(self, master, remote_service: RemoteControlService, username: str = ""):
        super().__init__(master, corner_radius=0)
        self.remote_service = remote_service
        self._username = username          # utilizatorul autentificat curent
        self.store = ScheduleStore()
        self.ui_state_store = UIStateStore()
        self.employee_store = EmployeeStore()
        self.events = Queue()
        self.remote_checker = RemoteChecker(remote_service, self.events)

        self.selected_date = self.ui_state_store.resolve_startup_date()
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.current_mode = "Magazie"
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self.status_var = ctk.StringVar(value="Planner pregatit.")
        self.week_var = ctk.StringVar()
        self.mode_var = ctk.StringVar(value=self.current_mode)
        self.employee_search_var = ctk.StringVar()
        self.history_var = ctk.StringVar(value="")
        self._closing = False
        self._dirty = False                        # modificari nesalvate
        self._grid_cell_frames: dict = {}          # cache {(day, shift): CTkFrame}
        self._grid_cell_canvases: dict = {}        # cache {(day, shift): tk.Canvas}
        self.ui_state_store.save_last_selected_date(self.selected_date)

        self._build_ui()
        self.refresh_all()
        self.remote_checker.start()
        self.after(1000, self.process_remote_events)

    def current_mode_record(self):
        return self.week_record["modes"][self.current_mode]

    def current_cell(self):
        return self.current_mode_record()["schedule"][self.selected_department][self.selected_day][self.selected_shift]

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

    def _visible_cell_content_height(self) -> int:
        row_height = EMPLOYEE_ROW_HEIGHT + EMPLOYEE_ROW_PADY * 2
        return min(CELL_MIN_HEIGHT - 8, VISIBLE_EMPLOYEE_ROWS * row_height + 6)

    def _create_hours_badge(self, parent, colors: dict, employee: str):
        hours_label = self._hours_for_employee(colors, employee)
        badge_color = self._lookup_color(colors or {}, employee) or HOURS_COLOR_MAP[hours_label]
        badge = ctk.CTkLabel(
            parent,
            text=self._hours_badge_value(colors, employee),
            width=BADGE_WIDTH,
            height=BADGE_HEIGHT,
            corner_radius=14,
            fg_color=badge_color,
            text_color="white",
            font=ctk.CTkFont(size=9, weight="bold"),
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
        selected = "#8EB8E5" if is_dark else PRIMARY_BLUE
        return normal, hover, selected

    def _apply_cell_frame_style(self, day_name: str, shift: str, hover: bool = False):
        frame = self._grid_cell_frames.get((day_name, shift))
        if not frame or not frame.winfo_exists():
            return
        normal_border, hover_border, selected_border = self._grid_border_theme()
        is_selected = self.selected_day == day_name and self.selected_shift == shift
        is_weekend = day_name in WEEKEND_DAYS
        if is_selected:
            fg_color = SELECTED_BG
            border_color = selected_border
        elif is_weekend:
            fg_color = WEEKEND_BG
            border_color = hover_border if hover else normal_border
        else:
            fg_color = GRID_CELL_BG
            border_color = hover_border if hover else normal_border
        frame.configure(fg_color=fg_color, border_width=2, border_color=border_color)
        canvas = self._grid_cell_canvases.get((day_name, shift))
        if canvas:
            canvas.configure(bg=self._resolve_theme_color(fg_color))

    def _build_ui(self):
        self.pack(fill="both", expand=True)
        self.configure(fg_color=BG_WHITE)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self._build_left()
        self._build_center()
        self._build_right()

    def _build_left(self):
        frame = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(15, weight=1)
        ctk.CTkLabel(frame, text="Saptamana", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=21, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(frame, textvariable=self.week_var, text_color=MUTED_TEXT, justify="left").grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        week_nav = ctk.CTkFrame(frame, fg_color="transparent")
        week_nav.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        week_nav.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(week_nav, text="<", command=lambda: self.shift_week(-1), height=30, width=44, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(week_nav, text="Sapt. curenta", command=self.go_to_current_week, height=30, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(week_nav, text=">", command=lambda: self.shift_week(1), height=30, width=44, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        for row, (label, command, color) in enumerate([
            ("Calendar", self.pick_week, PRIMARY_BLUE),
            ("Salveaza", self.save_week, ACCENT_BLUE),
            ("Export A3", self.export_excel, PRIMARY_BLUE),
        ], start=3):
            ctk.CTkButton(frame, text=label, command=command, fg_color=color, hover_color=HOVER_BLUE, height=34, font=ctk.CTkFont(size=14, weight="bold")).grid(row=row, column=0, sticky="ew", padx=16, pady=4)

        # ── Sectiunea Imprimanta ──────────────────────────────────────
        ctk.CTkLabel(frame, text="Printare A3", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=6, column=0, sticky="w", padx=16, pady=(8, 4))

        printer_header = ctk.CTkFrame(frame, fg_color="transparent")
        printer_header.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 4))
        printer_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(printer_header, text="Imprimanta:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(printer_header, text="↻ Refresh", width=80, height=24,
                      fg_color=SUGGESTION_BG, text_color=("#15304B", "#E8E8E8"),
                      hover_color=ACCENT_BLUE, font=ctk.CTkFont(size=11, weight="bold"),
                      command=self.load_printers).grid(row=0, column=1, sticky="e")

        self.printer_var = ctk.StringVar(value="")
        self.printer_menu = ctk.CTkOptionMenu(
            frame,
            variable=self.printer_var,
            values=[""],
            fg_color=ACCENT_BLUE,
            button_color=PRIMARY_BLUE,
            button_hover_color=HOVER_BLUE,
            text_color="white",
            dropdown_fg_color=CARD_WHITE,
            dropdown_text_color=BODY_TEXT,
            dynamic_resizing=False,
        )
        self.printer_menu.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 6))

        ctk.CTkButton(
            frame,
            text="🖨  Printează A3",
            command=self.print_excel,
            fg_color="#27AE60",
            hover_color="#1E8449",
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.after(200, self.load_printers)  # incarca imprimantele la pornire
        ctk.CTkLabel(frame, text="Istoric", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=10, column=0, sticky="w", padx=16, pady=(4, 3))
        self.history_menu = ctk.CTkOptionMenu(frame, variable=self.history_var, values=[""], command=self.load_history_week, fg_color=ACCENT_BLUE, button_color=PRIMARY_BLUE, button_hover_color=HOVER_BLUE, text_color="white", dropdown_fg_color=CARD_WHITE, dropdown_text_color=BODY_TEXT)
        self.history_menu.grid(row=11, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(frame, text="Mod plan", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=12, column=0, sticky="w", padx=16, pady=(0, 5))
        self.mode_buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.mode_buttons_frame.grid(row=13, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.mode_buttons_frame.grid_columnconfigure((0, 1), weight=1)
        self.mode_buttons = {}
        for idx, mode_name in enumerate(TEMPLATES):
            button = ctk.CTkButton(
                self.mode_buttons_frame,
                text=mode_name,
                command=lambda value=mode_name: self.change_mode(value),
                height=30,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            button.grid(row=0, column=idx, sticky="ew", padx=(0, 4) if idx == 0 else (4, 0))
            self.mode_buttons[mode_name] = button
        ctk.CTkButton(frame, text="Adauga departament", command=self.add_department, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, height=34, font=ctk.CTkFont(size=14, weight="bold")).grid(row=15, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(frame, text="Departamente", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=16, column=0, sticky="w", padx=16, pady=(0, 5))
        self.department_frame = ctk.CTkScrollableFrame(frame, width=230, fg_color=PANEL_BG)
        self.department_frame.grid(row=17, column=0, padx=16, pady=(0, 8), sticky="nsew")
        frame.grid_rowconfigure(17, weight=1)
        self.theme_switch = ctk.CTkSwitch(frame, text="Dark Mode", command=self.toggle_theme, onvalue="Dark", offvalue="Light")
        self.theme_switch.grid(row=18, column=0, sticky="w", padx=16, pady=(0, 4))
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        ctk.CTkButton(
            frame, text="🔑  Schimba parola",
            command=self._open_change_password,
            fg_color=PANEL_BG, hover_color=LINE_BLUE,
            text_color=PRIMARY_BLUE, height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=19, column=0, sticky="ew", padx=16, pady=(0, 12))

    def _build_center(self):
        frame = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        frame.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)
        self.editor_title = ctk.CTkLabel(frame, text="Editor", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=22, weight="bold"))
        self.editor_title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 5))
        self.status_label = ctk.CTkLabel(frame, textvariable=self.status_var, text_color=BODY_TEXT, anchor="w", justify="left", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.editor_hint = ctk.CTkLabel(
            frame,
            text="Selecteaza o celula din tabel pentru Sch1, Sch2 sau Sch3, apoi adauga angajatul din panoul din dreapta.",
            text_color=MUTED_TEXT,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=13),
        )
        self.editor_hint.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        legend = ctk.CTkFrame(frame, fg_color="transparent")
        legend.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 6))
        ctk.CTkLabel(legend, text="Weekend", text_color=MUTED_TEXT).pack(side="left")
        ctk.CTkLabel(legend, text=" ", fg_color=WEEKEND_BG, width=28, height=18, corner_radius=8).pack(side="left", padx=(6, 16))
        ctk.CTkLabel(legend, text="Selectat", text_color=MUTED_TEXT).pack(side="left")
        ctk.CTkLabel(legend, text=" ", fg_color=SELECTED_BG, width=28, height=18, corner_radius=8).pack(side="left", padx=(6, 0))
        self.grid_frame = ctk.CTkFrame(frame, fg_color=PANEL_BG, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        self.grid_frame.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def _build_right(self):
        frame = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)
        frame.grid_rowconfigure(8, weight=1)
        self.cell_title = ctk.CTkLabel(frame, text="Celula selectata", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=20, weight="bold"))
        self.cell_title.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 5))
        self.cell_meta = ctk.CTkLabel(frame, text="", text_color=MUTED_TEXT, justify="left")
        self.cell_meta.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        ctk.CTkLabel(frame, text="Angajati in celula", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 5))
        self.assignment_frame = ctk.CTkScrollableFrame(frame, width=330, fg_color=PANEL_BG)
        self.assignment_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 10))
        ctk.CTkLabel(frame, text="Cautare angajat", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=4, column=0, sticky="w", padx=16, pady=(0, 5))
        entry = ctk.CTkEntry(frame, textvariable=self.employee_search_var, placeholder_text="Scrie numele angajatului", fg_color=ENTRY_BG, border_width=2, border_color=LINE_BLUE, text_color=BODY_TEXT)
        entry.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 6))
        entry.bind("<KeyRelease>", self._on_search_change)
        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 8))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="Adaugă", command=self.add_employee_from_search, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, height=28, font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))
        ctk.CTkButton(actions, text="Angajat Nou", command=self.add_new_employee, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, height=28, font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=1, sticky="ew", pady=(0, 3))
        ctk.CTkButton(actions, text="Redenumește", command=self.rename_employee_global, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, height=28, font=ctk.CTkFont(size=10, weight="bold")).grid(row=1, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(actions, text="Șterge global", command=self.delete_employee_global, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, height=28, font=ctk.CTkFont(size=10, weight="bold")).grid(row=1, column=1, sticky="ew")
        ctk.CTkLabel(frame, text="Sugestii rapide", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=7, column=0, sticky="w", padx=16, pady=(0, 5))
        self.suggestion_frame = ctk.CTkScrollableFrame(frame, width=330, fg_color=PANEL_BG)
        self.suggestion_frame.grid(row=8, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def show_inline_message(self, message: str, is_error=False):
        self.status_var.set(message)
        color = "#C0392B" if is_error else ("#27AE60", "#2ECC71")
        try:
            self.status_label.configure(text_color=color)
        except Exception:
            pass
            
        def reset_color():
            if self.winfo_exists():
                try:
                    self.status_label.configure(text_color=BODY_TEXT)
                except Exception:
                    pass
        self.after(3000, reset_color)

    def refresh_all(self):
        self._refresh_current_week_if_needed()
        self.refresh_week_display()
        self.refresh_history()
        self.render_mode_buttons()
        self.render_department_buttons()
        self.render_grid()
        self.render_assignment_panel()
        self.refresh_suggestions()

    def refresh_week_display(self):
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        end = datetime.strptime(self.week_record["week_end"], "%Y-%m-%d").date()
        self.week_var.set(f"{self.week_record['week_label']}\n{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}")
        self.editor_title.configure(text=f"Editor {self.current_mode}: {self.selected_department}")
        split_names = [name for name in self.current_cell()["employees"] if self._employee_day_count(name) > 1]
        extra = f"\nSplit in zi: {', '.join(split_names)}" if split_names else ""
        self.cell_title.configure(text=f"{self.selected_department} | {self.selected_day} | {self.selected_shift}")
        self.cell_meta.configure(text=f"Mod: {self.current_mode}{extra}")

    def refresh_history(self):
        values = [f"{label} | {key}" for key, label, _ in self.store.get_week_history()] or [""]
        self.history_menu.configure(values=values)
        self.history_var.set(values[0])

    def render_department_buttons(self):
        for widget in self.department_frame.winfo_children():
            widget.destroy()
        for department in self.current_mode_record()["departments"]:
            selected = department == self.selected_department
            dep_text_color = "white" if selected else ("#15304B", "#E8E8E8")
            ctk.CTkButton(self.department_frame, text=department, anchor="w", height=32, fg_color=PRIMARY_BLUE if selected else SUGGESTION_BG, text_color=dep_text_color, hover_color=ACCENT_BLUE, border_width=1 if selected else 0, border_color=LINE_BLUE, font=ctk.CTkFont(size=14, weight="bold" if selected else "normal"), command=lambda dep=department: self.select_department(dep)).pack(fill="x", padx=4, pady=4)

    def render_mode_buttons(self):
        for mode_name, button in self.mode_buttons.items():
            selected = mode_name == self.current_mode
            button.configure(
                fg_color=PRIMARY_BLUE if selected else "#B8C2CC",
                hover_color=ACCENT_BLUE if selected else "#9EAAB6",
                text_color="white",
            )

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
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self._grid_cell_frames = {}   # reseteaza cache-ul la rebuild complet
        self._grid_cell_canvases = {}
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        self.grid_frame.grid_columnconfigure(0, weight=0)
        self.grid_frame.grid_rowconfigure(0, weight=0, minsize=42)
        for idx in range(1, len(DAYS) + 1):
            self.grid_frame.grid_columnconfigure(idx, weight=1)
        ctk.CTkLabel(self.grid_frame, text="Schimb", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        for day_idx, (day_name, _) in enumerate(DAYS, start=1):
            header_fg = WEEKEND_BG if day_name in WEEKEND_DAYS else SOFT_BLUE
            cell = ctk.CTkFrame(self.grid_frame, fg_color=header_fg, corner_radius=10, border_width=1, border_color=LINE_BLUE)
            cell.grid(row=0, column=day_idx, padx=4, pady=4, sticky="ew")
            ctk.CTkLabel(cell, text=format_day_label(start, day_idx - 1), text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=13, weight="bold")).pack(padx=5, pady=5)

        for row_idx, shift in enumerate(SHIFTS, start=1):
            self.grid_frame.grid_rowconfigure(row_idx, weight=0, minsize=CELL_MIN_HEIGHT + 10)
            ctk.CTkLabel(self.grid_frame, text=shift, text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=row_idx, column=0, padx=6, pady=6, sticky="nw")
            for day_idx, (day_name, _) in enumerate(DAYS, start=1):
                cell_data  = self.current_mode_record()["schedule"][self.selected_department][day_name][shift]
                employees  = cell_data.get("employees", [])
                cell_colors = cell_data.get("colors", {})
                normal_border, _hover_border, selected_border = self._grid_border_theme()
                is_selected = self.selected_day == day_name and self.selected_shift == shift
                is_weekend = day_name in WEEKEND_DAYS
                cell_bg = SELECTED_BG if is_selected else (WEEKEND_BG if is_weekend else GRID_CELL_BG)
                border_color_active = selected_border if is_selected else normal_border

                # Celula — frame clickabil
                cell_frame = ctk.CTkFrame(
                    self.grid_frame,
                    fg_color=cell_bg,
                    corner_radius=14,
                    border_width=2,
                    border_color=border_color_active,
                    width=150,
                    height=CELL_MIN_HEIGHT,
                )
                cell_frame.grid(row=row_idx, column=day_idx, padx=5, pady=5, sticky="nsew")
                cell_frame.grid_propagate(False)
                cell_frame.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                cell_frame.bind("<Enter>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=True))
                cell_frame.bind("<Leave>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=False))
                # Stocam referinta pentru update rapid la selectie
                self._grid_cell_frames[(day_name, shift)] = cell_frame

                canvas_height = self._visible_cell_content_height()
                content_canvas = tk.Canvas(
                    cell_frame,
                    highlightthickness=0,
                    bd=0,
                    relief="flat",
                    bg=self._resolve_theme_color(cell_bg),
                )
                content_canvas.place(x=4, y=4, relwidth=1, width=-8, height=canvas_height)
                self._grid_cell_canvases[(day_name, shift)] = content_canvas

                if len(employees) > VISIBLE_EMPLOYEE_ROWS:
                    scrollbar = ctk.CTkScrollbar(cell_frame, orientation="vertical", command=content_canvas.yview, width=8)
                    scrollbar.place(relx=1.0, x=-4, y=6, anchor="ne", height=canvas_height - 4)
                    content_canvas.configure(yscrollcommand=scrollbar.set)
                    content_canvas.place_configure(width=-16)

                content_frame = ctk.CTkFrame(content_canvas, fg_color="transparent")
                content_window = content_canvas.create_window((0, 0), window=content_frame, anchor="nw")
                content_canvas.bind(
                    "<Configure>",
                    lambda event, canvas=content_canvas, window_id=content_window: canvas.itemconfigure(window_id, width=event.width),
                )
                content_frame.bind(
                    "<Configure>",
                    lambda _event, canvas=content_canvas: canvas.configure(scrollregion=canvas.bbox("all")),
                )
                content_canvas.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                content_frame.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                if employees:
                    for emp in employees:
                        emp_row = ctk.CTkFrame(content_frame, fg_color="transparent")
                        emp_row.pack(fill="x", padx=4, pady=EMPLOYEE_ROW_PADY)
                        emp_row.grid_columnconfigure(1, weight=1)
                        emp_row.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                        badge = self._create_hours_badge(emp_row, cell_colors, emp)
                        badge.grid(row=0, column=0, sticky="w", padx=(0, 8))
                        badge.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                        shown_name = self._display_employee_name(emp, GRID_NAME_MAX_CHARS)

                        lbl = ctk.CTkLabel(
                            emp_row,
                            text=shown_name,
                            text_color=EMPLOYEE_NAME_TEXT,
                            font=ctk.CTkFont(size=13, weight="bold"),
                            anchor="w",
                            justify="left",
                            height=EMPLOYEE_ROW_HEIGHT,
                        )
                        lbl.grid(row=0, column=1, sticky="ew")
                        lbl.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                        self._attach_tooltip_if_truncated(lbl, emp, shown_name)
                else:
                    empty_frame = ctk.CTkFrame(content_frame, fg_color="transparent", height=CELL_MIN_HEIGHT - 8)
                    empty_frame.pack(fill="both", expand=True)
                    empty_frame.pack_propagate(False)
                    add_lbl = ctk.CTkLabel(
                        empty_frame,
                        text="+ adaugare",
                        text_color=("#6B8EAE", "#5A7A9A"),
                        font=ctk.CTkFont(size=12),
                    )
                    add_lbl.pack(expand=True)
                    add_lbl.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))

                self._apply_cell_frame_style(day_name, shift, hover=False)

    def _select_week(self, selected_date: date):
        if self._dirty:
            answer = messagebox.askyesnocancel(
                "Modificări nesalvate",
                "Există modificări nesalvate pentru săptămâna curentă.\nSalvezi înainte de a naviga?",
            )
            if answer is None:   # Cancel — rămânem pe săptămâna curentă
                return
            if answer:           # Yes — salvăm înainte de navigare
                self.save_week()
        self.selected_date = selected_date
        self.ui_state_store.save_last_selected_date(self.selected_date)
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self._grid_cell_frames = {}   # forteaza rebuild complet la noua saptamana
        self.refresh_all()

    def shift_week(self, weeks_delta: int):
        self._select_week(self.selected_date + timedelta(days=7 * weeks_delta))

    def go_to_current_week(self):
        self._select_week(date.today())

    def _refresh_current_week_if_needed(self):
        today = date.today()
        if self.store.get_or_create_week(today)["week_start"] == self.week_record["week_start"]:
            if self.selected_date != today:
                self.selected_date = today

    def set_employee_color(self, employee: str, color):
        """
        Seteaza sau sterge culoarea unui angajat in celula curenta.
        `color` = hex string sau None (pentru reset).
        """
        cell = self.current_cell()
        colors = cell.setdefault("colors", {})
        # Gasim cheia exacta (case-insensitive)
        existing_key = next((k for k in colors if k.casefold() == employee.casefold()), None)
        if color is None:
            if existing_key:
                del colors[existing_key]
        else:
            key = existing_key or employee
            colors[key] = color
        self._dirty = True
        self.render_grid()
        self.render_assignment_panel()

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
            card.pack(fill="x", padx=4, pady=5)

            # Randul de sus: indicator culoare + nume + butoane actiune
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=6, pady=(6, 2))
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
            ctk.CTkButton(actions, text="Sus", width=40, height=26, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=11), command=lambda e=employee: self.reorder_employee(e, -1)).pack(side="left", padx=(0, 3))
            ctk.CTkButton(actions, text="Jos", width=40, height=26, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=11), command=lambda e=employee: self.reorder_employee(e, 1)).pack(side="left", padx=3)
            ctk.CTkButton(actions, text="Mut", width=40, height=26, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=11), command=lambda e=employee: self.move_employee_to_shift(e)).pack(side="left", padx=3)
            ctk.CTkButton(actions, text="✕", width=28, height=26, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, font=ctk.CTkFont(size=12), command=lambda e=employee: self.remove_employee(e)).pack(side="left", padx=(3, 0))

            # Randul de jos: selector ore (comportament radio)
            palette_row = ctk.CTkFrame(card, fg_color="transparent")
            palette_row.pack(fill="x", padx=6, pady=(2, 6))
            ctk.CTkLabel(palette_row, text="Program:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
            for label in ("8h", "12h"):
                is_active = hours_label == label
                bg = HOURS_COLOR_MAP[label]
                ctk.CTkButton(
                    palette_row,
                    text=label,
                    width=46,
                    height=24,
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
        for employee in suggestions:
            ctk.CTkButton(
                self.suggestion_frame,
                text=employee,
                anchor="w",
                height=34,
                fg_color=SUGGESTION_BG,
                text_color=("#15304B", "#E8E8E8"),
                hover_color=ACCENT_BLUE,
                command=lambda e=employee: self.add_employee_to_selected_cell(e),
            ).pack(fill="x", padx=4, pady=4)

    def select_department(self, department):
        self.selected_department = department
        self._grid_cell_frames = {}   # departament nou = grid trebuie reconstruit
        self.refresh_all()

    def select_cell(self, day_name: str, shift: str):
        old_day, old_shift = self.selected_day, self.selected_shift
        self.selected_day = day_name
        self.selected_shift = shift
        # Fast path: actualizeaza doar highlight-ul + panoul dreapta (fara rebuild grid)
        self._update_cell_highlight(old_day, old_shift)
        self.render_assignment_panel()
        self.refresh_week_display()

    def _update_cell_highlight(self, old_day: str, old_shift: str):
        """Actualizeaza culoarea de fundal a celulei selectate/deselectate fara rebuild."""
        if not self._grid_cell_frames:
            self.render_grid()
            return
        self._apply_cell_frame_style(old_day, old_shift, hover=False)
        self._apply_cell_frame_style(self.selected_day, self.selected_shift, hover=False)

    def change_mode(self, selected_mode):
        self.current_mode = selected_mode
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self._grid_cell_frames = {}   # mod nou = grid trebuie reconstruit
        self.refresh_all()

    def load_history_week(self, selected_value):
        if not selected_value or "|" not in selected_value:
            return
        week_key = selected_value.split("|")[-1].strip()
        self.selected_date = datetime.strptime(week_key, "%Y-%m-%d").date()
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self._grid_cell_frames = {}   # saptamana noua = grid trebuie reconstruit
        self.refresh_all()

    def _on_search_change(self, _event=None):
        """Debounce 200 ms: evita refresh la fiecare tasta."""
        if hasattr(self, "_search_debounce_id"):
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(200, self.refresh_suggestions)

    def add_new_employee(self):
        from ui.employee_form import EmployeeRegistrationWindow
        def on_employee_added(full_name):
            try:
                employee = self.employee_store.add_employee(full_name)
                self.employee_search_var.set(employee)
                self.refresh_suggestions()
                self.add_employee_to_selected_cell(employee)
            except ValueError as exc:
                messagebox.showerror("Date invalide", str(exc))

        EmployeeRegistrationWindow(self.winfo_toplevel(), on_employee_added=on_employee_added)

    def add_employee_from_search(self):
        value = self.employee_search_var.get().strip()
        if not value:
            messagebox.showwarning("Lipseste numele", "Introdu sau selecteaza un angajat.")
            return
        matches = self.employee_store.search(value)
        employee = matches[0] if matches and matches[0].casefold() == value.casefold() else self.employee_store.add_employee(value)
        self.add_employee_to_selected_cell(employee)

    def add_employee_to_selected_cell(self, employee: str):
        try:
            self.store.validate_assignment(self.week_record, self.current_mode, self.selected_department, self.selected_day, self.selected_shift, employee)
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)
            return
        cell = self.current_cell()
        cell["employees"].append(employee)
        cell.setdefault("colors", {})[employee] = HOURS_COLOR_MAP["8h"]
        self._dirty = True
        self.employee_search_var.set("")
        self.show_inline_message(f"{employee} adăugat.")
        self.refresh_all()

    def toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)

    def _open_change_password(self):
        """Deschide dialogul de schimbare parola daca exista un user autentificat."""
        from ui.dashboard import ChangePasswordDialog
        if self._username:
            ChangePasswordDialog(self.winfo_toplevel(), self._username)
        else:
            messagebox.showwarning("Indisponibil", "Nu exista un utilizator autentificat.")

    def delete_employee_global(self):
        value = self.employee_search_var.get().strip()
        if not value:
            self.show_inline_message("Scrie angajatul în search înainte de a șterge.", is_error=True)
            return
        confirm = messagebox.askyesno("Confirmare Stergere", f"Esti sigur ca vrei sa stergi angajatul '{value}' din toata baza de date?")
        if not confirm:
            return
            
        success_db = self.employee_store.delete_employee(value)
        try:
            from logic.personnel_manager import PersonnelManager
            pm = PersonnelManager()
            success_pm = pm.delete_record(value)
        except Exception:
            success_pm = False
            
        if success_db or success_pm:
            self.show_inline_message(f"Angajatul '{value}' a fost șters global.")
            self.employee_search_var.set("")
            self.refresh_suggestions()
        else:
            self.show_inline_message(f"Angajatul '{value}' nu a fost găsit în baze de date.", is_error=True)

    def rename_employee_global(self):
        old_val = self.employee_search_var.get().strip()
        if not old_val:
            self.show_inline_message("Scrie angajatul în search înainte de a-l redenumi.", is_error=True)
            return

        dialog = ctk.CTkInputDialog(text=f"Introdu noul nume pentru '{old_val}':", title="Redenumire Angajat")
        new_val = dialog.get_input()
        if not new_val:
            return

        try:
            new_name = self.employee_store.rename_employee(old_val, new_val)
            # Actualizare si in toate saptamanile din planificari (nu doar in lista)
            count = self._rename_in_schedule_store(old_val, new_name)
            # Reload week record actualizat din store
            self.week_record = self.store.get_or_create_week(self.selected_date)
            self._grid_cell_frames = {}   # forteaza rebuild grid
            self.employee_search_var.set(new_name)
            self.refresh_all()
            self.show_inline_message(
                f"Redenumit în '{new_name}'. {count} intrare(i) actualizate în planificări."
            )
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

    def _rename_in_schedule_store(self, old_name: str, new_name: str) -> int:
        """
        Redenumeste angajatul in toate saptamanile/modurile/celulele din store.
        Actualizeaza si cheile din dict-urile de culori.
        Returneaza numarul de intrari modificate.
        """
        count  = 0
        old_cf = old_name.casefold()
        for week_rec in self.store.data.get("weeks", {}).values():
            if not isinstance(week_rec, dict):
                continue
            for mode_rec in week_rec.get("modes", {}).values():
                if not isinstance(mode_rec, dict):
                    continue
                for dept_sched in mode_rec.get("schedule", {}).values():
                    for day_sched in dept_sched.values():
                        for cell in day_sched.values():
                            if not isinstance(cell, dict):
                                continue
                            employees = cell.get("employees", [])
                            for i, emp in enumerate(employees):
                                if emp.casefold() == old_cf:
                                    employees[i] = new_name
                                    count += 1
                            # Actualizeaza si culorile (cheia = nume angajat)
                            colors = cell.get("colors", {})
                            for k in list(colors.keys()):
                                if k.casefold() == old_cf:
                                    colors[new_name] = colors.pop(k)
        if count > 0:
            try:
                self.store.save()
            except Exception as exc:
                log_exception("rename_in_schedule_store_save", exc)
        return count
            
    def remove_employee(self, employee: str):
        self.current_cell()["employees"] = [item for item in self.current_cell()["employees"] if item.casefold() != employee.casefold()]
        self._dirty = True
        self.refresh_all()

    def reorder_employee(self, employee: str, direction: int):
        employees = self.current_cell()["employees"]
        index = next((idx for idx, value in enumerate(employees) if value.casefold() == employee.casefold()), None)
        if index is None:
            return
        target = index + direction
        if target < 0 or target >= len(employees):
            return
        employees[index], employees[target] = employees[target], employees[index]
        self._dirty = True
        self.refresh_all()

    def move_employee_to_shift(self, employee: str):
        candidates = [shift for shift in SHIFTS if shift != self.selected_shift]
        dialog = ctk.CTkInputDialog(text=f"Mutare {employee} in: {', '.join(candidates)}", title="Mutare shift")
        target_shift = dialog.get_input()
        if target_shift is None:
            return
        target_shift = target_shift.strip()
        if target_shift not in candidates:
            messagebox.showwarning("Shift invalid", f"Foloseste: {', '.join(candidates)}")
            return
        try:
            self.store.validate_assignment(self.week_record, self.current_mode, self.selected_department, self.selected_day, target_shift, employee)
        except ValueError as exc:
            messagebox.showwarning("Mutare invalida", str(exc))
            return
        self.remove_employee(employee)
        self.current_mode_record()["schedule"][self.selected_department][self.selected_day][target_shift]["employees"].append(employee)
        self.selected_shift = target_shift
        self._dirty = True
        self.refresh_all()

    def add_department(self):
        dialog = ctk.CTkInputDialog(text="Introdu departamentul nou", title="Departament nou")
        value = dialog.get_input()
        if value is None:
            return
        department = " ".join(value.split()).strip()
        if not department:
            return
        if department in self.current_mode_record()["departments"]:
            messagebox.showwarning("Exista deja", "Departamentul exista deja in modul curent.")
            return
        self.current_mode_record()["departments"].append(department)
        self.current_mode_record()["schedule"][department] = {day: {shift: {"employees": []} for shift in SHIFTS} for day in DAY_NAMES}
        self._dirty = True
        self.selected_department = department
        self.save_week()   # auto-save dupa adaugare departament
        self.refresh_all()

    def pick_week(self):
        dialog = DatePickerDialog(self, self.selected_date)
        self.wait_window(dialog)
        if dialog.selected_date is None:
            return
        self._select_week(dialog.selected_date)

    def duplicate_previous_week(self):
        try:
            self.week_record = self.store.duplicate_previous_week(self.selected_date)
            self._dirty = True
            self.refresh_all()
            self.show_inline_message("Săptămâna anterioară a fost duplicată cu succes.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

    def clear_weekend(self):
        self.store.clear_weekend(self.week_record, self.current_mode)
        self._dirty = True
        self.refresh_all()
        self.show_inline_message(f"Weekend curățat pentru {self.current_mode}.")

    def clear_department(self):
        if not messagebox.askyesno("Confirmare", f"Sterg toate alocarile din {self.selected_department}?"):
            return
        self.store.clear_department(self.week_record, self.current_mode, self.selected_department)
        self._dirty = True
        self.refresh_all()
        self.show_inline_message(f"Departamentul {self.selected_department} a fost golit.")

    def save_week(self):
        try:
            self.store.update_week(self.week_record)
            self._dirty = False
            self.refresh_history()
            self.show_inline_message(f"Săptămâna salvată.")
        except Exception as exc:
            log_exception("save_week", exc)
            self.show_inline_message("A apărut o eroare la salvare.", is_error=True)

    # ── Gestionare imprimante ──────────────────────────────────

    def load_printers(self):
        """Porneste descoperirea imprimantelor in background (non-blocant)."""
        self.printer_var.set("Se incarca...")
        threading.Thread(target=self._discover_printers, daemon=True).start()

    def _discover_printers(self):
        """Rulat in thread background — fara acces la UI."""
        printers = []
        default  = ""
        try:
            import win32print
            printers = [p[2] for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )]
            try:
                default = win32print.GetDefaultPrinter()
            except Exception:
                pass
        except ImportError:
            try:
                import subprocess
                result = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Printer | Select-Object -ExpandProperty Name"],
                    capture_output=True, text=True, timeout=5
                )
                printers = [p.strip() for p in result.stdout.splitlines() if p.strip()]
            except Exception:
                pass
        except Exception:
            pass
        # Actualizare UI — garantat pe main thread
        self.after(0, lambda: self._apply_printers(printers, default))

    def _apply_printers(self, printers: list, default: str):
        """Actualizare UI cu lista de imprimante (rulat pe main thread)."""
        if not printers:
            printers = ["(nicio imprimanta gasita)"]
        self.printer_menu.configure(values=printers)
        if default and default in printers:
            self.printer_var.set(default)
        else:
            self.printer_var.set(printers[0])

    def print_excel(self):
        """
        Salveaza, exporta fisierul xlsx si trimite direct la imprimanta selectata.
        """
        selected_printer = self.printer_var.get()
        if not selected_printer or selected_printer == "(nicio imprimanta gasita)":
            messagebox.showwarning("Imprimanta", "Selecteaza o imprimanta din lista.")
            return

        # 1. Salveaza saptamana
        self.save_week()

        # 2. Exporta fisierul xlsx
        try:
            export_path = self._export_mode()
        except Exception as exc:
            log_exception("print_excel_export", exc)
            messagebox.showerror("Eroare export", str(exc))
            return

        if export_path is None:
            return

        # 3. Trimite la imprimanta
        try:
            import win32api
            win32api.ShellExecute(
                0, "print", str(export_path),
                f'/d:"{selected_printer}"',
                ".", 0
            )
            self.show_inline_message(f"Trimis la: {selected_printer}")
        except ImportError:
            # Fallback: deschide cu handler-ul default si printare sistem
            import subprocess
            try:
                subprocess.Popen(
                    ["powershell", "-Command",
                     f'Start-Process -FilePath "{export_path}" -Verb Print'],
                    shell=False
                )
                self.show_inline_message(f"Printare initiata: {selected_printer}")
            except Exception as exc2:
                log_exception("print_excel_fallback", exc2)
                messagebox.showerror("Eroare printare", str(exc2))
        except Exception as exc:
            log_exception("print_excel", exc)
            messagebox.showerror("Eroare printare", str(exc))

    def _employee_day_count(self, employee: str):
        count = 0
        mode_record = self.current_mode_record()
        for department in mode_record["departments"]:
            for shift in SHIFTS:
                employees = mode_record["schedule"][department][self.selected_day][shift]["employees"]
                if any(item.casefold() == employee.casefold() for item in employees):
                    count += 1
        return count

    def export_excel(self):
        self.save_week()
        self.show_inline_message("Se exporta planificarea, asteata...")
        week_snap = deepcopy(self.week_record)
        mode_snap = self.current_mode
        threading.Thread(
            target=self._export_thread,
            args=(week_snap, mode_snap),
            daemon=True,
        ).start()

    def _export_thread(self, week_record, current_mode):
        """Rulat in background — genereaza Excel fara a bloca UI-ul."""
        try:
            path = self._export_mode(week_record=week_record, current_mode=current_mode)
            self.after(0, lambda p=path: self._on_export_success(p))
        except Exception as exc:
            log_exception("export_excel_thread", exc)
            self.after(0, lambda e=str(exc): messagebox.showerror("Eroare export", e))

    def _on_export_success(self, path):
        """Callback pe main thread dupa export reusit."""
        self.status_var.set(f"Export realizat: {path.name}")
        messagebox.showinfo("Export finalizat", f"Fisierul a fost salvat in:\n{path}")

    def _export_mode(self, week_record=None, current_mode=None):
        """
        Genereaza fisierul Excel A3 pentru modul curent.
        Poate fi apelat din background thread (fara acces la UI).
        Delegheaza catre ExcelExporter pentru separarea logicii de UI.
        """
        return ExcelExporter.export(
            week_record   = week_record  or self.week_record,
            current_mode  = current_mode or self.current_mode,
            logo_path     = LOGO_PATH,
        )

    def process_remote_events(self):
        if self._closing or not self.winfo_exists():
            return
        latest = None
        try:
            while True:
                latest = self.events.get_nowait()
        except Empty:
            pass

        if latest:
            if latest["action"] == "block":
                # Blocare CONFIRMATĂ de administrator — singura cauză de oprire
                messagebox.showerror("Aplicatie oprita", latest["message"])
                self.destroy()
                self.winfo_toplevel().destroy()
                return
            elif latest["action"] == "warn":
                # Probleme de conexiune — doar status bar, app continuă normal
                self.status_var.set(latest["message"])

        try:
            self.after(1000, self.process_remote_events)
        except tk.TclError:
            pass

    def destroy(self):
        if self._closing:
            return
        self._closing = True
        self.remote_checker.stop()
        super().destroy()

    def confirm_close(self) -> bool:
        """Returneaza True daca e sigur sa se inchida (fara modificari sau user a confirmat)."""
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Modificări nesalvate",
            "Există modificări nesalvate.\nSalvezi înainte de a ieși din aplicație?",
        )
        if answer is None:   # Cancel
            return False
        if answer:           # Yes
            self.save_week()
        return True