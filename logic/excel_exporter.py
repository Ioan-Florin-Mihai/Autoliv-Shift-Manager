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
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from logic.app_logger import log_exception
from logic.app_paths import BUNDLE_DIR, EXPORT_DIR
from logic.schedule_store import DAYS, DEPARTMENT_COLORS, SHIFTS, WEEKEND_DAYS
from logic.version import VERSION


# ── COLOR_MAP — replica exacta a EMPLOYEE_COLOR_PALETTE din UI ──────────────
# cheie → culoare hex fara "#" (format openpyxl)
# Se foloseste cand angajatul NU are o culoare personalizata stocata in celula.
COLOR_MAP = {
    "8h":  "1A1A1A",   # Negru — 8 ore
    "12h": "C0392B",   # Rosu — 12 ore
    "R":   "C0392B",   # Rosu
    "V":   "27AE60",   # Verde
    "P":   "E67E22",   # Portocaliu
    "AL":  "2471A3",   # Albastru inchis
}

# Culoare implicita pentru text fara marcare (negru inchis — lizibil pe fond alb)
DEFAULT_TEXT_COLOR = "1A1A1A"

# Font folosit in tot documentul
FONT_NAME = "Calibri"
COLOR_8H = "1A1A1A"
COLOR_12H = "C0392B"


def _to_argb(hex_color: str | None) -> str:
    """Converteste '#C0392B' sau 'C0392B' → 'FFC0392B' (ARGB opac). Sigur pentru Font(color=...)."""
    if not hex_color:
        return "FF" + DEFAULT_TEXT_COLOR
    cleaned = hex_color.strip().lstrip("#").upper()
    if len(cleaned) == 6 and all(c in "0123456789ABCDEF" for c in cleaned):
        return "FF" + cleaned
    return "FF" + DEFAULT_TEXT_COLOR


def _fill(hex_color: str) -> "PatternFill":
    """PatternFill solid cu alpha FF (complet opac). Evita bug-ul openpyxl cu alpha=00."""
    cleaned = hex_color.strip().lstrip("#").upper()
    return PatternFill("solid", fgColor="FF" + cleaned)


def _hours_label_from_colors(colors: dict | None, employee: str) -> str:
    def _raw_color_for_employee(emp: str):
        raw = colors.get(emp) if isinstance(colors, dict) else None
        if raw:
            return raw
        return next(
            (v for k, v in (colors or {}).items() if isinstance(k, str) and k.casefold() == emp.casefold()),
            None,
        )

    raw = (_raw_color_for_employee(employee) or "").strip().upper().lstrip("#")
    return "12" if raw == COLOR_12H else "8"


def _cell_text_and_color(employees: list[str], colors: dict) -> tuple[str, str]:
    """
    Returneaza (text_celula, culoare_ARGB) pentru o celula din grid.

    Textul: fiecare angajat pe linie noua, prefixat cu '● 8 ' sau '● 12 '.
    Culoarea: daca toti angajatii au aceeasi culoare → acea culoare;
              altfel → negru inchis (DEFAULT_TEXT_COLOR).
    Fara CellRichText — compatibil 100% Excel (fara avertismente de reparare).
    """
    if not employees:
        return "", "FF" + DEFAULT_TEXT_COLOR

    text = "\n".join(f"\u25cf {_hours_label_from_colors(colors, emp)} {emp}" for emp in employees)

    # Colecteaza culorile unice ale angajatilor (case-insensitive lookup)
    unique_colors: set[str] = set()
    for emp in employees:
        raw = None
        if isinstance(colors, dict):
            raw = colors.get(emp)
            if not raw:
                raw = next((v for k, v in colors.items() if isinstance(k, str) and k.casefold() == emp.casefold()), None)
        unique_colors.add(_to_argb(raw))

    # O singura culoare → aplica pe toata celula; mai multe → negru
    color = unique_colors.pop() if len(unique_colors) == 1 else "FF" + DEFAULT_TEXT_COLOR
    return text, color


