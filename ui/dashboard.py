import tkinter as tk
import tkinter.messagebox as messagebox

import customtkinter as ctk

from logic.app_logger import log_exception
from logic.auth import change_password, verify_login_detailed
from logic.remote_control import RemoteControlService
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

ACCENT_BLUE = "#0067C8"


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master, corner_radius=0)
        self.on_login_success = on_login_success
        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Autentificare necesara.")
        self._build_ui()
        self.winfo_toplevel().bind("<Return>", self._handle_enter_key)

    def _build_ui(self):
        self.pack(fill="both", expand=True)
        self.configure(fg_color=BG_WHITE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Panoul stâng: branding albastru ──
        left = ctk.CTkFrame(self, corner_radius=0, fg_color=("#0A4D9B", "#0A3A7A"))
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        brand = ctk.CTkFrame(left, fg_color="transparent")
        brand.grid(row=0, column=0)
        AutolivLogo(brand, width=340, height=130).pack(pady=(0, 32))
        ctk.CTkLabel(brand, text="Shift Manager", text_color="white",
                     font=ctk.CTkFont(size=38, weight="bold")).pack()
        ctk.CTkLabel(brand, text="Planificare inteligenta a schimburilor", text_color=("#B8D4F4", "#B8D4F4"),
                     font=ctk.CTkFont(size=16)).pack(pady=(10, 0))
        sep = ctk.CTkFrame(brand, height=3, width=200, fg_color=("#4A90E2", "#4A90E2"), corner_radius=2)
        sep.pack(pady=(28, 0))

        # ── Panoul drept: formular ──
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
        ctk.CTkEntry(form, textvariable=self.password_var, placeholder_text="Introdu parola",
                     show="*", width=380, height=48, fg_color=ENTRY_BG, border_width=2,
                     border_color=LINE_BLUE, text_color=BODY_TEXT,
                     font=ctk.CTkFont(size=15)).grid(row=5, column=0, pady=(0, 32))

        ctk.CTkButton(form, text="Autentificare", command=self.login,
                      width=380, height=52, fg_color=PRIMARY_BLUE, hover_color=ACCENT_BLUE,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      corner_radius=12).grid(row=6, column=0, pady=(0, 16))
        ctk.CTkLabel(form, textvariable=self.status_var, text_color=MUTED_TEXT,
                     font=ctk.CTkFont(size=13)).grid(row=7, column=0, padx=32, pady=(4, 24))

    def login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        try:
            ok, msg = verify_login_detailed(username, password)
        except Exception as exc:
            messagebox.showerror("Eroare configurare", str(exc))
            self.status_var.set("Configurarea login-ului este invalida.")
            return
        if not ok:
            self.status_var.set(msg or "Username sau parola invalida.")
            return
        self._logged_in_username = username
        self.on_login_success(username)

    def _handle_enter_key(self, _event):
        self.login()


class ChangePasswordDialog(ctk.CTkToplevel):
    """
    Dialog modal pentru schimbarea parolei utilizatorului curent.
    Apeleaza logic.auth.change_password() — nu acceseaza fisiere direct.
    """

    def __init__(self, master, username: str):
        super().__init__(master)
        self.username  = username
        self.title("Schimba parola")
        self.geometry("420x360")
        self.resizable(False, False)
        self.grab_set()               # modal
        self.lift()
        self.focus_force()
        self._build_ui()

    def _build_ui(self):
        self.configure(fg_color=BG_WHITE)
        pad = {"padx": 32, "pady": 8}

        ctk.CTkLabel(
            self, text="Schimba parola",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY_BLUE,
        ).pack(**pad, pady=(24, 4))

        ctk.CTkLabel(self, text="Parola curenta", text_color=BODY_TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=32)
        self._old_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._old_var, show="*", width=360,
                     fg_color=ENTRY_BG, border_color=LINE_BLUE, border_width=2,
                     text_color=BODY_TEXT).pack(**pad)

        ctk.CTkLabel(self, text="Parola noua (min 8 caractere)", text_color=BODY_TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=32)
        self._new_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._new_var, show="*", width=360,
                     fg_color=ENTRY_BG, border_color=LINE_BLUE, border_width=2,
                     text_color=BODY_TEXT).pack(**pad)

        ctk.CTkLabel(self, text="Confirma parola noua", text_color=BODY_TEXT,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=32)
        self._confirm_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._confirm_var, show="*", width=360,
                     fg_color=ENTRY_BG, border_color=LINE_BLUE, border_width=2,
                     text_color=BODY_TEXT).pack(**pad)

        self._status_var = ctk.StringVar()
        ctk.CTkLabel(self, textvariable=self._status_var, text_color="#C0392B",
                     font=ctk.CTkFont(size=12), wraplength=360).pack(padx=32)

        ctk.CTkButton(
            self, text="Salveaza parola", command=self._submit,
            width=360, height=44, fg_color=PRIMARY_BLUE,
            font=ctk.CTkFont(size=14, weight="bold"), corner_radius=10,
        ).pack(padx=32, pady=(8, 16))

    def _submit(self):
        old     = self._old_var.get()
        new     = self._new_var.get()
        confirm = self._confirm_var.get()

        if not old or not new:
            self._status_var.set("Completeaza toate campurile.")
            return
        if new != confirm:
            self._status_var.set("Parolele noi nu coincid.")
            return
        if new == old:
            self._status_var.set("Parola noua trebuie sa fie diferita de cea curenta.")
            return

        ok, msg = change_password(self.username, old, new)
        if ok:
            messagebox.showinfo("Succes", msg, parent=self)
            self.destroy()
        else:
            self._status_var.set(msg)


class ShiftManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self._current_username: str | None = None
        self.geometry("1620x900")
        self.state("zoomed")
        self.minsize(1320, 760)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_WHITE)
        apply_window_icon(self)
        self.remote_service = RemoteControlService()
        self.current_frame = None
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.show_login()

    def show_login(self):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = LoginFrame(self, self.show_dashboard)

    def show_dashboard(self, username: str = ""):
        self._current_username = username
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.unbind("<Return>")
        self.current_frame = PlannerDashboard(self, self.remote_service, username=username)
        # Schimbare parolă obligatorie la primul login (parola implicită)
        from logic.auth import must_change_password as _must_change
        if _must_change(username):
            self.after(700, lambda: self._prompt_mandatory_password_change(username))

    def _prompt_mandatory_password_change(self, username: str):
        """Afișează avertisment + dialog obligatoriu de schimbare parolă."""
        import tkinter.messagebox as messagebox
        messagebox.showwarning(
            "Schimbare parolă obligatorie",
            "Folosești parola implicită (admin123).\n"
            "Din motive de securitate, trebuie să schimbi parola acum.",
            parent=self,
        )
        ChangePasswordDialog(self, username)

    def open_change_password(self):
        if self._current_username:
            ChangePasswordDialog(self, self._current_username)

    def close_app(self):
        # Verifica modificari nesalvate in PlannerDashboard
        if isinstance(self.current_frame, PlannerDashboard):
            if not self.current_frame.confirm_close():
                return   # utilizatorul a ales Cancel
        if self.current_frame is not None:
            try:
                self.current_frame.destroy()
            except Exception as exc:
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
