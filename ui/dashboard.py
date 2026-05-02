import tkinter as tk
import tkinter.messagebox as messagebox

import customtkinter as ctk

from logic.app_logger import log_exception
from logic.auth import get_lockout_remaining_seconds, get_user_role, verify_login_detailed
from logic.ui_state_store import UIStateStore
from logic.version import APP_NAME, VERSION
from ui.common_ui import (
    BG_WHITE,
    BODY_TEXT,
    ENTRY_BG,
    LINE_BLUE,
    MUTED_TEXT,
    PRIMARY_BLUE,
    AutolivLogo,
    apply_window_icon,
)
from ui.planner_dashboard import PlannerDashboard

ACCENT_BLUE = "#004A99"
SHOW_PASSWORD_ICON = "\U0001F441"
HIDE_PASSWORD_ICON = "\U0001F648"


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, corner_radius=0)
        self.on_login_success = on_login_success
        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Autentificare necesara.")
        self.show_password = False
        self._lockout_after_id: str | None = None
        self._lockout_username = ""
        self._build_ui()
        self.winfo_toplevel().bind("<Return>", self._handle_enter_key)

    def _build_ui(self):
        self.pack(fill="both", expand=True)
        self.configure(fg_color=BG_WHITE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Panoul stang: branding albastru
        left = ctk.CTkFrame(self, corner_radius=0, fg_color=("#0A4D9B", "#0A3A7A"))
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        brand = ctk.CTkFrame(left, fg_color="transparent")
        brand.grid(row=0, column=0)
        AutolivLogo(brand, width=340, height=130).pack(pady=(0, 32))
        ctk.CTkLabel(brand, text="Shift Manager", text_color="white",
                     font=ctk.CTkFont(size=38, weight="bold")).pack()
        ctk.CTkLabel(brand, text="Planificare inteligenta a schimburilor", text_color=("#EAF4FF", "#EAF4FF"),
                     font=ctk.CTkFont(size=16)).pack(pady=(10, 0))
        sep = ctk.CTkFrame(brand, height=3, width=200, fg_color=("#EAF4FF", "#EAF4FF"), corner_radius=2)
        sep.pack(pady=(28, 0))

        # Panoul drept: formular
        right = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_WHITE)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.grid(row=0, column=0)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Bun venit!", text_color=PRIMARY_BLUE,
                     font=ctk.CTkFont(size=32, weight="bold")).grid(row=0, column=0, pady=(0, 8))
        ctk.CTkLabel(form, text="Autentifica-te pentru a accesa dashboardul",
                     text_color=MUTED_TEXT, font=ctk.CTkFont(size=15)).grid(row=1, column=0, pady=(0, 40))

        ctk.CTkLabel(form, text="Username", text_color=PRIMARY_BLUE,
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=2, column=0, sticky="w", pady=(0, 6))
        ctk.CTkEntry(form, textvariable=self.username_var, placeholder_text="Introdu username",
                     width=380, height=48, fg_color=ENTRY_BG, border_width=2,
                     border_color=LINE_BLUE, text_color=BODY_TEXT,
                     font=ctk.CTkFont(size=15)).grid(row=3, column=0, pady=(0, 20))

        ctk.CTkLabel(form, text="Parola", text_color=PRIMARY_BLUE,
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=4, column=0, sticky="w", pady=(0, 6))
        password_parent = ctk.CTkFrame(form, fg_color="transparent")
        password_parent.grid(row=5, column=0, pady=(0, 32), sticky="w")
        password_parent.grid_columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(
            password_parent,
            textvariable=self.password_var,
            placeholder_text="Introdu parola",
            show="*",
            width=340,
            height=48,
            fg_color=ENTRY_BG,
            border_width=2,
            border_color=LINE_BLUE,
            text_color=BODY_TEXT,
            font=ctk.CTkFont(size=15),
        )
        self.password_entry.grid(row=0, column=0, sticky="w")

        def toggle_password():
            self.show_password = not self.show_password
            self.password_entry.configure(show="" if self.show_password else "*")
            self.toggle_btn.configure(text=HIDE_PASSWORD_ICON if self.show_password else SHOW_PASSWORD_ICON)

        self.toggle_btn = ctk.CTkButton(
            master=password_parent,
            text=SHOW_PASSWORD_ICON,
            width=35,
            height=48,
            command=toggle_password,
            fg_color=ENTRY_BG,
            hover_color="#e0e0e0",
            border_width=1,
            border_color=LINE_BLUE,
            font=ctk.CTkFont(size=18),
        )
        self.toggle_btn.grid(row=0, column=1, padx=(6, 0))

        self.login_button = ctk.CTkButton(
            form,
            text="Autentificare",
            command=self.login,
            width=380,
            height=52,
            fg_color=ACCENT_BLUE,
            hover_color=ACCENT_BLUE,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=12,
        )
        self.login_button.grid(row=6, column=0, pady=(0, 16))
        ctk.CTkLabel(form, textvariable=self.status_var, text_color=MUTED_TEXT,
                     font=ctk.CTkFont(size=13)).grid(row=7, column=0, padx=32, pady=(4, 24))

    def login(self):
        if self._is_login_locked():
            return
        username = self.username_var.get().strip()
        password = self.password_var.get()
        try:
            ok, msg = verify_login_detailed(username, password)
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Eroare configurare", str(exc))
            self.status_var.set("Configurarea login-ului este invalida.")
            return
        if not ok:
            self.status_var.set(msg or "Username sau parola invalida.")
            self._start_lockout_countdown(username)
            return
        self._cancel_lockout_countdown()
        self._logged_in_username = username
        self.on_login_success(username, get_user_role(username))

    def _handle_enter_key(self, _event):
        self.login()

    def _is_login_locked(self) -> bool:
        try:
            return str(self.login_button.cget("state")) == "disabled"
        except (tk.TclError, AttributeError):
            return False

    def _start_lockout_countdown(self, username: str) -> None:
        remaining = get_lockout_remaining_seconds(username)
        if remaining <= 0:
            return
        self._lockout_username = username
        self.login_button.configure(state="disabled")
        self._render_lockout_countdown()

    def _render_lockout_countdown(self) -> None:
        remaining = get_lockout_remaining_seconds(self._lockout_username)
        if remaining <= 0:
            self._cancel_lockout_countdown()
            self.status_var.set("")
            return
        suffix = "secunda" if remaining == 1 else "secunde"
        self.status_var.set(f"Prea multe incercari esuate. Incearca din nou dupa {remaining} {suffix}.")
        self._lockout_after_id = self.after(1000, self._render_lockout_countdown)

    def _cancel_lockout_countdown(self) -> None:
        if self._lockout_after_id is not None:
            try:
                self.after_cancel(self._lockout_after_id)
            except tk.TclError:
                pass
        self._lockout_after_id = None
        self._lockout_username = ""
        try:
            self.login_button.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass


class ShiftManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self._current_username: str | None = None
        self._current_role: str = "operator"
        self.geometry("1620x900")
        self.state("zoomed")
        self.minsize(1320, 760)
        self.ui_state_store = UIStateStore()
        ctk.set_appearance_mode(self.ui_state_store.load_theme())
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_WHITE)
        apply_window_icon(self)
        self.current_frame = None
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.show_login()

    def show_login(self):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = LoginFrame(self, self.show_dashboard)

    def show_dashboard(self, username: str = "", role: str = "operator"):
        self._current_username = username
        self._current_role = role
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.unbind("<Return>")
        self.current_frame = PlannerDashboard(self, username=username, user_role=role)

    def close_app(self):
        # Verifica modificari nesalvate in PlannerDashboard
        if isinstance(self.current_frame, PlannerDashboard):
            if not self.current_frame.confirm_close():
                return
        if self.current_frame is not None:
            try:
                self.current_frame.destroy()
            except (tk.TclError, RuntimeError) as exc:
                log_exception("close_app_frame_destroy", exc)
        self.quit()
        self.destroy()


def run_app():
    try:
        app = ShiftManagerApp()
        app.mainloop()
    except tk.TclError as exc:
        log_exception("run_app_tcl", exc)
        raise RuntimeError(
            "Interfata Tk nu poate fi initializata. Verifica instalarea Tcl/Tk sau ruleaza executabilul generat."
        ) from exc
