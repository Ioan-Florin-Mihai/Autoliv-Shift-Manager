import json
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import customtkinter as ctk

from logic.app_config import get_config
from logic.app_logger import log_exception
from logic.app_paths import BASE_DIR, RUNTIME_FILE
from logic.audit_logger import log_event
from logic.employee_store import EmployeeStore
from logic.schedule_store import (
    DAY_NAMES,
    DAYS,
    SHIFTS,
    TEMPLATES,
    ScheduleStore,
)
from logic.ui_state_store import UIStateStore
from ui.common_ui import (
    BG_WHITE,
    BODY_TEXT,
    CARD_WHITE,
    LINE_BLUE,
    MUTED_TEXT,
    PANEL_BG,
    PRIMARY_BLUE,
    DatePickerDialog,
)
from ui.components.constants import (
    BODY_FONT_SIZE,
    BUTTON_FONT_SIZE,
    GRID_INNER_PAD,
    HOURS_COLOR_MAP,
    LEFT_PANEL_WIDTH,
    META_FONT_SIZE,
    OUTER_PAD,
    PANEL_GAP,
    PANEL_HEADER_FONT_SIZE,
    RIGHT_PANEL_WIDTH,
    SECTION_TITLE_FONT_SIZE,
    STATUS_ERROR,
    STATUS_SUCCESS,
    TOPBAR_BG,
)
from ui.components.dialogs import ABSENCE_COLORS, MoveShiftDialog
from ui.components.left_panel import LeftPanelMixin
from ui.components.right_panel import RightPanelMixin
from ui.components.schedule_grid import ScheduleGridMixin


