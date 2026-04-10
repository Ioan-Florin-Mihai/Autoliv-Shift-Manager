import json
import tkinter as tk
import tkinter.messagebox as messagebox
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from queue import Empty, Queue

import customtkinter as ctk

from logic.app_config import get_config
from logic.app_logger import log_exception
from logic.audit_logger import log_event
from logic.employee_store import EmployeeStore
from logic.remote_control import RemoteChecker, RemoteControlService
from logic.schedule_store import (
    DAY_NAMES,
    DAYS,
    SHIFTS,
    TEMPLATES,
    WEEKEND_DAYS,
    ScheduleStore,
    format_day_label,
)
from logic.ui_state_store import UIStateStore
from ui.common_ui import (
    BG_WHITE,
    BODY_TEXT,
    CARD_WHITE,
    ENTRY_BG,
    LINE_BLUE,
    MUTED_TEXT,
    PANEL_BG,
    PRIMARY_BLUE,
    DatePickerDialog,
)

ACCENT_BLUE = "#0067C8"
SOFT_BLUE = "#DCEBFA"
WEEKEND_BG = ("#DDF7F1", "#1F4F4C")
WEEKEND_SELECTED_BG = ("#BFEAE1", "#2B6661")
SELECTED_BG = ("#D2E7FF", "#1C4268")
GRID_CELL_BG = ("#FFFFFF", "#2A2A2A")
SUGGESTION_BG = ("#D9E6F5", "#1E3A5F")
HOVER_BLUE = "#2E7FD2"
PANEL_GAP = 16
OUTER_PAD = 16
SECTION_GAP = 24
SECTION_INNER_GAP = 8
LEFT_PANEL_WIDTH = 290
RIGHT_PANEL_WIDTH = 400
PRIMARY_BUTTON_HEIGHT = 44
SECONDARY_BUTTON_HEIGHT = 32
UTILITY_BUTTON_HEIGHT = 30
SEARCH_HEIGHT = 38
GRID_HEADER_HEIGHT = 44
GRID_CELL_PAD = 6
GRID_INNER_PAD = 10
HEADER_FONT_SIZE = 16
SHIFT_FONT_SIZE = 14
SECTION_LABEL_FONT_SIZE = 11
SECONDARY_BUTTON_FG = ("#EEF4FB", "#25303D")
SECONDARY_BUTTON_HOVER = ("#E2ECF8", "#314155")
UTILITY_BUTTON_FG = ("#F7FAFD", "#202934")
UTILITY_BUTTON_HOVER = ("#E9F0F8", "#293746")
UTILITY_BUTTON_TEXT = ("#15304B", "#E8EEF5")
DANGER_RED = "#C0392B"
DANGER_RED_HOVER = "#A93226"
SUBTLE_HINT_TEXT = ("#93A5B8", "#6D8092")
CELL_MIN_HEIGHT = 204
GRID_BORDER_LIGHT = "#D8E1EB"
GRID_BORDER_DARK = "#6C88A6"
GRID_HOVER_LIGHT = "#98B8D9"
GRID_HOVER_DARK = "#8FAFD1"
HOURS_COLOR_MAP = {"8h": "#1A1A1A", "12h": "#C0392B"}
BADGE_WIDTH = 24
BADGE_HEIGHT = 24
GRID_NAME_MAX_CHARS = 16
PANEL_NAME_MAX_CHARS = 28
VISIBLE_EMPLOYEE_ROWS = 5
EMPLOYEE_ROW_HEIGHT = 28
EMPLOYEE_ROW_PADY = 3
EMPLOYEE_NAME_TEXT = ("#15304B", "#F4F7FB")
DAY_VIEW_LABELS = {
    "weekdays": "Zilele saptamanii",
    "weekend": "Weekend",
}


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

# Culori tipuri absență (CO=portocaliu, CM=violet, ABSENT=roșu intens)
ABSENCE_COLORS: dict[str, str] = {
    "CO":     "#F39C12",
    "CM":     "#8E44AD",
    "ABSENT": "#E74C3C",
}
ABSENCE_TYPES: list[str] = list(ABSENCE_COLORS.keys())


