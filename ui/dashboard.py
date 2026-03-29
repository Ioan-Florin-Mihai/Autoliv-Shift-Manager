import tkinter.messagebox as messagebox
import tkinter as tk

import customtkinter as ctk

from logic.app_logger import log_exception
from logic.auth import verify_login
from logic.remote_control import RemoteControlService
from ui.common_ui import AutolivLogo, BG_WHITE, BODY_TEXT, CARD_WHITE, ENTRY_BG, LINE_BLUE, MUTED_TEXT, PANEL_BG, PRIMARY_BLUE, apply_window_icon
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
                     font=ctk.CTkFont(size=13)).grid(row=7, column=0), padx=32, pady=(4, 24))

    def login(self):
        try:
            is_valid = verify_login(self.username_var.get().strip(), self.password_var.get())
        except Exception as exc:
            messagebox.showerror("Eroare configurare", str(exc))
            self.status_var.set("Configurarea login-ului este invalida.")
            return
        if not is_valid:
            self.status_var.set("Username sau parola invalida.")
            messagebox.showerror("Autentificare esuata", "Credentiale invalide.")
            return
        self.on_login_success()

    def _handle_enter_key(self, _event):
        self.login()


class ShiftManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Autoliv Shift Manager")
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

    def show_dashboard(self):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.unbind("<Return>")
        self.current_frame = PlannerDashboard(self, self.remote_service)

    def close_app(self):
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