class PlannerDashboard(ScheduleGridMixin, LeftPanelMixin, RightPanelMixin, ctk.CTkFrame):
    def __init__(self, master, username: str = "", user_role: str = "operator"):
        super().__init__(master, corner_radius=0)
        self._username = username          # utilizatorul autentificat curent
        self._user_role = user_role or "operator"
        self._config = get_config()
        self.store = ScheduleStore()
        self.ui_state_store = UIStateStore()
        self.employee_store = EmployeeStore()

        self.selected_date = self.ui_state_store.resolve_startup_date()
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.current_mode = "Magazie"
        self.selected_department = self.current_mode_record()["departments"][0]
        self.department_list: list[str] = []
        self.department_index = 0
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self.status_var = ctk.StringVar(value="Planner pregatit.")
        self.runtime_warning_var = ctk.StringVar(value="")
        self.week_var = ctk.StringVar()
        self.employee_search_var = ctk.StringVar()
        self.history_var = ctk.StringVar(value="")
        self.department_name_var = ctk.StringVar(value=self.selected_department)
        self._closing = False
        self._dirty = False                        # modificari nesalvate
        self._search_entry: ctk.CTkEntry | None = None   # referinta la entry search
        self._last_saved_var = ctk.StringVar(value="")
        self._lock_state_var = ctk.StringVar(value="")
        self._lock_button: ctk.CTkButton | None = None
        self._publish_button: ctk.CTkButton | None = None
        self._export_pdf_button: ctk.CTkButton | None = None
        self._export_excel_button: ctk.CTkButton | None = None
        self._delete_global_button: ctk.CTkButton | None = None
        self._add_button: ctk.CTkButton | None = None
        self._dirty_indicator: ctk.CTkLabel | None = None
        self._busy_cursor_enabled = False
        self._grid_cell_frames: dict = {}          # cache {(day, shift): CTkFrame}
        self._grid_cell_canvases: dict = {}        # cache {(day, shift): tk.Canvas}
        self._cached_tv_status: dict = {           # ultima stare TV fetch-uita async
            "server": "oprit", "tv": "necunoscut", "last_update": "-",
        }
        self._busy_action = False                  # guard pentru actiuni lungi (publish/restore)
        self.ui_state_store.save_last_selected_date(self.selected_date)
        self._sync_department_state()

        self._build_ui()
        self._refresh_after_cell_change()
        self._update_runtime_warning()

    def _current_week_code(self) -> str:
        try:
            week_start = date.fromisoformat(self.week_record.get("week_start", ""))
            iso = week_start.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        except (TypeError, ValueError, AttributeError):
            return "unknown"

    def _is_admin(self) -> bool:
        return self._user_role == "admin"

    def _require_admin(self, action_name: str) -> bool:
        if self._is_admin():
            return True
        self.show_inline_message(f"Doar admin poate executa actiunea: {action_name}.", is_error=True)
        return False

    def _last_backup_text(self) -> str:
        backups = self.store.get_backup_history()
        if not backups:
            return "Niciun backup"
        name, modified = backups[0]
        return f"{name} ({datetime.fromtimestamp(modified).strftime('%d.%m.%Y %H:%M')})"

    def _tv_status_snapshot(self) -> dict:
        port = int(self._config.get("server_port", 8000))
        health_url = f"http://127.0.0.1:{port}/health"
        status = {
            "server": "oprit",
            "tv": "necunoscut",
            "last_update": "-",
        }
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            status["server"] = "activ" if payload.get("status") == "ok" else "eroare"
            last_update_ms = int(payload.get("last_update", 0) or 0)
            if last_update_ms:
                status["last_update"] = datetime.fromtimestamp(last_update_ms / 1000).strftime("%d.%m.%Y %H:%M:%S")
                stale_seconds = int(self._config.get("tv_stale_seconds", 15))
                age_seconds = max(0, (datetime.now().timestamp() * 1000 - last_update_ms) / 1000)
                status["tv"] = "stale" if age_seconds > stale_seconds else "connected"
            elif payload.get("data_loaded"):
                status["tv"] = "connected"
        except (OSError, ValueError, urllib.error.URLError, TimeoutError):
            pass
        return status

    def _fetch_tv_status_async(self, callback) -> None:
        """Ruleaza _tv_status_snapshot() intr-un thread background.
        Apeleaza callback(result) pe main thread prin after()."""
        def _worker():
            result = self._tv_status_snapshot()
            if not self._closing:
                try:
                    self.after(0, lambda: callback(result))
                except (tk.TclError, RuntimeError):
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _update_runtime_warning(self):
        message = ""
        try:
            if RUNTIME_FILE.exists():
                runtime_root = RUNTIME_FILE.read_text(encoding="utf-8").strip()
                if runtime_root and Path(runtime_root).resolve() != BASE_DIR.resolve():
                    message = "TV server ruleaza din alta locatie. Datele NU sunt sincronizate."
        except OSError:
            pass

        # Aplica mesajul din RUNTIME_FILE imediat (citire locala, non-blocanta)
        self.runtime_warning_var.set(message)
        if self.runtime_warning_label is not None:
            if message:
                self.runtime_warning_label.grid()
            else:
                self.runtime_warning_label.grid_remove()

        # Fetch TV status async - nu blocheaza main thread
        def _apply_tv_status(tv_status: dict) -> None:
            if self._closing or not self.winfo_exists():
                return
            tv_base_dir = ""
            current_msg = self.runtime_warning_var.get()
            if not current_msg and tv_base_dir:
                try:
                    if Path(tv_base_dir).resolve() != BASE_DIR.resolve():
                        self.runtime_warning_var.set(
                            "TV server ruleaza din alta locatie. Datele NU sunt sincronizate."
                        )
                        if self.runtime_warning_label is not None:
                            self.runtime_warning_label.grid()
                except OSError:
                    self.runtime_warning_var.set(
                        "TV server ruleaza din alta locatie. Datele NU sunt sincronizate."
                    )
                    if self.runtime_warning_label is not None:
                        self.runtime_warning_label.grid()
            self._cached_tv_status = tv_status

        self._fetch_tv_status_async(_apply_tv_status)

        if not self._closing and self.winfo_exists():
            self.after(10000, self._update_runtime_warning)

    def open_system_status(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Status Sistem")
        dialog.geometry("640x420")
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        content.grid_columnconfigure(1, weight=1)

        last_publish = self.week_record.get("published_at", "Niciodata") or "Niciodata"
        tv_status = self._cached_tv_status
        rows = [
            ("Utilizator activ", f"{self._username or '-'} ({self._user_role})"),
            ("Planner BASE_DIR", str(BASE_DIR)),
            ("Server TV", tv_status["server"]),
            ("TV status", tv_status["tv"]),
            ("Ultima actualizare TV", tv_status["last_update"]),
            ("Ultima publicare", last_publish),
            ("Ultimul backup", self._last_backup_text()),
        ]
        ctk.CTkLabel(content, text="Status Sistem", font=ctk.CTkFont(size=22, weight="bold"), text_color=PRIMARY_BLUE).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))
        for idx, (label, value) in enumerate(rows, start=1):
            ctk.CTkLabel(content, text=label, text_color=MUTED_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(row=idx, column=0, sticky="w", pady=8)
            ctk.CTkLabel(content, text=str(value), text_color=BODY_TEXT, justify="left", wraplength=360).grid(row=idx, column=1, sticky="w", pady=8)

    def restore_backup_dialog(self):
        if self._busy_action:
            return
        if not self._require_admin("restore backup"):
            return
        backups = self.store.get_backup_history()
        if not backups:
            messagebox.showinfo("Backup", "Nu exista backup-uri disponibile.")
            return
        values = [name for name, _ in backups[:30]]
        dialog = ctk.CTkInputDialog(
            text="Introdu numele backup-ului de restaurat:\n\n" + "\n".join(values[:10]),
            title="Restore backup",
        )
        selected = dialog.get_input()
        if not selected:
            return
        if not messagebox.askyesno("Confirmare restore", f"Restauram backup-ul {selected}?\nDraft si live vor fi rescrise."):
            return
        self._busy_action = True
        try:
            if self._publish_button is not None:
                self._publish_button.configure(state="disabled")
            if self._lock_button is not None:
                self._lock_button.configure(state="disabled")
        except tk.TclError:
            pass
        try:
            self.store.restore_backup(selected.strip())
            self.week_record = self.store.get_or_create_week(self.selected_date)
            self._dirty = False
            self.refresh_all()
            self.show_inline_message("Backup restaurat cu succes.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)
        finally:
            self._busy_action = False
            try:
                self._sync_action_states()
                if self._lock_button is not None:
                    self._lock_button.configure(state="normal")
            except tk.TclError:
                pass

    def current_mode_record(self):
        return self.week_record["modes"][self.current_mode]

    def _all_departments(self) -> list[str]:
        ordered_departments: list[str] = []
        for mode_name in TEMPLATES:
            mode_record = self.week_record["modes"].get(mode_name, {})
            for department in mode_record.get("departments", []):
                if department and department not in ordered_departments:
                    ordered_departments.append(department)
        return ordered_departments

    def _mode_for_department(self, department: str) -> str:
        for mode_name in TEMPLATES:
            mode_record = self.week_record["modes"].get(mode_name, {})
            if department in mode_record.get("departments", []):
                return mode_name
        return self.current_mode

    def current_cell(self):
        return self.current_mode_record()["schedule"][self.selected_department][self.selected_day][self.selected_shift]

    def _visible_days(self):
        # Afisam mereu Luni-Duminica. Toggle-urile vechi pentru zile/weekend au fost eliminate.
        return list(DAYS)

    def _sync_department_state(self):
        departments = self._all_departments()
        self.department_list = departments
        if not departments:
            self.selected_department = ""
            self.department_index = -1
            self.department_name_var.set("-")
            return
        if self.selected_department not in departments:
            self.selected_department = departments[0]
        self.current_mode = self._mode_for_department(self.selected_department)
        self.department_index = departments.index(self.selected_department)
        self.department_name_var.set(self.selected_department)

    def _build_ui(self):
        self.pack(fill="both", expand=True)
        self.configure(fg_color=BG_WHITE)
        self.grid_columnconfigure(0, weight=0, minsize=LEFT_PANEL_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=RIGHT_PANEL_WIDTH)
        self.grid_rowconfigure(0, weight=1)

        self._build_left()
        self._build_center()
        self._build_right()

    def _build_center(self):
        frame = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        frame.grid(row=0, column=1, sticky="nsew", padx=(0, PANEL_GAP))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        header_row = ctk.CTkFrame(
            frame,
            fg_color=TOPBAR_BG,
            corner_radius=14,
            border_width=1,
            border_color=LINE_BLUE,
        )
        header_row.grid(row=0, column=0, sticky="ew", padx=OUTER_PAD, pady=(10, 6))
        header_row.grid_columnconfigure(0, weight=1)

        context_header = ctk.CTkFrame(header_row, fg_color="transparent")
        context_header.grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        department_nav = ctk.CTkFrame(context_header, fg_color="transparent")
        department_nav.grid(row=0, column=0, sticky="w")
        department_nav.grid_columnconfigure(1, weight=1)
        self.department_prev_button = self._create_utility_button(
            department_nav,
            "<",
            self.prev_department,
            width=36,
            height=30,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        )
        self.department_prev_button.grid(row=0, column=0, sticky="w")
        self.department_name_label = ctk.CTkLabel(
            department_nav,
            textvariable=self.department_name_var,
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=SECTION_TITLE_FONT_SIZE, weight="bold"),
            anchor="w",
        )
        self.department_name_label.grid(row=0, column=1, sticky="w", padx=10)
        self.department_next_button = self._create_utility_button(
            department_nav,
            ">",
            self.next_department,
            width=36,
            height=30,
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE, weight="bold"),
        )
        self.department_next_button.grid(row=0, column=2, sticky="w")

        self.cell_title = ctk.CTkLabel(
            context_header,
            text="",
            text_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=PANEL_HEADER_FONT_SIZE, weight="bold"),
            anchor="w",
        )
        self.cell_title.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.cell_meta = ctk.CTkLabel(
            context_header,
            text="",
            text_color=MUTED_TEXT,
            justify="left",
            font=ctk.CTkFont(size=META_FONT_SIZE),
        )
        self.cell_meta.grid(row=2, column=0, sticky="w", pady=(2, 0))

        self.runtime_warning_label = ctk.CTkLabel(
            frame,
            textvariable=self.runtime_warning_var,
            fg_color="#FDECEC",
            text_color="#9B241A",
            corner_radius=10,
            anchor="w",
            justify="left",
            padx=12,
            pady=8,
            font=ctk.CTkFont(size=META_FONT_SIZE, weight="bold"),
        )
        self.runtime_warning_label.grid(row=1, column=0, sticky="ew", padx=OUTER_PAD, pady=(0, 8))
        self.runtime_warning_label.grid_remove()

        toolbar_row = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar_row.grid(row=2, column=0, sticky="ew", padx=OUTER_PAD, pady=(0, 6))
        toolbar_row.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(toolbar_row, textvariable=self.status_var, text_color=BODY_TEXT, anchor="w", justify="left", font=ctk.CTkFont(size=BODY_FONT_SIZE, weight="bold"))
        self.status_label.grid(row=0, column=0, sticky="w")
        self.editor_hint = ctk.CTkLabel(
            toolbar_row,
            text="Selecteaza o celula si adauga angajatul din panoul din dreapta.",
            text_color=MUTED_TEXT,
            anchor="e",
            justify="right",
            font=ctk.CTkFont(size=META_FONT_SIZE),
        )
        self.editor_hint.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.grid_shell = ctk.CTkFrame(frame, fg_color=PANEL_BG, corner_radius=16, border_width=1, border_color=LINE_BLUE)
        self.grid_shell.grid(row=3, column=0, sticky="nsew", padx=OUTER_PAD, pady=(0, OUTER_PAD))
        self.grid_shell.grid_columnconfigure(0, weight=1)
        self.grid_shell.grid_rowconfigure(0, weight=1)
        self.grid_shell.grid_rowconfigure(1, weight=0)
        self.grid_frame = ctk.CTkScrollableFrame(
            self.grid_shell,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
            scrollbar_button_color="#9EB6CF",
            scrollbar_button_hover_color="#7F9AB8",
        )
        self.grid_frame.grid(row=0, column=0, sticky="nsew", padx=GRID_INNER_PAD, pady=(GRID_INNER_PAD, 0))

        # Scroll orizontal jos pentru zile (Excel-like). Vertical scrollbar ramane cel existent in dreapta.
        self.grid_hscroll = ctk.CTkScrollbar(self.grid_shell, orientation="horizontal", height=12)
        self.grid_hscroll.grid(row=1, column=0, sticky="ew", padx=GRID_INNER_PAD, pady=(2, GRID_INNER_PAD))

        # Layout intern: coloana din stanga (Schimb) ramane fixa; zilele sunt intr-un canvas scrollabil orizontal.
        self.grid_inner = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
        self.grid_inner.pack(fill="both", expand=True)
        self.grid_inner.grid_columnconfigure(0, weight=0)
        self.grid_inner.grid_columnconfigure(1, weight=1)

        self.grid_left = ctk.CTkFrame(self.grid_inner, fg_color="transparent")
        self.grid_left.grid(row=0, column=0, sticky="ns")

        bg = self._resolve_theme_color(PANEL_BG)
        self.grid_days_canvas = tk.Canvas(self.grid_inner, highlightthickness=0, bd=0, bg=bg)
        self.grid_days_canvas.grid(row=0, column=1, sticky="nsew")
        self.grid_days_frame = tk.Frame(self.grid_days_canvas, bg=bg)
        self._grid_days_window = self.grid_days_canvas.create_window((0, 0), window=self.grid_days_frame, anchor="nw")

        def _on_days_frame_configure(_e=None):
            if self.grid_days_canvas.winfo_exists():
                self.grid_days_canvas.configure(scrollregion=self.grid_days_canvas.bbox("all"))
                # Canvas-ul trebuie sa fie suficient de inalt pentru tot grid-ul.
                # Scroll-ul vertical este facut de CTkScrollableFrame, nu de canvas.
                try:
                    self.grid_days_canvas.configure(height=self.grid_days_frame.winfo_reqheight())
                except tk.TclError:
                    pass

        self.grid_days_frame.bind("<Configure>", _on_days_frame_configure)
        self.grid_days_canvas.configure(xscrollcommand=self.grid_hscroll.set)
        self.grid_hscroll.configure(command=self.grid_days_canvas.xview)

    def show_inline_message(self, message: str, is_error=False):
        self.status_var.set(message)
        color = STATUS_ERROR if is_error else STATUS_SUCCESS
        try:
            self.status_label.configure(text_color=color)
        except tk.TclError:
            pass
            
        def reset_color():
            if self.winfo_exists():
                try:
                    self.status_label.configure(text_color=BODY_TEXT)
                except tk.TclError:
                    pass
        self.after(3000, reset_color)

    def _ensure_week_editable(self) -> bool:
        if self.store.is_week_locked(self.week_record):
            self.show_inline_message(
                "Saptamana este publicata (read-only). Deblocheaza sau publica alta versiune.",
                is_error=True,
            )
            return False
        return True

    def refresh_all(self):
        self._refresh_current_week_if_needed()
        self._sync_department_state()
        self.refresh_week_display()
        self.refresh_history()
        self.render_department_navigation()
        self.render_grid()
        self.render_assignment_panel()
        self.refresh_suggestions()
        self.render_unplanned_warning()
        self._update_dirty_indicator()
        self._refresh_lock_button()
        self._sync_action_states()

    def _refresh_after_cell_change(self) -> None:
        """Refresh minim dupa modificari in celula curenta (fara history/day toggles/nav)."""
        self.refresh_week_display()
        self.render_grid()
        self.render_assignment_panel()
        self.refresh_suggestions()
        self.render_unplanned_warning()
        self._update_dirty_indicator()
        self._sync_action_states()

    def refresh_week_display(self):
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        end = datetime.strptime(self.week_record["week_end"], "%Y-%m-%d").date()
        self.week_var.set(f"{self.week_record['week_label']}\n{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}")
        split_names = [name for name in self.current_cell()["employees"] if self._employee_day_count(name) > 1]
        extra = f"In mai multe zone azi: {', '.join(split_names)}" if split_names else ""
        self.cell_title.configure(text=f"{self.selected_department} | {self.selected_day} | {self.selected_shift}")
        self.cell_meta.configure(text=extra)

    def refresh_history(self):
        values = [f"{label} | {key}" for key, label, _ in self.store.get_week_history()] or [""]
        self.history_menu.configure(values=values)
        self.history_var.set(values[0])

    def render_department_navigation(self):
        self.department_name_var.set(self.selected_department or "-")

    def _select_week(self, selected_date: date):
        if self._dirty:
            answer = messagebox.askyesnocancel(
                "Modificari nesalvate",
                "Exista modificari nesalvate pentru saptamana curenta.\nSalvezi inainte de a naviga?",
            )
            if answer is None:   # Cancel - ramanem pe saptamana curenta
                return
            if answer:           # Yes - salvam inainte de navigare
                self.save_week()
        prev_dept = self.selected_department
        self.selected_date = selected_date
        self.ui_state_store.save_last_selected_date(self.selected_date)
        self.week_record = self.store.get_or_create_week(self.selected_date)
        all_depts = self._all_departments()
        if prev_dept not in all_depts:
            self.selected_department = all_depts[0] if all_depts else ""
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self._grid_cell_frames = {}   # forteaza rebuild complet la noua saptamana
        self._refresh_after_cell_change()

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
        if not self._ensure_week_editable():
            return
        self.store.set_employee_color(
            self.week_record,
            self.current_mode,
            self.selected_department,
            self.selected_day,
            self.selected_shift,
            employee,
            color,
        )
        self._dirty = True
        self.render_grid()
        self.render_assignment_panel()

    def select_department(self, department):
        self.selected_department = department
        self.current_mode = self._mode_for_department(department)
        self._grid_cell_frames = {}   # departament nou = grid trebuie reconstruit
        self.refresh_all()

    def next_department(self):
        self._sync_department_state()
        if not self.department_list:
            return
        self.department_index = (self.department_index + 1) % len(self.department_list)
        self.selected_department = self.department_list[self.department_index]
        self.current_mode = self._mode_for_department(self.selected_department)
        self._grid_cell_frames = {}
        self.refresh_all()

    def prev_department(self):
        self._sync_department_state()
        if not self.department_list:
            return
        self.department_index = (self.department_index - 1) % len(self.department_list)
        self.selected_department = self.department_list[self.department_index]
        self.current_mode = self._mode_for_department(self.selected_department)
        self._grid_cell_frames = {}
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

    def load_history_week(self, selected_value):
        if not selected_value or "|" not in selected_value:
            return
        week_key = selected_value.split("|")[-1].strip()
        prev_dept = self.selected_department
        self.selected_date = datetime.strptime(week_key, "%Y-%m-%d").date()
        self.week_record = self.store.get_or_create_week(self.selected_date)
        all_depts = self._all_departments()
        if prev_dept not in all_depts:
            self.selected_department = all_depts[0] if all_depts else ""
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self._grid_cell_frames = {}   # saptamana noua = grid trebuie reconstruit
        self.refresh_all()

    def add_new_employee(self):
        from ui.employee_form import EmployeeRegistrationWindow
        def on_employee_added(full_name):
            try:
                self.employee_store = EmployeeStore()
                employee = full_name.strip()
                if not employee:
                    raise ValueError("Numele angajatului este obligatoriu.")
                self.employee_search_var.set(employee)
                self.refresh_suggestions()
                self.render_unplanned_warning()
                self.show_inline_message(f"{employee} salvat in personal.")
            except ValueError as exc:
                messagebox.showerror("Date invalide", str(exc))

        EmployeeRegistrationWindow(
            self.winfo_toplevel(),
            on_employee_added=on_employee_added,
            initial_department=self.selected_department,
        )

    def add_employee_from_search(self):
        value = self.employee_search_var.get().strip()
        if not value:
            messagebox.showwarning("Lipseste numele", "Introdu sau selecteaza un angajat.")
            return
        matches = self.employee_store.search(value)
        employee = matches[0] if matches and matches[0].casefold() == value.casefold() else value
        self.add_employee_to_selected_cell(employee)

    def add_employee_to_selected_cell(self, employee: str):
        if not self._ensure_week_editable():
            return
        try:
            default_color = ABSENCE_COLORS.get(employee.strip().upper(), HOURS_COLOR_MAP["8h"])
            self.store.add_employee_assignment(
                self.week_record,
                self.current_mode,
                self.selected_department,
                self.selected_day,
                self.selected_shift,
                employee,
                default_color=default_color,
            )
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)
            return
        self._dirty = True
        log_event(
            action="add_employee",
            user=self._username or "unknown",
            week=self._current_week_code(),
            details={
                "mode": self.current_mode,
                "department": self.selected_department,
                "day": self.selected_day,
                "shift": self.selected_shift,
                "employee": employee,
            },
        )
        self.employee_search_var.set("")
        self.show_inline_message(f"{employee} adaugat.")
        self._refresh_after_cell_change()
        if self._search_entry:
            self._search_entry.focus_set()

    def toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)

    def delete_employee_global(self):
        if not self._require_admin("stergere globala angajat"):
            return
        value = self.employee_search_var.get().strip()
        if not value:
            self.show_inline_message("Scrie angajatul in search inainte de a sterge.", is_error=True)
            return
        confirm = messagebox.askyesno("Confirmare Stergere", f"Esti sigur ca vrei sa stergi angajatul '{value}' din toata baza de date?")
        if not confirm:
            return
            
        success_db = self.employee_store.delete_employee(value)
        try:
            from logic.personnel_manager import PersonnelManager
            pm = PersonnelManager()
            success_pm = pm.delete_record(value)
        except (ImportError, OSError, ValueError, AttributeError):
            success_pm = False
            
        if success_db or success_pm:
            self.show_inline_message(f"Angajatul '{value}' a fost sters global.")
            self.employee_search_var.set("")
            self.refresh_suggestions()
        else:
            self.show_inline_message(f"Angajatul '{value}' nu a fost gasit in baze de date.", is_error=True)

    def rename_employee_global(self):
        old_val = self.employee_search_var.get().strip()
        if not old_val:
            self.show_inline_message("Scrie angajatul in search inainte de a-l redenumi.", is_error=True)
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
                f"Redenumit in '{new_name}'. {count} intrare(i) actualizate in planificari."
            )
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

    def _rename_in_schedule_store(self, old_name: str, new_name: str) -> int:
        """
        Redenumeste angajatul in toate saptamanile/modurile/celulele din store.
        Actualizeaza si cheile din dictionarele de culori.
        Returneaza numarul de intrari modificate.
        """
        try:
            return self.store.rename_employee_everywhere(old_name, new_name, skip_locked=True)
        except (OSError, ValueError, RuntimeError) as exc:
            log_exception("rename_in_schedule_store", exc)
            return 0
            
    def remove_employee(self, employee: str):
        if not self._ensure_week_editable():
            return
        self.store.remove_employee_assignment(
            self.week_record,
            self.current_mode,
            self.selected_department,
            self.selected_day,
            self.selected_shift,
            employee,
        )
        self._dirty = True
        log_event(
            action="remove_employee",
            user=self._username or "unknown",
            week=self._current_week_code(),
            details={
                "mode": self.current_mode,
                "department": self.selected_department,
                "day": self.selected_day,
                "shift": self.selected_shift,
                "employee": employee,
            },
        )
        self.refresh_all()

    def reorder_employee(self, employee: str, direction: int):
        if not self._ensure_week_editable():
            return
        self.store.reorder_employee_assignment(
            self.week_record,
            self.current_mode,
            self.selected_department,
            self.selected_day,
            self.selected_shift,
            employee,
            direction,
        )
        self._dirty = True
        self.refresh_all()

    def move_employee_to_shift(self, employee: str):
        if not self._ensure_week_editable():
            return
        source_shift = self.selected_shift
        candidates = [shift for shift in SHIFTS if shift != self.selected_shift]
        dlg = MoveShiftDialog(self.winfo_toplevel(), candidates)
        self.wait_window(dlg)
        target_shift = dlg.selected
        if target_shift is None:
            return
        try:
            self.store.move_employee_assignment(
                self.week_record,
                self.current_mode,
                self.selected_department,
                self.selected_day,
                self.selected_shift,
                target_shift,
                employee,
            )
        except ValueError as exc:
            messagebox.showwarning("Mutare invalida", str(exc))
            return
        self.selected_shift = target_shift
        self._dirty = True
        log_event(
            action="move_employee",
            user=self._username or "unknown",
            week=self._current_week_code(),
            details={
                "mode": self.current_mode,
                "department": self.selected_department,
                "day": self.selected_day,
                "source_shift": source_shift,
                "target_shift": target_shift,
                "employee": employee,
            },
        )
        self.refresh_all()

    def add_department(self):
        if not self._ensure_week_editable():
            return
        dialog = ctk.CTkInputDialog(text="Introdu departamentul nou", title="Departament nou")
        value = dialog.get_input()
        if value is None:
            return
        department = " ".join(value.split()).strip()
        if not department:
            return
        try:
            self.store.add_department(self.week_record, self.current_mode, department)
        except ValueError as exc:
            messagebox.showwarning("Exista deja", str(exc))
            return
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
            self.show_inline_message("Saptamana anterioara a fost duplicata cu succes.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

    def clear_weekend(self):
        if not self._ensure_week_editable():
            return
        try:
            self.store.clear_weekend(self.week_record, self.current_mode, self._username or "")
        except PermissionError:
            self.show_inline_message("Unauthorized", is_error=True)
            return
        self._dirty = True
        self.refresh_all()
        self.show_inline_message(f"Weekend curatat pentru {self.current_mode}.")

    def clear_department(self):
        if not self._ensure_week_editable():
            return
        if not messagebox.askyesno("Confirmare", f"Sterg toate alocarile din {self.selected_department}?"):
            return
        try:
            self.store.clear_department(
                self.week_record,
                self.current_mode,
                self.selected_department,
                self._username or "",
            )
        except PermissionError:
            self.show_inline_message("Unauthorized", is_error=True)
            return
        self._dirty = True
        self.refresh_all()
        self.show_inline_message(f"Departamentul {self.selected_department} a fost golit.")

    def publish_to_tv(self):
        if self._busy_action:
            return
        week_text = self._current_week_code()
        confirm = messagebox.askyesno(
            "Confirmare publicare",
            "Sigur vrei sa publici planificarea?\n\n"
            f"Saptamana: {week_text}\n"
            f"Departament: {self.selected_department}\n\n"
            "Dupa publicare:\n"
            "- datele devin vizibile pe toate ecranele\n"
            "- saptamana va fi blocata (read-only)",
        )
        if not confirm:
            return
        week_snapshot = deepcopy(self.week_record)
        self._set_busy_action(True, disable_publish=True)

        def _worker():
            try:
                week_key = week_snapshot.get("week_start", "")
                if not week_key:
                    raise ValueError("Saptamana curenta este invalida.")
                self.store.data.setdefault("weeks", {})[week_key] = deepcopy(week_snapshot)
                self.store.publish_week(week_key, self._username or "")

                def _ok():
                    self.week_record = self.store.get_or_create_week(self.selected_date)
                    self._dirty = False
                    self._update_dirty_indicator()
                    self._refresh_lock_button()
                    self.render_unplanned_warning()
                    self.show_inline_message("Planificarea a fost publicata pe ecrane.")
                    messagebox.showinfo(
                        "Publicare reusita",
                        "Planificarea live a fost actualizata.",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _ok)
            except (OSError, ValueError, RuntimeError, PermissionError) as exc:
                error_text = str(exc)
                log_exception("publish_to_tv", exc)

                def _err():
                    self.show_inline_message("Publicarea a esuat.", is_error=True)
                    messagebox.showerror(
                        "Publicare",
                        f"Nu am putut publica planificarea:\n\n{error_text}",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _err)
            finally:
                self._finish_background_action()

        threading.Thread(target=_worker, daemon=True).start()

    def export_pdf_dialog(self):
        if self._busy_action:
            return

        export_dir = self._ensure_export_dir()
        path = filedialog.asksaveasfilename(
            title="Export PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialdir=str(export_dir) if export_dir.exists() else None,
            initialfile=self._default_pdf_filename(),
            parent=self.winfo_toplevel(),
        )
        if not path:
            return

        self._set_busy_action(True, disable_pdf=True)

        week_snapshot = deepcopy(self.week_record)

        def _worker():
            try:
                from logic.pdf_exporter import export_full_week_plan_pdf

                export_full_week_plan_pdf(week_record=week_snapshot, output_path=path)

                def _ok():
                    self.show_inline_message("PDF exportat cu succes.")
                    messagebox.showinfo(
                        "Export PDF",
                        f"PDF exportat cu succes:\n\n{path}",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _ok)
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                error_text = str(exc)
                log_exception("export_pdf", exc)

                def _err():
                    self.show_inline_message("Export PDF a esuat.", is_error=True)
                    messagebox.showerror(
                        "Export PDF",
                        f"Nu am putut genera PDF-ul:\n\n{error_text}",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _err)
            finally:
                self._finish_background_action()

        threading.Thread(target=_worker, daemon=True).start()

    def export_excel_dialog(self):
        if self._busy_action:
            return

        export_dir = self._ensure_export_dir()
        path = filedialog.asksaveasfilename(
            title="Export Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialdir=str(export_dir) if export_dir.exists() else None,
            initialfile=self._default_excel_filename(),
            parent=self.winfo_toplevel(),
        )
        if not path:
            return

        self._set_busy_action(True, disable_pdf=True, disable_excel=True)

        week_snapshot = deepcopy(self.week_record)

        def _worker():
            try:
                from logic.excel_exporter import export_full_week_plan_excel

                export_full_week_plan_excel(week_record=week_snapshot, output_path=path)

                def _ok():
                    self.show_inline_message("Excel exportat cu succes.")
                    messagebox.showinfo(
                        "Export Excel",
                        f"Fisierul Excel a fost generat:\n\n{path}",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _ok)
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                error_text = str(exc)
                log_exception("export_excel", exc)

                def _err():
                    self.show_inline_message("Export Excel a esuat.", is_error=True)
                    messagebox.showerror(
                        "Export Excel",
                        f"Nu am putut genera fisierul Excel:\n\n{error_text}",
                        parent=self.winfo_toplevel(),
                    )

                self.after(0, _err)
            finally:
                self._finish_background_action()

        threading.Thread(target=_worker, daemon=True).start()

    def _ensure_export_dir(self) -> Path:
        export_dir = BASE_DIR / "Exports"
        try:
            export_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return export_dir

    def _default_pdf_filename(self) -> str:
        week_start = str(self.week_record.get("week_start") or date.today().isoformat())
        return f"Planificare_Completa_{week_start}.pdf"

    def _default_excel_filename(self) -> str:
        week_start = str(self.week_record.get("week_start") or date.today().isoformat())
        return f"Planificare_Completa_{week_start}.xlsx"

    def _set_busy_cursor(self, busy: bool) -> None:
        try:
            cursor = "watch" if busy else ""
            self.configure(cursor=cursor)
            self.winfo_toplevel().configure(cursor=cursor)
            self._busy_cursor_enabled = busy
        except tk.TclError:
            self._busy_cursor_enabled = False

    def _finish_background_action(self) -> None:
        def _finally():
            self._set_busy_action(False)

        try:
            self.after(0, _finally)
        except (tk.TclError, RuntimeError):
            _finally()

    def _set_busy_action(
        self,
        busy: bool,
        *,
        disable_pdf: bool = False,
        disable_excel: bool = False,
        disable_publish: bool = False,
    ) -> None:
        self._busy_action = busy
        self._set_busy_cursor(busy)
        try:
            if self._export_pdf_button is not None:
                state = "disabled" if busy and disable_pdf else "normal"
                self._export_pdf_button.configure(state=state)
            if self._export_excel_button is not None:
                state = "disabled" if busy and disable_excel else "normal"
                self._export_excel_button.configure(state=state)
            if self._publish_button is not None:
                state = "disabled" if busy and disable_publish else "normal"
                if not self._is_admin():
                    state = "disabled"
                self._publish_button.configure(state=state)
            if self._lock_button is not None:
                self._lock_button.configure(state="disabled" if busy else "normal")
            if self._add_button is not None:
                self._add_button.configure(state="disabled" if busy else ("disabled" if self.store.is_week_locked(self.week_record) else "normal"))
            if self._delete_global_button is not None:
                self._delete_global_button.configure(state="disabled" if busy else ("normal" if self._is_admin() else "disabled"))
        except tk.TclError:
            pass

    def save_week(self):
        try:
            self.store.update_week(self.week_record)
            self._dirty = False
            from datetime import datetime as _dt
            self._last_saved_var.set(f"Salvat la {_dt.now().strftime('%H:%M:%S')}")
            self._update_dirty_indicator()
            self.refresh_history()
            self.show_inline_message("Saptamana salvata.")
        except (OSError, ValueError, RuntimeError) as exc:
            log_exception("save_week", exc)
            self.show_inline_message("A aparut o eroare la salvare.", is_error=True)

    def _employee_day_count(self, employee: str):
        count = 0
        mode_record = self.current_mode_record()
        for department in mode_record["departments"]:
            for shift in SHIFTS:
                employees = mode_record["schedule"][department][self.selected_day][shift]["employees"]
                if any(item.casefold() == employee.casefold() for item in employees):
                    count += 1
        return count

    def destroy(self):
        if self._closing:
            return
        self._closing = True
        super().destroy()


    def confirm_close(self) -> bool:
        """Returneaza True daca e sigur sa se inchida (fara modificari sau user a confirmat)."""
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Modificari nesalvate",
            "Exista modificari nesalvate.\nSalvezi inainte de a iesi din aplicatie?",
        )
        if answer is None:   # Cancel
            return False
        if answer:           # Yes
            self.save_week()
        return True

    # Dirty indicator

    def _update_dirty_indicator(self):
        """Actualizeaza labelul daca exista modificari nesalvate."""
        if self._dirty_indicator is None:
            return
        if self._dirty:
            self._dirty_indicator.configure(text="* Modificari nesalvate")
        else:
            self._dirty_indicator.configure(text="")

    # Lock week

    def lock_week_toggle(self):
        """Publicare / deblocare saptamana curenta."""
        try:
            if self.store.is_week_locked(self.week_record):
                self.store.unlock_week(self.week_record, self._username or "")
                log_event(
                    action="unlock_week",
                    user=self._username or "unknown",
                    week=self._current_week_code(),
                    details={"source": "manual"},
                )
                self.show_inline_message("Saptamana a fost deblocata pentru editare.")
            else:
                if self._dirty:
                    self.save_week()
                self.store.lock_week(self.week_record, self._username or "")
                log_event(
                    action="lock_week",
                    user=self._username or "unknown",
                    week=self._current_week_code(),
                    details={"source": "manual"},
                )
                self.show_inline_message("Saptamana a fost publicata (read-only).")
        except PermissionError:
            self.show_inline_message("Unauthorized", is_error=True)
            return
        self._refresh_lock_button()
        self._sync_action_states()

    def _refresh_lock_button(self):
        """Actualizeaza textul si culoarea butonului de lock in functie de starea curenta."""
        if self._lock_button is None:
            return
        if self.store.is_week_locked(self.week_record):
            self._lock_state_var.set("SAPTAMANA BLOCATA")
            self._lock_button.configure(
                text="Saptamana publicata",
                fg_color="#9B241A", hover_color="#842016",
            )
        else:
            self._lock_state_var.set("")
            self._lock_button.configure(
                text="Saptamana deschisa",
                fg_color="#145C32", hover_color="#0F4A28",
            )

    def _sync_action_states(self):
        is_locked = self.store.is_week_locked(self.week_record)
        if self._add_button is not None:
            self._add_button.configure(state="disabled" if is_locked else "normal")
        if self._publish_button is not None:
            can_publish = self._is_admin() and not self._busy_action
            self._publish_button.configure(state="normal" if can_publish else "disabled")
        if self._delete_global_button is not None:
            self._delete_global_button.configure(state="normal" if self._is_admin() else "disabled")

    def _auto_save(self):
        # Pastrat ca metoda inerta pentru compatibilitate cu instante vechi/teste.
        # Plannerul nu mai salveaza automat: modificarile se scriu doar la actiuni explicite.
        return

    # Absente rapide

    def _quick_add_absence(self, absence_type: str):
        """Adauga tipul de absenta in celula selectata curent."""
        self.add_employee_to_selected_cell(absence_type)