class MoveShiftDialog(ctk.CTkToplevel):
    """Dialog cu butoane pentru selectarea shift-ului destinație."""

    def __init__(self, master, candidate_shifts: list[str]):
        super().__init__(master)
        self.selected: str | None = None
        self.title("Mută în shift")
        self.geometry("300x160")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        ctk.CTkLabel(
            self, text="Selectează shift-ul destinație:",
            font=ctk.CTkFont(size=13),
        ).pack(pady=(20, 12))
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()
        for shift in candidate_shifts:
            ctk.CTkButton(
                btn_frame, text=shift, width=80, height=34,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda s=shift: self._select(s),
            ).pack(side="left", padx=6)
        ctk.CTkButton(
            self, text="Anulează", width=100, height=30,
            fg_color="#B8C2CC", hover_color="#9EAAB6", text_color="white",
            command=self.destroy,
        ).pack(pady=10)

    def _select(self, shift: str):
        self.selected = shift
        self.destroy()


class PlannerDashboard(ctk.CTkFrame):
    def __init__(self, master, remote_service: RemoteControlService, username: str = "", user_role: str = "operator"):
        super().__init__(master, corner_radius=0)
        self.remote_service = remote_service
        self._username = username          # utilizatorul autentificat curent
        self._user_role = user_role or "operator"
        self._config = get_config()
        self.store = ScheduleStore()
        self.ui_state_store = UIStateStore()
        self.employee_store = EmployeeStore()
        self.events: Queue[dict[str, str]] = Queue()
        self.remote_checker = RemoteChecker(remote_service, self.events)

        self.selected_date = self.ui_state_store.resolve_startup_date()
        self.week_record = self.store.get_or_create_week(self.selected_date)
        self.current_mode = "Magazie"
        self.selected_department = self.current_mode_record()["departments"][0]
        self.department_list: list[str] = []
        self.department_index = 0
        self.selected_day = DAY_NAMES[0]
        self.selected_shift = SHIFTS[0]
        self.status_var = ctk.StringVar(value="Planner pregatit.")
        self.week_var = ctk.StringVar()
        self.day_view_mode = ctk.StringVar(value="weekdays")
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
        self._delete_global_button: ctk.CTkButton | None = None
        self._add_button: ctk.CTkButton | None = None
        self._dirty_indicator: ctk.CTkLabel | None = None
        self._grid_cell_frames: dict = {}          # cache {(day, shift): CTkFrame}
        self._grid_cell_canvases: dict = {}        # cache {(day, shift): tk.Canvas}
        self.ui_state_store.save_last_selected_date(self.selected_date)
        self._sync_department_state()

        self._build_ui()
        self.refresh_all()
        self.remote_checker.start()
        self.after(1000, self.process_remote_events)
        self.after(60000, self._auto_save)

    def _current_week_code(self) -> str:
        try:
            week_start = date.fromisoformat(self.week_record.get("week_start", ""))
            iso = week_start.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        except Exception:
            return "unknown"

    def _is_admin(self) -> bool:
        return self._user_role == "admin"

    def _require_admin(self, action_name: str) -> bool:
        if self._is_admin():
            return True
        self.show_inline_message(f"Doar admin poate executa acțiunea: {action_name}.", is_error=True)
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
        status = {"server": "oprit", "tv": "necunoscut", "last_update": "-"}
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
        tv_status = self._tv_status_snapshot()
        rows = [
            ("Utilizator activ", f"{self._username or '-'} ({self._user_role})"),
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
        if not messagebox.askyesno("Confirmare restore", f"Restaurăm backup-ul {selected}?\nDraft și live vor fi rescrise."):
            return
        try:
            self.store.restore_backup(selected.strip())
            self.week_record = self.store.get_or_create_week(self.selected_date)
            self._dirty = False
            self.refresh_all()
            self.show_inline_message("Backup restaurat cu succes.")
        except ValueError as exc:
            self.show_inline_message(str(exc), is_error=True)

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
        if self.day_view_mode.get() == "weekend":
            return [day for day in DAYS if day[0] in WEEKEND_DAYS]
        return [day for day in DAYS if day[0] not in WEEKEND_DAYS]

    def _ensure_selected_day_is_visible(self):
        visible_day_names = [day_name for day_name, _ in self._visible_days()]
        if self.selected_day not in visible_day_names and visible_day_names:
            self.selected_day = visible_day_names[0]

    def set_day_view_mode(self, mode: str):
        if mode not in DAY_VIEW_LABELS:
            return
        self.day_view_mode.set(mode)
        self._ensure_selected_day_is_visible()
        self.refresh_all()

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
        selected = "#8EB8E5" if is_dark else PRIMARY_BLUE[0]
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
        is_weekend = day_name in WEEKEND_DAYS
        if is_selected:
            fg_color = WEEKEND_SELECTED_BG if is_weekend else SELECTED_BG
            border_color = selected_border
        elif is_weekend:
            fg_color = WEEKEND_BG
            border_color = hover_border if hover else normal_border
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

    def _build_center(self):
        frame = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        frame.grid(row=0, column=1, sticky="nsew", padx=(0, PANEL_GAP))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        header_row = ctk.CTkFrame(frame, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=OUTER_PAD, pady=(12, 4))
        header_row.grid_columnconfigure(0, weight=1)

        self.editor_title = ctk.CTkLabel(header_row, text="Editor", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=22, weight="bold"))
        self.editor_title.grid(row=0, column=0, sticky="w")

        self.day_toggle_frame = ctk.CTkFrame(header_row, fg_color="transparent")
        self.day_toggle_frame.grid(row=0, column=1, sticky="e")
        self.day_toggle_buttons = {}
        for idx, mode in enumerate(("weekdays", "weekend")):
            button = ctk.CTkButton(
                self.day_toggle_frame,
                text=DAY_VIEW_LABELS[mode],
                command=lambda value=mode: self.set_day_view_mode(value),
                height=28,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            button.pack(side="left", padx=(0, 6) if idx == 0 else (0, 0))
            self.day_toggle_buttons[mode] = button

        toolbar_row = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar_row.grid(row=1, column=0, sticky="ew", padx=OUTER_PAD, pady=(0, 8))
        toolbar_row.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(toolbar_row, textvariable=self.status_var, text_color=BODY_TEXT, anchor="w", justify="left", font=ctk.CTkFont(size=13, weight="bold"))
        self.status_label.grid(row=0, column=0, sticky="w")
        self.editor_hint = ctk.CTkLabel(
            toolbar_row,
            text="Selecteaza o celula si adauga angajatul din panoul din dreapta.",
            text_color=MUTED_TEXT,
            anchor="e",
            justify="right",
            font=ctk.CTkFont(size=12),
        )
        self.editor_hint.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.grid_shell = ctk.CTkFrame(frame, fg_color=PANEL_BG, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        self.grid_shell.grid(row=2, column=0, sticky="nsew", padx=OUTER_PAD, pady=(0, OUTER_PAD))
        self.grid_shell.grid_columnconfigure(0, weight=1)
        self.grid_shell.grid_rowconfigure(0, weight=1)
        self.grid_frame = ctk.CTkScrollableFrame(
            self.grid_shell,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
            scrollbar_button_color="#9EB6CF",
            scrollbar_button_hover_color="#7F9AB8",
        )
        self.grid_frame.grid(row=0, column=0, sticky="nsew", padx=GRID_INNER_PAD, pady=GRID_INNER_PAD)

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
        frame.grid_rowconfigure(0, weight=3)
        frame.grid_rowconfigure(3, weight=2)

        context_section = ctk.CTkFrame(frame, fg_color="transparent")
        context_section.grid(row=0, column=0, sticky="nsew", padx=20, pady=(OUTER_PAD, SECTION_GAP))
        context_section.grid_columnconfigure(0, weight=1)
        context_section.grid_rowconfigure(5, weight=1)
        self._create_section_label(context_section, "CONTEXT").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        department_nav = ctk.CTkFrame(context_section, fg_color="transparent")
        department_nav.grid(row=1, column=0, sticky="ew", pady=(0, SECTION_INNER_GAP))
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
        self.cell_title = ctk.CTkLabel(context_section, text="Celula selectata", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=20, weight="bold"))
        self.cell_title.grid(row=2, column=0, sticky="w")
        self.cell_meta = ctk.CTkLabel(context_section, text="", text_color=MUTED_TEXT, justify="left")
        self.cell_meta.grid(row=3, column=0, sticky="w", pady=(2, SECTION_INNER_GAP))
        ctk.CTkLabel(context_section, text="Angajati in celula", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.assignment_frame = ctk.CTkScrollableFrame(context_section, width=370, fg_color=PANEL_BG)
        self.assignment_frame.grid(row=5, column=0, sticky="nsew")
        context_section.grid_rowconfigure(5, weight=1)

        quick_add_section = ctk.CTkFrame(frame, fg_color="transparent")
        quick_add_section.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, SECTION_GAP))
        quick_add_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(quick_add_section, "QUICK ADD").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        entry = ctk.CTkEntry(
            quick_add_section,
            textvariable=self.employee_search_var,
            placeholder_text="Scrie numele angajatului",
            height=SEARCH_HEIGHT,
            fg_color=ENTRY_BG,
            border_width=2,
            border_color=LINE_BLUE,
            text_color=BODY_TEXT,
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(0, SECTION_INNER_GAP))
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
            height=PRIMARY_BUTTON_HEIGHT,
            corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._add_button.grid(row=2, column=0, sticky="ew")

        more_actions_section = ctk.CTkFrame(frame, fg_color="transparent")
        more_actions_section.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, SECTION_GAP))
        more_actions_section.grid_columnconfigure(0, weight=1)
        self._create_section_label(more_actions_section, "MORE ACTIONS").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        self._create_secondary_button(more_actions_section, "Angajat Nou", self.add_new_employee, height=SECONDARY_BUTTON_HEIGHT).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._create_secondary_button(more_actions_section, "Redenumește", self.rename_employee_global, height=SECONDARY_BUTTON_HEIGHT).grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._delete_global_button = ctk.CTkButton(
            more_actions_section,
            text="Șterge global",
            command=self.delete_employee_global,
            fg_color=DANGER_RED,
            hover_color=DANGER_RED_HOVER,
            text_color="white",
            height=SECONDARY_BUTTON_HEIGHT,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._delete_global_button.grid(row=3, column=0, sticky="ew")

        suggestions_section = ctk.CTkFrame(frame, fg_color="transparent")
        suggestions_section.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, OUTER_PAD))
        suggestions_section.grid_columnconfigure(0, weight=1)
        suggestions_section.grid_rowconfigure(1, weight=1)
        self._create_section_label(suggestions_section, "SUGESTII").grid(row=0, column=0, sticky="w", pady=(0, SECTION_INNER_GAP))
        self.suggestion_frame = ctk.CTkScrollableFrame(suggestions_section, width=370, fg_color=PANEL_BG)
        self.suggestion_frame.grid(row=1, column=0, sticky="nsew")

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
        self._ensure_selected_day_is_visible()
        self.refresh_week_display()
        self.refresh_history()
        self.render_day_toggle_buttons()
        self.render_department_navigation()
        self.render_grid()
        self.render_assignment_panel()
        self.refresh_suggestions()
        self._update_dirty_indicator()
        self._refresh_lock_button()
        self._sync_action_states()

    def refresh_week_display(self):
        start = datetime.strptime(self.week_record["week_start"], "%Y-%m-%d").date()
        end = datetime.strptime(self.week_record["week_end"], "%Y-%m-%d").date()
        self.week_var.set(f"{self.week_record['week_label']}\n{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}")
        self.editor_title.configure(text=f"Editor: {self.selected_department}")
        split_names = [name for name in self.current_cell()["employees"] if self._employee_day_count(name) > 1]
        extra = f"  |  Split in zi: {', '.join(split_names)}" if split_names else ""
        self.cell_title.configure(text=f"{self.selected_department} | {self.selected_day} | {self.selected_shift}")
        self.cell_meta.configure(text=f"Tip: {self.current_mode}{extra}")

    def refresh_history(self):
        values = [f"{label} | {key}" for key, label, _ in self.store.get_week_history()] or [""]
        self.history_menu.configure(values=values)
        self.history_var.set(values[0])

    def render_department_navigation(self):
        self.department_name_var.set(self.selected_department or "-")

    def render_day_toggle_buttons(self):
        if not hasattr(self, "day_toggle_buttons"):
            return
        active_mode = self.day_view_mode.get()
        for mode_name, button in self.day_toggle_buttons.items():
            selected = mode_name == active_mode
            button.configure(
                fg_color=PRIMARY_BLUE if selected else SUGGESTION_BG,
                hover_color=ACCENT_BLUE if selected else "#C7D7E8",
                text_color="white" if selected else ("#15304B", "#E8E8E8"),
                width=150 if mode_name == "weekdays" else 92,
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
        visible_days = self._visible_days()
        self.grid_frame.grid_columnconfigure(0, weight=0)
        self.grid_frame.grid_rowconfigure(0, weight=0, minsize=GRID_HEADER_HEIGHT)
        for idx in range(1, len(visible_days) + 1):
            self.grid_frame.grid_columnconfigure(idx, weight=1)
        ctk.CTkLabel(self.grid_frame, text="Schimb", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=SHIFT_FONT_SIZE, weight="bold")).grid(row=0, column=0, padx=(6, 12), pady=8, sticky="w")
        for day_idx, (day_name, day_offset) in enumerate(visible_days, start=1):
            header_fg = WEEKEND_BG if day_name in WEEKEND_DAYS else SOFT_BLUE
            cell = ctk.CTkFrame(self.grid_frame, fg_color=header_fg, corner_radius=10, border_width=1, border_color=LINE_BLUE)
            cell.grid(row=0, column=day_idx, padx=GRID_CELL_PAD, pady=GRID_CELL_PAD, sticky="ew")
            ctk.CTkLabel(cell, text=format_day_label(start, day_offset), text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=HEADER_FONT_SIZE, weight="bold")).pack(padx=10, pady=9)

        for row_idx, shift in enumerate(SHIFTS, start=1):
            self.grid_frame.grid_rowconfigure(row_idx, weight=0, minsize=CELL_MIN_HEIGHT + 12)
            ctk.CTkLabel(self.grid_frame, text=shift, text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=SHIFT_FONT_SIZE, weight="bold")).grid(row=row_idx, column=0, padx=(6, 12), pady=8, sticky="nw")
            for day_idx, (day_name, _) in enumerate(visible_days, start=1):
                cell_data  = self.current_mode_record()["schedule"][self.selected_department][day_name][shift]
                employees  = cell_data.get("employees", [])
                cell_colors = cell_data.get("colors", {})
                normal_border, _hover_border, selected_border = self._grid_border_theme()
                is_selected = self.selected_day == day_name and self.selected_shift == shift
                is_weekend = day_name in WEEKEND_DAYS
                if is_selected:
                    cell_bg = WEEKEND_SELECTED_BG if is_weekend else SELECTED_BG
                else:
                    cell_bg = WEEKEND_BG if is_weekend else GRID_CELL_BG
                border_color_active = selected_border if is_selected else normal_border

                # Celula — frame clickabil
                cell_frame = ctk.CTkFrame(
                    self.grid_frame,
                    fg_color=cell_bg,
                    corner_radius=14,
                    border_width=self._grid_border_width(is_selected),
                    border_color=border_color_active,
                    width=150,
                    height=CELL_MIN_HEIGHT,
                )
                cell_frame.grid(row=row_idx, column=day_idx, padx=GRID_CELL_PAD, pady=GRID_CELL_PAD, sticky="nsew")
                cell_frame.grid_propagate(False)
                cell_frame.pack_propagate(False)
                cell_frame.bind("<Button-1>", lambda _e, d=day_name, s=shift: self.select_cell(d, s))
                cell_frame.bind("<Enter>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=True))
                cell_frame.bind("<Leave>", lambda _e, d=day_name, s=shift: self._apply_cell_frame_style(d, s, hover=False))
                self._grid_cell_frames[(day_name, shift)] = cell_frame

                # ── Scroll container: tk.Frame → Canvas + Scrollbar → inner_frame ──
                resolved_bg = self._resolve_theme_color(cell_bg)
                scroll_host = tk.Frame(cell_frame, bg=resolved_bg, highlightthickness=0)
                scroll_host.pack(fill="both", expand=True, padx=GRID_INNER_PAD, pady=GRID_INNER_PAD)

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
                        font=("Segoe UI", 7),
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
                        font=("Segoe UI", 8),
                    )
                    add_lbl.pack(expand=True, pady=16)
                    self._bind_cell_mousewheel(add_lbl, content_canvas)
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
            top_row.pack(fill="x", padx=8, pady=(8, 3))
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
            up_btn = self._create_utility_button(actions, "Sus", lambda e=employee: self.reorder_employee(e, -1), width=38, height=26, font=ctk.CTkFont(size=11))
            down_btn = self._create_utility_button(actions, "Jos", lambda e=employee: self.reorder_employee(e, 1), width=38, height=26, font=ctk.CTkFont(size=11))
            move_btn = self._create_utility_button(actions, "Mut", lambda e=employee: self.move_employee_to_shift(e), width=38, height=26, font=ctk.CTkFont(size=11))
            remove_btn = ctk.CTkButton(actions, text="✕", width=28, height=26, fg_color=DANGER_RED, hover_color=DANGER_RED_HOVER, text_color="white", font=ctk.CTkFont(size=12), command=lambda e=employee: self.remove_employee(e))
            if is_locked:
                for btn in (up_btn, down_btn, move_btn, remove_btn):
                    btn.configure(state="disabled")
            up_btn.pack(side="left", padx=(0, 3))
            down_btn.pack(side="left", padx=3)
            move_btn.pack(side="left", padx=3)
            remove_btn.pack(side="left", padx=(3, 0))

            # Randul de jos: selector ore (comportament radio)
            palette_row = ctk.CTkFrame(card, fg_color="transparent")
            palette_row.pack(fill="x", padx=8, pady=(2, 8))
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
        is_locked = self.store.is_week_locked(self.week_record)
        for employee in suggestions:
            btn = ctk.CTkButton(
                self.suggestion_frame,
                text=employee,
                anchor="w",
                height=30,
                fg_color=("#F8FBFE", "#202A35"),
                text_color=UTILITY_BUTTON_TEXT,
                hover_color=("#EBF3FA", "#2B3A4B"),
                border_width=1,
                border_color=LINE_BLUE,
                corner_radius=10,
                font=ctk.CTkFont(size=12),
                command=lambda e=employee: self.add_employee_to_selected_cell(e),
            )
            if is_locked:
                btn.configure(state="disabled")
            btn.pack(fill="x", padx=4, pady=3)

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
        self.show_inline_message(f"{employee} adăugat.")
        self.refresh_all()
        if self._search_entry:
            self._search_entry.focus_set()

    def toggle_theme(self):
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)

    def delete_employee_global(self):
        if not self._require_admin("ștergere globală angajat"):
            return
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
        try:
            return self.store.rename_employee_everywhere(old_name, new_name, skip_locked=True)
        except Exception as exc:
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
            self.show_inline_message("Săptămâna anterioară a fost duplicată cu succes.")
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
        self.show_inline_message(f"Weekend curățat pentru {self.current_mode}.")

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
        week_text = self._current_week_code()
        confirm = messagebox.askyesno(
            "Confirmare publicare",
            "Sigur vrei să publici planificarea?\n\n"
            f"Săptămâna: {week_text}\n"
            f"Departament: {self.selected_department}\n\n"
            "După publicare:\n"
            "• datele devin vizibile pe toate ecranele\n"
            "• săptămâna va fi blocată (read-only)",
        )
        if not confirm:
            return
        try:
            self.store.update_week(self.week_record)
            self.store.publish_week(self.week_record.get("week_start", ""), self._username or "")
            self.week_record = self.store.get_or_create_week(self.selected_date)
            self._dirty = False
            self._update_dirty_indicator()
            self._refresh_lock_button()
            self.show_inline_message("Planificarea a fost publicata pe ecrane.")
            messagebox.showinfo("Publicare reusita", "Planificarea live a fost actualizata.")
        except Exception as exc:
            log_exception("publish_to_tv", exc)
            self.show_inline_message("Publicarea a esuat.", is_error=True)

    def save_week(self):
        try:
            self.store.update_week(self.week_record)
            self._dirty = False
            from datetime import datetime as _dt
            self._last_saved_var.set(f"Salvat la {_dt.now().strftime('%H:%M:%S')}")
            self._update_dirty_indicator()
            self.refresh_history()
            self.show_inline_message("Săptămâna salvată.")
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
                # Mod local — nu afisam nimic in status bar
                pass

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

    # ── Dirty indicator ───────────────────────────────────────────────────────

    def _update_dirty_indicator(self):
        """Actualizează labelul cu '*' dacă există modificări nesalvate."""
        if self._dirty_indicator is None:
            return
        if self._dirty:
            self._dirty_indicator.configure(text="● Modificări nesalvate")
        else:
            self._dirty_indicator.configure(text="")

    # ── Lock week ─────────────────────────────────────────────────────────────

    def lock_week_toggle(self):
        """Publicare / deblocare săptămână curentă."""
        try:
            if self.store.is_week_locked(self.week_record):
                self.store.unlock_week(self.week_record, self._username or "")
                log_event(
                    action="unlock_week",
                    user=self._username or "unknown",
                    week=self._current_week_code(),
                    details={"source": "manual"},
                )
                self.show_inline_message("Săptămâna a fost deblocată pentru editare.")
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
                self.show_inline_message("Săptămâna a fost publicată (read-only).")
        except PermissionError:
            self.show_inline_message("Unauthorized", is_error=True)
            return
        self._refresh_lock_button()
        self._sync_action_states()

    def _refresh_lock_button(self):
        """Actualizează textul și culoarea butonului de lock în funcție de starea curentă."""
        if self._lock_button is None:
            return
        if self.store.is_week_locked(self.week_record):
            self._lock_state_var.set("🔒 SĂPTĂMÂNĂ BLOCATĂ")
            self._lock_button.configure(
                text="🔒 Săptămână publicată",
                fg_color="#C0392B", hover_color="#A93226",
            )
        else:
            self._lock_state_var.set("")
            self._lock_button.configure(
                text="🔓 Săptămâna deschisă",
                fg_color="#27AE60", hover_color="#1E8449",
            )

    def _sync_action_states(self):
        is_locked = self.store.is_week_locked(self.week_record)
        if self._add_button is not None:
            self._add_button.configure(state="disabled" if is_locked else "normal")
        if self._publish_button is not None:
            self._publish_button.configure(state="normal" if self._is_admin() else "disabled")
        if self._delete_global_button is not None:
            self._delete_global_button.configure(state="normal" if self._is_admin() else "disabled")

    def _auto_save(self):
        if self._closing or not self.winfo_exists():
            return
        try:
            if self._dirty:
                self.store.update_week(self.week_record)
                self._dirty = False
                self._last_saved_var.set(f"Salvat automat la {datetime.now().strftime('%H:%M')}")
                self._update_dirty_indicator()
                self.refresh_history()
        except Exception as exc:
            log_exception("auto_save", exc)
        finally:
            try:
                self.after(60000, self._auto_save)
            except tk.TclError:
                pass

    # ── Absențe rapide ────────────────────────────────────────────────────────

    def _quick_add_absence(self, absence_type: str):
        """Adaugă tipul de absență în celula selectată curentă."""
        self.add_employee_to_selected_cell(absence_type)