def _build_employee_rich_text(employees: list[str], colors: dict) -> CellRichText:
    rich_text = CellRichText()
    for index, employee in enumerate(employees):
        hours_label = _hours_label_from_colors(colors, employee)
        line_text = f"\u25cf {hours_label} {employee}"
        line_color = "FF" + (COLOR_12H if hours_label == "12" else COLOR_8H)
        rich_text.append(
            TextBlock(
                InlineFont(rFont=FONT_NAME, b=True, sz=11, color=line_color),
                line_text,
            )
        )
        if index < len(employees) - 1:
            rich_text.append("\n")
    return rich_text


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

        # Auto-detecteaza logo-ul daca nu este furnizat explicit
        if logo_path is None:
            _auto = BUNDLE_DIR / "assets" / "autoliv_logo.png"
            if _auto.exists():
                logo_path = _auto

        week_start  = datetime.strptime(week_record["week_start"], "%Y-%m-%d").date()
        week_label  = week_record["week_label"].replace(" ", "_")
        filename    = f"{current_mode.lower()}_{week_start.isoformat()}_{week_label}.xlsx"
        export_path = EXPORT_DIR / filename

        workbook = Workbook()
        sheet    = workbook.active
        sheet.title = current_mode
        sheet.sheet_view.showGridLines = False

        # ── A3 Landscape, fit-to-page ────────────────────────────────
        sheet.page_setup.orientation = sheet.ORIENTATION_LANDSCAPE
        sheet.page_setup.paperSize   = sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth  = 1
        sheet.page_setup.fitToHeight = 1      # 1 = forteaza o singura pagina A3
        sheet.page_setup.scale       = None   # elimina conflictul cu fitToWidth/Height
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

        # Margini minime A3 (in inch: ~0.5 cm)
        sheet.page_margins = PageMargins(
            left=0.2, right=0.2, top=0.3, bottom=0.3,
            header=0.2, footer=0.2,
        )

        # ── Stiluri comune ───────────────────────────────────────────
        thin   = Side(style="thin",   color="AAAAAA")
        medium = Side(style="medium", color="666666")

        border_thin   = Border(left=thin,   right=thin,   top=thin,   bottom=thin)
        border_dept   = Border(left=medium, right=medium, top=medium, bottom=medium)

        centered     = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell_text_aln = Alignment(horizontal="left", vertical="center", wrap_text=True)
        vertical_aln = Alignment(horizontal="center", vertical="center", text_rotation=90, wrap_text=True)

        # ── Latimi coloane (A3 landscape — 9 coloane, fara coloana goala) ──
        #   Col 1 (A): Departament (text vertical)  — ingust
        #   Col 2 (B): Schimb                       — compact
        #   Col 3-9 (C-I): Luni–Duminica            — maresc sa umple A3
        # Total: ~5+11+7*30 = 226 unitati ≈ A3 landscape cu margini 0.2"
        col_widths = {1: 5, 2: 11, 3: 30, 4: 30, 5: 30, 6: 30, 7: 30, 8: 30, 9: 30}
        for col, width in col_widths.items():
            sheet.column_dimensions[get_column_letter(col)].width = width

        # ── Inaltimi randuri fixe ────────────────────────────────────
        sheet.row_dimensions[1].height = 30
        sheet.row_dimensions[2].height = 30

        # ── Header principal (rand 1-2) — full width A–I ─────────────
        sheet.merge_cells("A1:I2")
        hdr = sheet["A1"]
        hdr.value     = f"Planificare {current_mode.lower()} — {week_record['week_label']}"
        hdr.fill      = _fill("0067C8")
        hdr.font      = Font(name=FONT_NAME, color="FFFFFFFF", bold=True, size=20)
        hdr.alignment = centered

        # Logo suprapus pe banda albastra, ancorat in coltul dreapta (col I)
        if logo_path and logo_path.exists():
            try:
                img        = XLImage(str(logo_path))
                img.width  = 140
                img.height = 50
                sheet.add_image(img, "I1")
            except Exception as exc:
                log_exception("excel_export_logo", exc)

        # ── Rand 3: subtitlu raport (generat, mod, versiune) ───────────
        sheet.row_dimensions[3].height = 18
        sheet.merge_cells("A3:I3")
        sub = sheet["A3"]
        sub.value     = (
            f"Generat: {datetime.now().strftime('%d-%m-%Y %H:%M')}  │  "
            f"Mod: {current_mode}  │  "
            f"v{VERSION}"
        )
        sub.font      = Font(name=FONT_NAME, color="FFFFFFFF", size=9, italic=True)
        sub.fill      = _fill("1A4A80")
        sub.alignment = Alignment(horizontal="left", vertical="center",
                                  indent=1, wrap_text=False)

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
                row_heights.append(max(48, max_emp * 22 + 14))

            total_rows = 1 + len(SHIFTS)  # 1 header + N schimburi

            # Celula departament — merge pe header + toate schimburile
            sheet.merge_cells(
                start_row=current_row,    start_column=1,
                end_row=current_row + total_rows - 1, end_column=1,
            )
            dep_cell           = sheet.cell(current_row, 1)
            dep_cell.value     = department
            dep_cell.fill      = _fill(dep_color)
            dep_cell.font      = Font(name=FONT_NAME, bold=True, size=10)
            dep_cell.alignment = vertical_aln
            dep_cell.border    = border_dept

            # ── Rand header departament (cu zile) ──
            sheet.row_dimensions[current_row].height = 34

            h_shift = sheet.cell(current_row, 2)
            h_shift.value     = "Schimb"
            h_shift.font      = Font(name=FONT_NAME, bold=True, size=10)
            h_shift.fill      = _fill("EAF1FB")
            h_shift.alignment = centered
            h_shift.border    = border_thin

            for col_offset, (day_name, day_idx) in enumerate(DAYS, start=3):
                current_day = start + timedelta(days=day_idx)
                cell_obj    = sheet.cell(current_row, col_offset)
                cell_obj.value = f"{day_name}\n{current_day.strftime('%d-%b-%y')}"
                cell_obj.font  = Font(name=FONT_NAME, bold=True, size=10)
                cell_obj.fill  = _fill("FCE4D6" if day_name in WEEKEND_DAYS else "EAF1FB")
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
                shift_cell.fill      = _fill("F5F5F5")
                shift_cell.border    = border_thin

                # Celule angajati — text multi-linie cu stil unitar, culoare per linie.
                for col_offset, (day_name, _) in enumerate(DAYS, start=3):
                    cell_data  = schedule[day_name][shift]
                    employees  = cell_data.get("employees", [])
                    colors     = cell_data.get("colors", {})

                    text, _ = _cell_text_and_color(employees, colors)

                    value_cell            = sheet.cell(row, col_offset)
                    value_cell.value      = text
                    value_cell.font       = Font(name=FONT_NAME, bold=True, size=11, color="FF" + DEFAULT_TEXT_COLOR)
                    value_cell.alignment  = cell_text_aln
                    value_cell.border     = border_thin
                    # Fond neutru pe toata celula pentru print A3 consistent.
                    value_cell.fill = PatternFill(
                        start_color="FFFFFFFF",
                        end_color="FFFFFFFF",
                        fill_type="solid",
                    )
                    if employees:
                        try:
                            value_cell.value = _build_employee_rich_text(employees, colors)
                        except Exception as exc:
                            # Fallback robust: text simplu integral negru, fara artefacte la print.
                            log_exception("excel_export_rich_text_fallback", exc)
                            value_cell.value = text
                            value_cell.font = Font(name=FONT_NAME, bold=True, size=11, color="FF" + DEFAULT_TEXT_COLOR)

            current_row += total_rows

        # Ingheata pane-urile dupa header si coloana schimb
        sheet.freeze_panes = "C4"

        # Repeta randurile de header (1-3) pe fiecare pagina printata
        sheet.print_title_rows = "1:3"

        # Zona de printare — strict A1 pana la ultima celula cu date (fara coloane goale)
        last_col = get_column_letter(sheet.max_column)
        sheet.print_area = f"A1:{last_col}{sheet.max_row}"

        # ── Footer profesional ───────────────────────────────────────
        sheet.oddFooter.left.text  = "Generated by Autoliv Shift Manager"
        sheet.oddFooter.left.size  = 9
        sheet.oddFooter.right.text = (
            f"Data: {datetime.now().strftime('%Y-%m-%d')}  |  "
            f"Versiune: {VERSION}"
        )
        sheet.oddFooter.right.size = 9
        sheet.oddFooter.center.text = "Pagina &P din &N"
        sheet.oddFooter.center.size = 9

        workbook.save(export_path)
        return export_path
