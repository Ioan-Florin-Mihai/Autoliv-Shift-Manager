import tkinter.messagebox as messagebox
import tkinter as tk

import customtkinter as ctk

from logic.app_logger import log_exception
from logic.remote_control import RemoteControlService
from ui.common_ui import AutolivLogo, BG_WHITE, BODY_TEXT, CARD_WHITE, LINE_BLUE, MUTED_TEXT, PANEL_BG, PRIMARY_BLUE, apply_window_icon


ACCENT_BLUE = "#0067C8"
BLOCK_RED = "#C0392B"


class RemoteAdminApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Autoliv Remote Control")
        self.geometry("760x520")
        self.minsize(700, 480)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_WHITE)
        apply_window_icon(self)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.service = RemoteControlService()
        self.status_var = ctk.StringVar(value="Verific statusul remote...")
        self.info_var = ctk.StringVar(value="")

        self._build_ui()
        self.refresh_status()

    def _build_ui(self):
        shell = ctk.CTkFrame(self, fg_color=CARD_WHITE, corner_radius=18, border_width=1, border_color=LINE_BLUE)
        shell.pack(fill="both", expand=True, padx=24, pady=24)
        shell.grid_columnconfigure(0, weight=1)

        AutolivLogo(shell, width=260, height=100).pack(pady=(22, 8))

        ctk.CTkLabel(shell, text="Control Remote Aplicatie", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=28, weight="bold")).pack()
        ctk.CTkLabel(shell, text="Butoane pentru blocare sau reactivare din Firebase", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14)).pack(pady=(6, 20))

        status_box = ctk.CTkFrame(shell, fg_color=PANEL_BG, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        status_box.pack(fill="x", padx=24, pady=(0, 18))
        ctk.CTkLabel(status_box, text="Status curent", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(status_box, textvariable=self.status_var, text_color=BODY_TEXT, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16)
        ctk.CTkLabel(status_box, textvariable=self.info_var, text_color=MUTED_TEXT, justify="left").pack(anchor="w", padx=16, pady=(8, 14))

        button_row = ctk.CTkFrame(shell, fg_color="transparent")
        button_row.pack(fill="x", padx=24, pady=(0, 16))
        button_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(button_row, text="Refresh", command=self.refresh_status, fg_color=PRIMARY_BLUE, height=42).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(button_row, text="Activeaza", command=lambda: self.change_status("active"), fg_color=ACCENT_BLUE, height=42).grid(row=0, column=1, sticky="ew", padx=6)
        ctk.CTkButton(button_row, text="Blocheaza", command=lambda: self.change_status("blocked"), fg_color=BLOCK_RED, hover_color="#A93226", height=42).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        note = (
            "Daca aplicatia de pe stick are Firebase activat, statusul blocked o opreste la urmatoarea verificare.\n"
            "Daca dispozitivul nu mai are internet, se va inchide dupa timeout-ul configurat."
        )
        ctk.CTkLabel(shell, text=note, text_color=MUTED_TEXT, justify="left").pack(anchor="w", padx=24, pady=(8, 0))

    def refresh_status(self):
        try:
            status = self.service.get_status()
        except Exception as exc:
            self.status_var.set("Nu pot citi statusul")
            self.info_var.set(str(exc))
            return

        if status == "firebase_disabled":
            self.status_var.set("Firebase dezactivat")
            self.info_var.set("Activeaza firebase_enabled si completeaza datele din remote_config.json.")
            return

        self.status_var.set(f"Status remote: {status}")
        self.info_var.set(f"Path status: {self.service.config['status_path']}")

    def change_status(self, status: str):
        try:
            self.service.set_status(status)
        except Exception as exc:
            messagebox.showerror("Eroare", str(exc))
            return

        self.refresh_status()
        messagebox.showinfo("Confirmare", f"Statusul a fost schimbat in {status}.")

    def close_app(self):
        self.quit()
        self.destroy()


def run_remote_admin():
    try:
        app = RemoteAdminApp()
        app.mainloop()
    except tk.TclError as exc:
        log_exception("run_remote_admin_tcl", exc)
        raise RuntimeError(
            "Interfata Tk nu poate fi initializata. Verifica instalarea Tcl/Tk sau ruleaza executabilul generat."
        ) from exc
