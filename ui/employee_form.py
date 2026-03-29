import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime

import customtkinter as ctk

from logic.personnel_manager import PersonnelManager
from ui.common_ui import PRIMARY_BLUE, CARD_WHITE, BG_WHITE, LINE_BLUE, ENTRY_BG, BODY_TEXT, MUTED_TEXT, PANEL_BG, ACCENT_BLUE, HOVER_BLUE

class EmployeeRegistrationWindow(ctk.CTkToplevel):
    def __init__(self, master, on_employee_added=None):
        super().__init__(master)
        self.title("Gestionare Personal (Angajat Nou)")
        self.geometry("680x800")
        self.minsize(680, 700)
        self.configure(fg_color=BG_WHITE)
        self.transient(master)
        self.grab_set()

        self.on_employee_added = on_employee_added
        self.personnel_manager = PersonnelManager()

        self._build_ui()
        self.auto_load_list()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)

        # Containerul de formular
        form_frame = ctk.CTkFrame(main_container, fg_color=CARD_WHITE, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        form_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form_frame, text="Inregistrare Angajat", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 15))

        # 1. Auto completare dată
        # Data în sine
        ctk.CTkLabel(form_frame, text="Data Inregistrarii:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=1, column=0, sticky="w", padx=20, pady=8)
        self.data_label_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ctk.CTkLabel(form_frame, textvariable=self.data_label_var, text_color=BODY_TEXT, font=ctk.CTkFont(size=14)).grid(row=1, column=1, sticky="w", padx=10, pady=8)

        # Nume & Prenume
        ctk.CTkLabel(form_frame, text="Nume:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, sticky="w", padx=20, pady=8)
        self.nume_var = ctk.StringVar()
        self.nume_entry = ctk.CTkEntry(form_frame, textvariable=self.nume_var, placeholder_text="Ex: Popescu", width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.nume_entry.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(form_frame, text="Prenume:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=3, column=0, sticky="w", padx=20, pady=8)
        self.prenume_var = ctk.StringVar()
        self.prenume_entry = ctk.CTkEntry(form_frame, textvariable=self.prenume_var, placeholder_text="Ex: Ion", width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.prenume_entry.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        # 2. Dropdown pentru departament
        ctk.CTkLabel(form_frame, text="Departament:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, sticky="w", padx=20, pady=8)
        self.departament_var = ctk.StringVar(value="Eroare")
        self.departament_cb = ctk.CTkComboBox(form_frame, variable=self.departament_var, values=["Buclă", "Finite", "Asamblare"], width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT, state="readonly")
        self.departament_cb.set("Buclă") 
        self.departament_cb.grid(row=4, column=1, sticky="w", padx=10, pady=8)

        # 3. Auto setare ore după contract
        ctk.CTkLabel(form_frame, text="Contract (ore/zi):", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=5, column=0, sticky="w", padx=20, pady=8)
        self.contract_var = ctk.StringVar(value="8")
        self.contract_cb = ctk.CTkComboBox(form_frame, variable=self.contract_var, values=["8", "12"], width=300, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT, state="readonly", command=self.on_contract_changed)
        self.contract_cb.grid(row=5, column=1, sticky="w", padx=10, pady=8)
        self.contract_cb.set("8")

        # Câmpul readonly 'Ore Setate', disabled for manual editing as required
        ctk.CTkLabel(form_frame, text="Ore alocate:", text_color=MUTED_TEXT, font=ctk.CTkFont(size=14, weight="bold")).grid(row=6, column=0, sticky="w", padx=20, pady=8)
        self.ore_var = ctk.StringVar(value="8")
        self.ore_entry = ctk.CTkEntry(form_frame, textvariable=self.ore_var, width=100, fg_color="#E0E0E0", border_color=LINE_BLUE, text_color=BODY_TEXT, state="readonly")
        self.ore_entry.grid(row=6, column=1, sticky="w", padx=10, pady=8)

        # 4. Activare automată Split Shift
        self.split_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        self.split_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        self.split_frame.grid_columnconfigure((0,1,2,3), weight=1)

        ctk.CTkLabel(self.split_frame, text="Split 1 (ore):", text_color=MUTED_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="e", padx=10)
        self.split_1_var = ctk.StringVar()
        self.split_1_entry = ctk.CTkEntry(self.split_frame, textvariable=self.split_1_var, width=100, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.split_1_entry.grid(row=0, column=1, sticky="w", padx=10)

        ctk.CTkLabel(self.split_frame, text="Split 2 (ore):", text_color=MUTED_TEXT, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=2, sticky="e", padx=10)
        self.split_2_var = ctk.StringVar()
        self.split_2_entry = ctk.CTkEntry(self.split_frame, textvariable=self.split_2_var, width=100, fg_color=ENTRY_BG, border_color=LINE_BLUE, text_color=BODY_TEXT)
        self.split_2_entry.grid(row=0, column=3, sticky="w", padx=10)
        
        # Ascunzi la initializare decat daca era setat pe 12 implicit
        self.split_frame.grid_remove()

        # Salveaza
        self.btn_salveaza = ctk.CTkButton(form_frame, text="Salvează Angajat", font=ctk.CTkFont(size=15, weight="bold"), height=42, fg_color=PRIMARY_BLUE, hover_color=ACCENT_BLUE, command=self.save_employee)
        self.btn_salveaza.grid(row=8, column=0, columnspan=2, pady=20, padx=20, sticky="ew")

        # 8. Auto încărcare la start -> UI List Frame for cache.json entries
        list_container = ctk.CTkFrame(main_container, fg_color=CARD_WHITE, corner_radius=14, border_width=1, border_color=LINE_BLUE)
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.grid_rowconfigure(1, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_container, text="Angajați Recenți (cache.json)", text_color=PRIMARY_BLUE, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))
        
        self.records_scroll = ctk.CTkScrollableFrame(list_container, fg_color=PANEL_BG, corner_radius=10)
        self.records_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

    def on_contract_changed(self, choice):
        # 3. Auto setare ore după contract
        self.ore_var.set(choice)
        
        # 4. Activare automată Split Shift
        if choice == "12":
            self.split_frame.grid()
        else:
            self.split_frame.grid_remove()
            self.split_1_var.set("")
            self.split_2_var.set("")

    def save_employee(self):
        nume = self.nume_var.get().strip()
        prenume = self.prenume_var.get().strip()
        departament = self.departament_var.get()
        contract_ore = self.contract_var.get()
        ore = self.ore_var.get()

        # 6. Validare input (Câmpuri goale)
        if not nume or not prenume or not departament or not contract_ore:
            messagebox.showerror("Eroare Validare", "Toate câmpurile principale sunt obligatorii.")
            return

        try:
            ore_num = int(ore)
        except ValueError:
            messagebox.showerror("Eroare Validare", "Orele trebuie să fie un număr valid.")
            return

        if ore_num > 12:
            messagebox.showerror("Eroare Validare", "Orele nu pot depăși valoarea de 12.")
            return

        split_1_val = 0
        split_2_val = 0
        # Validare Split Shift 
        if contract_ore == "12":
            s1 = self.split_1_var.get().strip()
            s2 = self.split_2_var.get().strip()
            if not s1 or not s2:
                messagebox.showerror("Eroare Validare", "Pentru contract de 12 ore trebuie să completați ambele splituri.")
                return
            try:
                split_1_val = int(s1)
                split_2_val = int(s2)
            except ValueError:
                messagebox.showerror("Eroare Validare", "Valorile split trebuie să fie numere.")
                return
            
            if split_1_val + split_2_val != 12:
                messagebox.showerror("Eroare Validare", "Suma spliturilor trebuie să fie exact 12 ore.")
                return

        # 9. Prevenire duplicate
        if self.personnel_manager.is_duplicate(nume, prenume):
            messagebox.showwarning("Inregistrare Duplicata", "Acest nume și prenume există deja în baza de date.")
            return

        data_curenta = self.data_label_var.get()
        new_record = {
            "nume": nume,
            "prenume": prenume,
            "departament": departament,
            "contract": contract_ore,
            "ore": ore_num,
            "split_1": split_1_val,
            "split_2": split_2_val,
            "data_adaugare": data_curenta
        }

        # 7. Auto salvare JSON
        success = self.personnel_manager.add_record(new_record)

        if success:
            # 10. Mesaje UX - "Salvat cu succes"
            messagebox.showinfo("Succes", "Salvat cu cerere.")
            if self.on_employee_added:
                # Callback to notify parent (like PlannerDashboard) to sync its autocomplete
                self.on_employee_added(f"{nume} {prenume}")
            
            # 5. Reset automat formular
            self.reset_form()
            # Reload display
            self.auto_load_list()
        else:
            messagebox.showerror("Eroare", "Angajatul nu a putut fi salvat (posibil duplicat intern).")

    def reset_form(self):
        # resetează câmpurile
        self.nume_var.set("")
        self.prenume_var.set("")
        
        # resetează dropdown-urile
        self.departament_var.set("Buclă")
        self.contract_cb.set("8")
        
        # setează automat ora înapoi
        self.ore_var.set("8")
        self.data_label_var.set(datetime.now().strftime("%Y-%m-%d"))
        
        # ascunde split fields
        self.split_frame.grid_remove()
        self.split_1_var.set("")
        self.split_2_var.set("")

    def auto_load_list(self):
        # 8. Auto încărcare la start -> afișează lista în UI
        # Sterge widget-urile existente
        for widget in self.records_scroll.winfo_children():
            widget.destroy()
        
        records = self.personnel_manager.get_all()
        if not records:
            ctk.CTkLabel(self.records_scroll, text="Nu există angajați înregistrați.", text_color=MUTED_TEXT, font=ctk.CTkFont(size=13, italic=True)).pack(pady=20)
            return

        # Afiseaza istoricul
        for p in reversed(records):
            item_frame = ctk.CTkFrame(self.records_scroll, fg_color="#FFFFFF", border_color=LINE_BLUE, border_width=1, corner_radius=8)
            item_frame.pack(fill="x", padx=4, pady=4)
            
            full_name = f"{p.get('nume','')} {p.get('prenume','')}".strip()
            dep = p.get('departament', 'N/A')
            c_ore = p.get('contract', 'N/A')
            data = p.get('data_adaugare', 'N/A')

            ctk.CTkLabel(item_frame, text=f"👤 {full_name} | DP: {dep} | Contract: {c_ore} ore", font=ctk.CTkFont(size=14, weight="bold"), text_color=PRIMARY_BLUE).pack(side="left", padx=10, pady=10)
            ctk.CTkLabel(item_frame, text=f"Adaugat: {data}", font=ctk.CTkFont(size=12), text_color=MUTED_TEXT).pack(side="right", padx=10, pady=10)
