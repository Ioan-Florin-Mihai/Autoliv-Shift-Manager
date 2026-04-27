import tkinter.messagebox as messagebox
from datetime import datetime

import customtkinter as ctk

from logic.employee_store import EmployeeStore
from logic.schedule_store import TEMPLATES
from ui.common_ui import (
    ACCENT_BLUE,
    BG_WHITE,
    BODY_TEXT,
    CARD_WHITE,
    ENTRY_BG,
    LINE_BLUE,
    MUTED_TEXT,
    PANEL_BG,
    PRIMARY_BLUE,
)

_DEPT_LIST = list(TEMPLATES["Magazie"]) + list(TEMPLATES["Bucle"])


class EmployeeRegistrationWindow(ctk.CTkToplevel):
    def __init__(self, master, on_employee_added=None, initial_department: str | None = None):
        super().__init__(master)
        self.title("Gestionare Personal (Angajat Nou)")
        self.geometry("680x760")
        self.minsize(680, 640)
        self.configure(fg_color=BG_WHITE)
        self.transient(master)
        self.grab_set()

        self.on_employee_added = on_employee_added
        self.employee_store = EmployeeStore()
        self.initial_department = initial_department if initial_department in _DEPT_LIST else _DEPT_LIST[0]

        self._build_ui()
        self.auto_load_list()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)

        form_frame = ctk.CTkFrame(main_container, fg_color=CARD_WHITE, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        form_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form_frame, text="Inregistrare Angajat", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 15))

        ctk.CTkLabel(form_frame, text="Data Inregistrarii:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=1, column=0, sticky="w", padx=20, pady=8)
        self.data_label_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ctk.CTkLabel(form_frame, textvariable=self.data_label_var, text_color=BODY_TEXT, font=ctk.CTkFont(size=14)).grid(row=1, column=1, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(form_frame, text="Nume:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", padx=20, pady=8)
        self.nume_var = ctk.StringVar()
        self.nume_entry = ctk.CTkEntry(form_frame, textvariable=self.nume_var, placeholder_text="Ex: Boatca", width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.nume_entry.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(form_frame, text="Prenume:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, sticky="w", padx=20, pady=8)
        self.prenume_var = ctk.StringVar()
        self.prenume_entry = ctk.CTkEntry(form_frame, textvariable=self.prenume_var, placeholder_text="Ex: D", width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.prenume_entry.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(form_frame, text="Departament:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, sticky="w", padx=20, pady=8)
        self.departament_var = ctk.StringVar(value=self.initial_department)
        self.departament_cb = ctk.CTkComboBox(
            form_frame,
            variable=self.departament_var,
            values=_DEPT_LIST,
            width=300,
            fg_color=ENTRY_BG,
            border_color=LINE_BLUE,
            text_color=BODY_TEXT,
            state="readonly",
        )
        self.departament_cb.set(self.initial_department)
        self.departament_cb.grid(row=4, column=1, sticky="w", padx=10, pady=8)

        self.btn_salveaza = ctk.CTkButton(
            form_frame,
            text="Salveaza Angajat",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            fg_color=PRIMARY_BLUE,
            hover_color=ACCENT_BLUE,
            command=self.save_employee,
        )
        self.btn_salveaza.grid(row=5, column=0, columnspan=2, pady=20, padx=20, sticky="ew")

        list_container = ctk.CTkFrame(main_container, fg_color=CARD_WHITE, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.grid_rowconfigure(1, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_container, text="Angajati Recenți", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        self.records_scroll = ctk.CTkScrollableFrame(list_container, fg_color=PANEL_BG, corner_radius=10)
        self.records_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

    def save_employee(self):
        nume = self.nume_var.get().strip()
        prenume = self.prenume_var.get().strip()
        departament = self.departament_var.get().strip()

        if not nume or not prenume or not departament:
            messagebox.showerror("Eroare Validare", "Nume, prenume si departament sunt obligatorii.")
            return

        full_name = f"{nume} {prenume}".strip()
        existing_departments = self.employee_store.get_department_map()
        existing_key = next((name for name in existing_departments if name.casefold() == full_name.casefold()), None)
        if existing_key is not None:
            confirm = messagebox.askyesno(
                "Actualizare departament",
                "Angajatul exista deja. Actualizez departamentul principal?",
                parent=self,
            )
            if not confirm:
                return
            self.employee_store.upsert_profile(nume, prenume, departament)
            messagebox.showinfo("Succes", "Departamentul principal a fost actualizat.", parent=self)
        else:
            self.employee_store.upsert_profile(nume, prenume, departament)
            messagebox.showinfo("Succes", "Angajatul a fost salvat.", parent=self)

        if self.on_employee_added:
            self.on_employee_added(full_name)

        self.reset_form()
        self.auto_load_list()

    def reset_form(self):
        self.nume_var.set("")
        self.prenume_var.set("")
        self.departament_var.set(self.initial_department)
        self.data_label_var.set(datetime.now().strftime("%Y-%m-%d"))

    def auto_load_list(self):
        for widget in self.records_scroll.winfo_children():
            widget.destroy()

        records = self.employee_store.get_profiles()
        if not records:
            ctk.CTkLabel(self.records_scroll, text="Nu exista angajati inregistrati.", text_color=MUTED_TEXT, font=ctk.CTkFont(size=13, italic=True)).pack(pady=20)
            return

        for profile in reversed(records):
            item_frame = ctk.CTkFrame(self.records_scroll, fg_color="#FFFFFF", border_color=LINE_BLUE, border_width=1, corner_radius=8)
            item_frame.pack(fill="x", padx=4, pady=4)
            full_name = profile.get("full_name", "")
            dep = profile.get("departament") or "-"
            ctk.CTkLabel(item_frame, text=f"{full_name} | DP: {dep}", font=ctk.CTkFont(size=14, weight="bold"), text_color=PRIMARY_BLUE).pack(side="left", padx=10, pady=10)
            ctk.CTkLabel(item_frame, text=f"Adaugat: {self.data_label_var.get()}", font=ctk.CTkFont(size=12), text_color=MUTED_TEXT).pack(side="right", padx=10, pady=10)
