"""Standalone dialog / tooltip widgets used by the Planner Dashboard."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

# Culori tipuri absență (CO=portocaliu, CM=violet, ABSENT=roșu intens)
ABSENCE_COLORS: dict[str, str] = {
    "CO":     "#F39C12",
    "CM":     "#8E44AD",
    "ABSENT": "#E74C3C",
}
ABSENCE_TYPES: list[str] = list(ABSENCE_COLORS.keys())


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
