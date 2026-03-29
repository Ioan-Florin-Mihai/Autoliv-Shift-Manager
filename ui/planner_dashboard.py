from datetime import date, datetime, timedelta
import tkinter.messagebox as messagebox
import tkinter as tk
from queue import Empty, Queue

import customtkinter as ctk
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from logic.app_logger import log_exception
from logic.app_paths import EXPORT_DIR
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


class PlannerDashboard(ctk.CTkFrame):
    def __init__(self, master, remote_service: RemoteControlService):
        super().__init__(master, corner_radius=0)
        self.remote_service = remote_service
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
        self.ui_state_store.save_last_selected_date(self.selected_date)

        self._build_ui()
        self.refresh_all()
        self.remote_checker.start()
        self.after(1000, self.process_remote_events)

    def current_mode_record(self):
        return self.week_record["modes"][self.current_mode]

    def current_cell(self):
        return self.current_mode_record()["schedule"][self.selected_department][self.selected_day][self.selected_shift]

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
            ("Duplica saptamana", self.duplicate_previous_week, ACCENT_BLUE),
            ("Curata weekend", self.clear_weekend, PRIMARY_BLUE),
            ("Curata departament", self.clear_department, ACCENT_BLUE),
        ], start=3):
            ctk.CTkButton(frame, text=label, command=command, fg_color=color, hover_color=HOVER_BLUE, height=34, font=ctk.CTkFont(size=14, weight="bold")).grid(row=row, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkLabel(frame, text="Istoric", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=9, column=0, sticky="w", padx=16, pady=(4, 5))
        self.history_menu = ctk.CTkOptionMenu(frame, variable=self.history_var, values=[""], command=self.load_history_week, fg_color=ACCENT_BLUE, button_color=PRIMARY_BLUE, button_hover_color=HOVER_BLUE, text_color="white", dropdown_fg_color=CARD_WHITE, dropdown_text_color=BODY_TEXT)
        self.history_menu.grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(frame, text="Mod plan", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=11, column=0, sticky="w", padx=16, pady=(0, 5))
        self.mode_buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.mode_buttons_frame.grid(row=12, column=0, sticky="ew", padx=16, pady=(0, 10))
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
        ctk.CTkButton(frame, text="Adauga departament", command=self.add_department, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, height=34, font=ctk.CTkFont(size=14, weight="bold")).grid(row=13, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(frame, text="Departamente", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=17, weight="bold")).grid(row=14, column=0, sticky="w", padx=16, pady=(0, 5))
        self.department_frame = ctk.CTkScrollableFrame(frame, width=230, fg_color=PANEL_BG)
        self.department_frame.grid(row=15, column=0, padx=16, pady=(0, 8), sticky="nsew")
        self.theme_switch = ctk.CTkSwitch(frame, text="Dark Mode", command=self.toggle_theme, onvalue="Dark", offvalue="Light")
        self.theme_switch.grid(row=16, column=0, sticky="w", padx=16, pady=(0, 16))
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()

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
        ctk.CTkLabel(legend, text=" ", fg_color=SELECTED_BG, width=28, height=18, corner_radius=8).pack(side="left", padx=(6, 16))
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
        ctk.CTkButton(actions, text="Adaugă", command=self.add_employee_from_search, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, height=30, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))
        ctk.CTkButton(actions, text="Angajat Nou", command=self.add_new_employee, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, height=30, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, sticky="ew", pady=(0, 4))
        ctk.CTkButton(actions, text="Redenumește", command=self.rename_employee_global, fg_color="#E67E22", hover_color="#D35400", height=30, font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(actions, text="Șterge global", command=self.delete_employee_global, fg_color="#C0392B", hover_color="#A93226", height=30, font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=1, sticky="ew")
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

    def render_grid(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        self.grid_frame.grid_columnconfigure(0, weight=0)
        for idx in range(1, len(DAYS) + 1):
            self.grid_frame.grid_columnconfigure(idx, weight=1)
        ctk.CTkLabel(self.grid_frame, text="Schimb", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        for day_idx, (day_name, _) in enumerate(DAYS, start=1):
            header_fg = WEEKEND_BG if day_name in WEEKEND_DAYS else SOFT_BLUE
            header_text_color = ("#15304B", "#E0E0E0")
            cell = ctk.CTkFrame(self.grid_frame, fg_color=header_fg, corner_radius=10, border_width=1, border_color=LINE_BLUE)
            cell.grid(row=0, column=day_idx, padx=4, pady=4, sticky="ew")
            ctk.CTkLabel(cell, text=format_day_label(start, day_idx - 1), text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=13, weight="bold")).pack(padx=5, pady=5)

        for row_idx, shift in enumerate(SHIFTS, start=1):
            ctk.CTkLabel(self.grid_frame, text=shift, text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=row_idx, column=0, padx=6, pady=6, sticky="nw")
            for day_idx, (day_name, _) in enumerate(DAYS, start=1):
                employees = self.current_mode_record()["schedule"][self.selected_department][day_name][shift]["employees"]
                is_selected = self.selected_day == day_name and self.selected_shift == shift
                is_weekend = day_name in WEEKEND_DAYS
                fg = SELECTED_BG if is_selected else WEEKEND_BG if is_weekend else GRID_CELL_BG
                border_active = 2 if is_selected else 1
                border_color_active = PRIMARY_BLUE if is_selected else LINE_BLUE

                if employees:
                    button_text = "\n".join(employees)
                    cell_font = ctk.CTkFont(size=14, weight="bold")
                    cell_text_color = ("#15304B", "#E8E8E8")
                    cell_anchor = "nw"
                else:
                    button_text = "+ adaugare"
                    cell_font = ctk.CTkFont(size=12)
                    cell_text_color = ("#6B8EAE", "#5A7A9A")
                    cell_anchor = "center"

                ctk.CTkButton(
                    self.grid_frame,
                    text=button_text,
                    width=150,
                    height=130,
                    corner_radius=16,
                    fg_color=fg,
                    hover_color=HOVER_BLUE,
                    border_width=border_active,
                    border_color=border_color_active,
                    text_color=cell_text_color,
                    font=cell_font,
                    anchor=cell_anchor,
                    command=lambda d=day_name, s=shift: self.select_cell(d, s),
                ).grid(row=row_idx, column=day_idx, padx=5, pady=5, sticky="nsew")

    def _select_week(self, selected_date: date):
        self.selected_date = selected_date
        self.ui_state_store.save_last_selected_date(self.selected_date)
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
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

    def render_assignment_panel(self):
        for widget in self.assignment_frame.winfo_children():
            widget.destroy()
        employees = self.current_cell()["employees"]
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
            row = ctk.CTkFrame(self.assignment_frame, fg_color=CARD_WHITE, border_width=1, border_color=LINE_BLUE)
            row.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(row, text=employee, text_color=BODY_TEXT, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=8, pady=8)
            ctk.CTkButton(row, text="Sus", width=42, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, command=lambda e=employee: self.reorder_employee(e, -1)).pack(side="right", padx=(4, 8), pady=6)
            ctk.CTkButton(row, text="Jos", width=42, fg_color=ACCENT_BLUE, hover_color=HOVER_BLUE, command=lambda e=employee: self.reorder_employee(e, 1)).pack(side="right", padx=4, pady=6)
            ctk.CTkButton(row, text="Mutare", width=62, fg_color=PRIMARY_BLUE, hover_color=HOVER_BLUE, command=lambda e=employee: self.move_employee_to_shift(e)).pack(side="right", padx=4, pady=6)
            ctk.CTkButton(row, text="Sterge", width=58, fg_color="#C0392B", hover_color="#A93226", command=lambda e=employee: self.remove_employee(e)).pack(side="right", padx=4, pady=6)

    def refresh_suggestions(self):
        for widget in self.suggestion_frame.winfo_children():
            widget.destroy()
        suggestions = self.employee_store.search(self.employee_search_var.get())
        if not suggestions:
            ctk.CTkLabel(self.suggestion_frame, text="Nicio sugestie.", text_color=MUTED_TEXT).pack(anchor="w", padx=8, pady=8)
            return
        for employee in suggestions:
            ctk.CTkButton(self.suggestion_frame, text=employee, anchor="w", height=34, fg_color=SUGGESTION_BG, text_color=("#15304B", "#E8E8E8"), hover_color=ACCENT_BLUE, command=lambda e=employee: self.add_employee_to_selected_cell(e)).pack(fill="x", padx=4, pady=4)

    def select_department(self, department):
        self.selected_department = department
        self.refresh_all()

    def select_cell(self, day_name: str, shift: str):
        self.selected_day = day_name
        self.selected_shift = shift
        self.refresh_all()

    def change_mode(self, selected_mode):
        self.current_mode = selected_mode
        self.selected_department = self.current_mode_record()["departments"][0]
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
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
        self.refresh_all()

    def _on_search_change(self, _event=None):
        self.refresh_suggestions()

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
        self.current_cell()["employees"].append(employee)
        self.employee_search_var.set("")
        self.show_inline_message(f"{employee} adăugat.")
        self.refresh_all()

    def toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)

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
            self.employee_search_var.set(new_name)
            self.refresh_suggestions()
            self.show_inline_message(f"Angajatul a fost redenumit în '{new_name}'.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)
            
    def remove_employee(self, employee: str):
        self.current_cell()["employees"] = [item for item in self.current_cell()["employees"] if item.casefold() != employee.casefold()]
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
        self.selected_department = department
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
            self.refresh_all()
            self.show_inline_message("Săptămâna anterioară a fost duplicată cu succes.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

    def clear_weekend(self):
        self.store.clear_weekend(self.week_record, self.current_mode)
        self.refresh_all()
        self.show_inline_message(f"Weekend curățat pentru {self.current_mode}.")

    def clear_department(self):
        if not messagebox.askyesno("Confirmare", f"Sterg toate alocarile din {self.selected_department}?"):
            return
        self.store.clear_department(self.week_record, self.current_mode, self.selected_department)
        self.refresh_all()
        self.show_inline_message(f"Departamentul {self.selected_department} a fost golit.")

    def save_week(self):
        try:
            self.store.update_week(self.week_record)
            self.refresh_history()
            self.show_inline_message(f"Săptămâna salvată.")
        except Exception as exc:
            log_exception("save_week", exc)
            self.show_inline_message("A apărut o eroare la salvare.", is_error=True)

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
        try:
            self._export_mode()
        except Exception as exc:
            log_exception("export_excel", exc)
            messagebox.showerror("Eroare export", str(exc))

    def _export_mode(self):
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        week_start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        filename = f"{self.current_mode.lower()}_{week_start.isoformat()}_{self.week_record['week_label'].replace(' ', '_')}.xlsx"
        export_path = EXPORT_DIR / filename
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = self.current_mode
        sheet.sheet_view.showGridLines = False
        sheet.page_setup.orientation = "landscape"
        if hasattr(sheet, "PAPERSIZE_A3"):
            sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        thin = Side(style="thin", color="666666")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        centered = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_aligned = Alignment(horizontal="left", vertical="top", wrap_text=True)
        vertical = Alignment(horizontal="center", vertical="center", text_rotation=90, wrap_text=True)

        sheet.merge_cells("A1:I2")
        sheet["A1"] = f"Planificare {self.current_mode.lower()} : {self.week_record['week_label']}"
        sheet["A1"].fill = PatternFill("solid", fgColor="4F81BD")
        sheet["A1"].font = Font(color="FFFFFF", bold=True, size=18)
        sheet["A1"].alignment = centered
        sheet.merge_cells("J1:J2")
        sheet["J1"] = "Autoliv"
        sheet["J1"].fill = PatternFill("solid", fgColor="4F81BD")
        sheet["J1"].font = Font(color="FFFFFF", bold=True, size=12)
        sheet["J1"].alignment = centered
        if LOGO_PATH.exists():
            try:
                image = XLImage(str(LOGO_PATH))
                image.width = 120
                image.height = 38
                sheet.add_image(image, "A1")
            except Exception:
                pass
        widths = {1: 20, 2: 10, 3: 17, 4: 17, 5: 17, 6: 17, 7: 17, 8: 17, 9: 17, 10: 11}
        for col, width in widths.items():
            sheet.column_dimensions[get_column_letter(col)].width = width

        current_row = 4
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        mode_record = self.current_mode_record()
        for department in mode_record["departments"]:
            schedule = mode_record["schedule"][department]
            sheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row + 3, end_column=1)
            dep = sheet.cell(current_row, 1)
            dep.value = department
            dep.fill = PatternFill("solid", fgColor=DEPARTMENT_COLORS.get(department, "D9A35F"))
            dep.font = Font(bold=True)
            dep.alignment = vertical
            dep.border = border
            h = sheet.cell(current_row, 2)
            h.value = "Schimbul"
            h.font = Font(bold=True)
            h.fill = PatternFill("solid", fgColor="F2F2F2")
            h.alignment = centered
            h.border = border
            for offset, (day_name, _) in enumerate(DAYS, start=3):
                cell = sheet.cell(current_row, offset)
                current_day = start + timedelta(days=offset - 3)
                cell.value = f"{day_name}\n{current_day.strftime('%d-%b-%y')}"
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="F2F2F2" if day_name not in WEEKEND_DAYS else "FCE4D6")
                cell.alignment = centered
                cell.border = border
            for shift_index, shift in enumerate(SHIFTS, start=1):
                row = current_row + shift_index
                sheet.row_dimensions[row].height = 40
                shift_cell = sheet.cell(row, 2)
                shift_cell.value = shift
                shift_cell.font = Font(bold=True)
                shift_cell.alignment = centered
                shift_cell.fill = PatternFill("solid", fgColor="FAFAFA")
                shift_cell.border = border
                for offset, (day_name, _) in enumerate(DAYS, start=3):
                    value_cell = sheet.cell(row, offset)
                    cell_employees = schedule[day_name][shift]["employees"]
                    value_cell.value = "\n".join(cell_employees)
                    value_cell.alignment = left_aligned
                    value_cell.border = border
                    if cell_employees:
                        value_cell.font = Font(bold=True, size=11)
                    if day_name in WEEKEND_DAYS:
                        value_cell.fill = PatternFill("solid", fgColor="FFF7ED")
            sheet.row_dimensions[current_row].height = 46
            current_row += 5
        sheet.freeze_panes = "C5"
        workbook.save(export_path)
        self.status_var.set(f"Export {self.current_mode} realizat: {filename}")
        messagebox.showinfo("Export finalizat", f"Fisierul a fost salvat in:\n{export_path}")

    def process_remote_events(self):
        if self._closing or not self.winfo_exists():
            return
        latest = None
        try:
            while True:
                latest = self.events.get_nowait()
        except Empty:
            pass
        if latest and latest["action"] == "block":
            messagebox.showerror("Aplicatie oprita", latest["message"])
            self.destroy()
            self.winfo_toplevel().destroy()
            return
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