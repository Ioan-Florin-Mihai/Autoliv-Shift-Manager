# ============================================================
# MODUL: excel_exporter.py - EXPORT EXCEL A3 WYSIWYG
# ============================================================
#
# Responsabil cu:
#   - Generarea fisierelor .xlsx pentru planificarea saptamanala
#   - Export WYSIWYG: culorile angajatilor din UI sunt pastrate exact
#   - Formatare A3 landscape, print-ready, fara taieri
#   - Complet independent de UI (testabil izolat)
#
# Utilizare:
#   from logic.excel_exporter import ExcelExporter
#   path = ExcelExporter.export(week_record, current_mode)
# ============================================================

from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock, InlineFont
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from logic.app_logger import log_exception
from logic.app_paths import EXPORT_DIR
from logic.schedule_store import DAYS, DEPARTMENT_COLORS, SHIFTS, WEEKEND_DAYS


# ── COLOR_MAP — replica exacta a EMPLOYEE_COLOR_PALETTE din UI ──────────────
# cheie → culoare hex fara "#" (format openpyxl)
# Se foloseste cand angajatul NU are o culoare personalizata stocata in celula.
COLOR_MAP = {
    "8h":  "1A1A1A",   # Negru — 8 ore
    "12h": "7B3FC4",   # Violet — 12 ore
    "R":   "C0392B",   # Rosu
    "V":   "27AE60",   # Verde
    "P":   "E67E22",   # Portocaliu
    "AL":  "2471A3",   # Albastru inchis
}

# Culoare implicita pentru text fara marcare (negru inchis — lizibil pe fond alb)
DEFAULT_TEXT_COLOR = "1A1A1A"

# Font folosit in tot documentul
FONT_NAME = "Calibri"


def _hex_to_openpyxl(hex_color: str | None) -> str:
    """
    Converteste "  #C0392B  " → "FFC0392B" (ARGB, alpha=FF = opac 100%).
    openpyxl interpreteaza 6 caractere ca RGB cu alpha=00 (transparent),
    deci trebuie adaugat prefixul "FF" pentru culori complet opace.
    Returneaza DEFAULT_TEXT_COLOR la eroare.
    """
    if not hex_color:
        return "FF" + DEFAULT_TEXT_COLOR
    cleaned = hex_color.strip().lstrip("#").upper()
    if len(cleaned) == 6 and all(c in "0123456789ABCDEF" for c in cleaned):
        return "FF" + cleaned
    return "FF" + DEFAULT_TEXT_COLOR


def _build_rich_cell(employees: list[str], colors: dict) -> CellRichText | str:
    """
    Construieste un CellRichText cu fiecare angajat pe linie noua,
    cu culoarea individuala pastrata din UI.
    Returneaza string simplu daca nu exista angajati.
    """
    if not employees:
        return ""

    rt = CellRichText()
    for i, emp in enumerate(employees):
        # Culoarea stocata in celula (din paleta UI a utilizatorului)
        stored_color = colors.get(emp) if colors else None
        if not stored_color:
            # cautare case-insensitive
            stored_color = next(
                (v for k, v in (colors or {}).items() if k.casefold() == emp.casefold()),
                None,
            )
        hex_color = _hex_to_openpyxl(stored_color)

        font = InlineFont(
            rFont=FONT_NAME,
            b=True,
            sz=11,
            color=hex_color,
        )
        rt.append(TextBlock(font, f"● {emp}"))
        if i < len(employees) - 1:
            rt.append("\n")

    return rt


