from datetime import date, datetime
from pathlib import Path
import tkinter as tk
import tkinter.messagebox as messagebox
from typing import cast

import customtkinter as ctk
from PIL import Image

from logic.app_paths import APP_DIR, ASSETS_DIR, ensure_runtime_file

try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None


PRIMARY_BLUE = ("#0A4D9B", "#4A90E2")
ACCENT_BLUE = "#0067C8"
HOVER_BLUE = "#2E7FD2"
BG_WHITE = ("#EAF2FB", "#121212")
MUTED_TEXT = ("#3F536B", "#A0A0A0")
BODY_TEXT = ("#15304B", "#E0E0E0")
CARD_WHITE = ("#FFFFFF", "#1E1E1E")
PANEL_BG = ("#F2F7FD", "#2A2A2A")
LINE_BLUE = ("#B7D0EB", "#333333")
ENTRY_BG = ("#FFFFFF", "#252525")

DEFAULT_LOGO_PATH = ASSETS_DIR / "autoliv_logo.png"
FALLBACK_USER_LOGO_PATH = APP_DIR / "Autoliv_logo" / "Screenshot_1.png"
APP_ICON_PATH = ASSETS_DIR / "autoliv_app.ico"
APP_ICON_PNG_PATH = ASSETS_DIR / "autoliv_app_icon.png"
ensure_runtime_file("assets/autoliv_logo.png")
ensure_runtime_file("assets/autoliv_app.ico")
ensure_runtime_file("assets/autoliv_app_icon.png")
LOGO_PATH = DEFAULT_LOGO_PATH if DEFAULT_LOGO_PATH.exists() else FALLBACK_USER_LOGO_PATH


class AutolivLogo(ctk.CTkFrame):
    def __init__(self, master, width=220, height=90):
        super().__init__(master, fg_color="transparent", width=width, height=height)
        self.grid_propagate(False)

        if LOGO_PATH.exists():
            image = self._load_prepared_logo(LOGO_PATH)
            image_width, image_height = image.size
            scale = min(width / image_width, height / image_height)
            size = (max(1, int(image_width * scale)), max(1, int(image_height * scale)))
            self.logo_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            ctk.CTkLabel(self, text="", image=self.logo_image).pack(fill="both", expand=True)
            return

        canvas_bg = BG_WHITE[0] if ctk.get_appearance_mode() == "Light" else BG_WHITE[1]
        canvas = tk.Canvas(self, width=width, height=height, bg=canvas_bg, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        primary_blue_color = PRIMARY_BLUE[0] if ctk.get_appearance_mode() == "Light" else PRIMARY_BLUE[1]
        canvas.create_text(12, 18, anchor="nw", text="Autoliv", fill=primary_blue_color, font=("Segoe UI", 34, "bold"))
        canvas.create_rectangle(12, 58, 194, 70, fill=primary_blue_color, outline=primary_blue_color)

    def _load_prepared_logo(self, path: Path):
        image = Image.open(path).convert("RGBA")
        width, height = image.size
        search_height = max(1, int(height * 0.8))
        min_x, min_y = width, search_height
        max_x, max_y = -1, -1

        for y in range(search_height):
            for x in range(width):
                red, green, blue, alpha = cast(tuple[int, int, int, int], image.getpixel((x, y)))
                if alpha and blue > 90 and blue > red + 25 and blue > green + 10:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        if max_x >= min_x and max_y >= min_y:
            image = image.crop((max(0, min_x - 8), max(0, min_y - 6), min(width, max_x + 8), min(height, max_y + 6)))
        return image


class DatePickerDialog(ctk.CTkToplevel):
    def __init__(self, master, initial_date: date):
        super().__init__(master)
        self.title("Selecteaza saptamana")
        self.geometry("320x340")
        self.resizable(False, False)
        self.selected_date = None
        self.configure(fg_color=BG_WHITE)
        self.transient(master)
        self.grab_set()

        if Calendar is not None:
            self.calendar = Calendar(self, selectmode="day", date_pattern="yyyy-mm-dd")
            self.calendar.selection_set(initial_date)
            self.calendar.pack(padx=16, pady=16, fill="both", expand=True)
        else:
            self.calendar = None
            self.date_var = ctk.StringVar(value=initial_date.isoformat())
            ctk.CTkLabel(self, text="tkcalendar nu este instalat.\nIntrodu data din saptamana dorita.", text_color=MUTED_TEXT).pack(
                padx=16, pady=(24, 8)
            )
            ctk.CTkEntry(self, textvariable=self.date_var, width=220).pack(pady=(0, 12))

        ctk.CTkButton(self, text="Foloseste saptamana", command=self.confirm).pack(pady=(0, 16))

    def confirm(self):
        try:
            if self.calendar is not None:
                self.selected_date = datetime.strptime(self.calendar.get_date(), "%Y-%m-%d").date()
            else:
                self.selected_date = datetime.strptime(self.date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Data invalida", "Foloseste formatul YYYY-MM-DD.")
            return
        self.destroy()


def apply_window_icon(window):
    try:
        if APP_ICON_PATH.exists():
            window.iconbitmap(default=str(APP_ICON_PATH))
            return
    except Exception as exc:
        from logic.app_logger import log_warning
        log_warning("apply_window_icon: iconbitmap failed: %s", exc)

    try:
        if APP_ICON_PNG_PATH.exists():
            icon_image = tk.PhotoImage(file=str(APP_ICON_PNG_PATH))
            window._autoliv_icon_image = icon_image
            window.iconphoto(True, icon_image)
    except Exception as exc:
        from logic.app_logger import log_warning
        log_warning("apply_window_icon: iconphoto failed: %s", exc)