class ExcelExporter:
    """Serviciu de export Excel A3 WYSIWYG pentru planificarea saptamanala."""

    @staticmethod
    def export(
        week_record: dict,
        current_mode: str,
        logo_path: Path | None = None,
    ) -> Path:
        """
        Genereaza fisierul Excel A3 pentru modul si saptamana date.
        Culorile angajatilor sunt identice cu cele din UI (WYSIWYG).
        Returneaza calea fisierului exportat.

        :param week_record: dict cu structura saptamanii (din ScheduleStore)
        :param current_mode: "Magazie" sau "Bucle"
        :param logo_path: cale optionala catre logo PNG
        """
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        week_start  = datetime.strptime(week_record["week_start"], "%Y-%m-%d").date()
        week_label  = week_record["week_label"].replace(" ", "_")
        filename    = f"{current_mode.lower()}_{week_start.isoformat()}_{week_label}.xlsx"
        export_path = EXPORT_DIR / filename

        workbook = Workbook()
        sheet    = workbook.active
        sheet.title = current_mode
        sheet.sheet_view.showGridLines = False

        # ── A3 Landscape, fit-to-page ────────────────────────────────
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize   = 8      # 8 = A3 in Excel/openpyxl enum
        sheet.page_setup.fitToWidth  = 1
        sheet.page_setup.fitToHeight = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

        # Margini reduse pentru A3 (in inch: ~0.5 cm = 0.2 in)
        sheet.page_margins = PageMargins(
            left=0.28, right=0.28, top=0.35, bottom=0.35,
            header=0.2, footer=0.2,
        )

        # ── Stiluri comune ───────────────────────────────────────────
        thin   = Side(style="thin",   color="AAAAAA")
        medium = Side(style="medium", color="666666")

        border_thin   = Border(left=thin,   right=thin,   top=thin,   bottom=thin)
        border_dept   = Border(left=medium, right=medium, top=medium, bottom=medium)

        centered     = Alignment(horizontal="center", vertical="center", wrap_text=True)
        center_top   = Alignment(horizontal="center", vertical="center", wrap_text=True)
        vertical_aln = Alignment(horizontal="center", vertical="center", text_rotation=90, wrap_text=True)

        # ── Latimi coloane (A3 landscape — ajustate pentru lizibilitate) ──
        #   Col 1: Departament (name vertical)
        #   Col 2: Schimb
        #   Col 3-9: Luni–Duminica
        #   Col 10: Logo / spatiu
        col_widths = {1: 5, 2: 8, 3: 18, 4: 18, 5: 18, 6: 18, 7: 18, 8: 18, 9: 18, 10: 13}
        for col, width in col_widths.items():
            sheet.column_dimensions[get_column_letter(col)].width = width

        # ── Inaltimi randuri fixe ────────────────────────────────────
        sheet.row_dimensions[1].height = 26
        sheet.row_dimensions[2].height = 26

        # ── Header principal (rand 1-2) ──────────────────────────────
        sheet.merge_cells("A1:I2")
        hdr = sheet["A1"]
        hdr.value     = f"Planificare {current_mode.lower()} — {week_record['week_label']}"
        hdr.fill      = PatternFill("solid", fgColor="0067C8")
        hdr.font      = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=18)
        hdr.alignment = centered

        sheet.merge_cells("J1:J2")
        logo_cell = sheet["J1"]
        logo_cell.fill      = PatternFill("solid", fgColor="0067C8")
        logo_cell.font      = Font(name=FONT_NAME, color="FFFFFF", bold=True, size=12)
        logo_cell.alignment = centered

        if logo_path and logo_path.exists():
            try:
                img        = XLImage(str(logo_path))
                img.width  = 120
                img.height = 42
                logo_cell.value = ""
                sheet.add_image(img, "J1")
            except Exception as exc:
                log_exception("excel_export_logo", exc)
                logo_cell.value = "Autoliv"
        else:
            logo_cell.value = "Autoliv"

        # ── Date compacta in header row 3 (rand cu zile saptamanii) ──
        start       = datetime.strptime(week_record["week_start"], "%Y-%m-%d").date()
        mode_record = week_record["modes"][current_mode]

        # ── Corpul tabelului ─────────────────────────────────────────
        current_row = 4
        for department in mode_record["departments"]:
            schedule = mode_record["schedule"][department]
            dep_color = DEPARTMENT_COLORS.get(department, "D9A35F")

            # Calculam inaltimea maxima de rand pentru fiecare schimb
            # (bazata pe cel mai aglomerat cell din schimb)
            row_heights = []
            for shift in SHIFTS:
                max_emp = max(
                    (len(schedule[day_name][shift]["employees"]) for day_name, _ in DAYS),
                    default=0,
                )
                row_heights.append(max(44, max_emp * 20 + 12))

            total_rows = 1 + len(SHIFTS)  # 1 header + N schimburi

            # Celula departament — merge pe header + toate schimburile
            sheet.merge_cells(
                start_row=current_row,    start_column=1,
                end_row=current_row + total_rows - 1, end_column=1,
            )
            dep_cell           = sheet.cell(current_row, 1)
            dep_cell.value     = department
            dep_cell.fill      = PatternFill("solid", fgColor=dep_color)
            dep_cell.font      = Font(name=FONT_NAME, bold=True, size=10)
            dep_cell.alignment = vertical_aln
            dep_cell.border    = border_dept

            # ── Rand header departament (cu zile) ──
            sheet.row_dimensions[current_row].height = 34

            h_shift = sheet.cell(current_row, 2)
            h_shift.value     = "Schimb"
            h_shift.font      = Font(name=FONT_NAME, bold=True, size=10)
            h_shift.fill      = PatternFill("solid", fgColor="EAF1FB")
            h_shift.alignment = centered
            h_shift.border    = border_thin

            for col_offset, (day_name, day_idx) in enumerate(DAYS, start=3):
                current_day = start + timedelta(days=day_idx)
                cell_obj    = sheet.cell(current_row, col_offset)
                cell_obj.value = f"{day_name}\n{current_day.strftime('%d-%b-%y')}"
                cell_obj.font  = Font(name=FONT_NAME, bold=True, size=10)
                cell_obj.fill  = PatternFill(
                    "solid",
                    fgColor="FCE4D6" if day_name in WEEKEND_DAYS else "EAF1FB",
                )
                cell_obj.alignment = centered
                cell_obj.border    = border_thin

            # ── Randuri schimburi ──
            for shift_index, shift in enumerate(SHIFTS):
                row = current_row + 1 + shift_index
                sheet.row_dimensions[row].height = row_heights[shift_index]

                # Celula schimb
                shift_cell           = sheet.cell(row, 2)
                shift_cell.value     = shift
                shift_cell.font      = Font(name=FONT_NAME, bold=True, size=10)
                shift_cell.alignment = centered
                shift_cell.fill      = PatternFill("solid", fgColor="F5F5F5")
                shift_cell.border    = border_thin

                # Celule angajati — WYSIWYG culori
                for col_offset, (day_name, _) in enumerate(DAYS, start=3):
                    cell_data  = schedule[day_name][shift]
                    employees  = cell_data.get("employees", [])
                    colors     = cell_data.get("colors", {})

                    value_cell = sheet.cell(row, col_offset)
                    value_cell.value     = _build_rich_cell(employees, colors)
                    value_cell.alignment = center_top
                    value_cell.border    = border_thin
                    # Fond alb pur — culoarea este DOAR pe text (WYSIWYG)
                    value_cell.fill = PatternFill("solid", fgColor="FFFFFF")

            current_row += total_rows

        # Ingheata pane-urile dupa header si coloana schimb
        sheet.freeze_panes = "C4"

        # Repeta randurile de header (1-3) pe fiecare pagina printata
        sheet.print_title_rows = "1:3"

        workbook.save(export_path)
        return export_path
