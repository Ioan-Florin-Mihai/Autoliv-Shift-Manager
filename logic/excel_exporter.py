# ============================================================
# MODUL: excel_exporter.py - EXPORT EXCEL A3
# ============================================================
#
# Responsabil cu:
#   - Generarea fisierelor .xlsx pentru planificarea saptamanala
#   - Formatare A3 landscape cu logo, culori departament, grid
#   - Complet independent de UI (testabil izolat)
#
# Utilizare:
#   from logic.excel_exporter import ExcelExporter
#   path = ExcelExporter.export(week_record, current_mode)
# ============================================================

from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from logic.app_logger import log_exception
from logic.app_paths import EXPORT_DIR
from logic.schedule_store import DAYS, DEPARTMENT_COLORS, SHIFTS, WEEKEND_DAYS


class ExcelExporter:
    """Serviciu de export Excel A3 pentru planificarea saptamanala."""

    @staticmethod
    def export(
        week_record: dict,
        current_mode: str,
        logo_path: Path | None = None,
    ) -> Path:
        """
        Genereaza fisierul Excel A3 pentru modul si saptamana date.
        Returneaza calea fisierului exportat.
        Poate fi apelat din background thread (nu acceseaza UI).

        :param week_record: dict cu structura saptamanii (din ScheduleStore)
        :param current_mode: "Magazie" sau "Bucle"
        :param logo_path: cale optionala catre logo PNG
        :raises Exception: orice eroare de I/O sau openpyxl
        """
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        week_start = datetime.strptime(week_record["week_start"], "%Y-%m-%d").date()
        week_label = week_record["week_label"].replace(" ", "_")
        filename   = f"{current_mode.lower()}_{week_start.isoformat()}_{week_label}.xlsx"
        export_path = EXPORT_DIR / filename

        workbook = Workbook()
        sheet    = workbook.active
        sheet.title = current_mode
        sheet.sheet_view.showGridLines = False
        sheet.page_setup.orientation = "landscape"
        if hasattr(sheet.page_setup, "PAPERSIZE_A3"):
            sheet.page_setup.paperSize = sheet.page_setup.PAPERSIZE_A3
        else:
            sheet.page_setup.paperSize = 8  # A3 = 8 in openpyxl enum
        sheet.page_setup.fitToWidth  = 1
        sheet.page_setup.fitToHeight = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

        thin   = Side(style="thin", color="666666")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        centered     = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_aligned = Alignment(horizontal="left",   vertical="top",    wrap_text=True)
        vertical_aln = Alignment(horizontal="center", vertical="center", text_rotation=90, wrap_text=True)

        # ── Header ──────────────────────────────────────────────────
        sheet.merge_cells("A1:I2")
        header_cell = sheet["A1"]
        header_cell.value     = f"Planificare {current_mode.lower()} : {week_record['week_label']}"
        header_cell.fill      = PatternFill("solid", fgColor="4F81BD")
        header_cell.font      = Font(color="FFFFFF", bold=True, size=18)
        header_cell.alignment = centered

        sheet.merge_cells("J1:J2")
        logo_cell = sheet["J1"]
        logo_cell.value     = "Autoliv"
        logo_cell.fill      = PatternFill("solid", fgColor="4F81BD")
        logo_cell.font      = Font(color="FFFFFF", bold=True, size=12)
        logo_cell.alignment = centered

        # Logo PNG opptional
        if logo_path and logo_path.exists():
            try:
                img        = XLImage(str(logo_path))
                img.width  = 120
                img.height = 38
                sheet.add_image(img, "A1")
            except Exception as exc:
                log_exception("excel_export_logo", exc)

        # ── Latimi coloane ───────────────────────────────────────────
        for col, width in {1: 20, 2: 10, 3: 17, 4: 17, 5: 17, 6: 17, 7: 17, 8: 17, 9: 17, 10: 11}.items():
            sheet.column_dimensions[get_column_letter(col)].width = width

        # ── Date header row (row 3) ──────────────────────────────────
        start       = datetime.strptime(week_record["week_start"], "%Y-%m-%d").date()
        mode_record = week_record["modes"][current_mode]

        current_row = 4
        for department in mode_record["departments"]:
            schedule = mode_record["schedule"][department]

            # Celula departament (merge pe 4 randuri: header + 3 schimburi)
            sheet.merge_cells(
                start_row=current_row, start_column=1,
                end_row=current_row + 3, end_column=1,
            )
            dep_cell           = sheet.cell(current_row, 1)
            dep_cell.value     = department
            dep_cell.fill      = PatternFill("solid", fgColor=DEPARTMENT_COLORS.get(department, "D9A35F"))
            dep_cell.font      = Font(bold=True)
            dep_cell.alignment = vertical_aln
            dep_cell.border    = border

            # Coloana "Schimbul"
            h_cell           = sheet.cell(current_row, 2)
            h_cell.value     = "Schimbul"
            h_cell.font      = Font(bold=True)
            h_cell.fill      = PatternFill("solid", fgColor="F2F2F2")
            h_cell.alignment = centered
            h_cell.border    = border

            # Zile in header
            for offset, (day_name, _) in enumerate(DAYS, start=3):
                cell_obj       = sheet.cell(current_row, offset)
                current_day    = start + timedelta(days=offset - 3)
                cell_obj.value = f"{day_name}\n{current_day.strftime('%d-%b-%y')}"
                cell_obj.font  = Font(bold=True)
                cell_obj.fill  = PatternFill(
                    "solid", fgColor="F2F2F2" if day_name not in WEEKEND_DAYS else "FCE4D6"
                )
                cell_obj.alignment = centered
                cell_obj.border    = border

            # Randuri schimburi
            for shift_index, shift in enumerate(SHIFTS, start=1):
                row = current_row + shift_index
                sheet.row_dimensions[row].height = 40

                shift_cell           = sheet.cell(row, 2)
                shift_cell.value     = shift
                shift_cell.font      = Font(bold=True)
                shift_cell.alignment = centered
                shift_cell.fill      = PatternFill("solid", fgColor="FAFAFA")
                shift_cell.border    = border

                for offset, (day_name, _) in enumerate(DAYS, start=3):
                    value_cell = sheet.cell(row, offset)
                    cell_employees = schedule[day_name][shift]["employees"]
                    value_cell.value     = "\n".join(cell_employees)
                    value_cell.alignment = left_aligned
                    value_cell.border    = border
                    if cell_employees:
                        value_cell.font = Font(bold=True, size=11)
                    if day_name in WEEKEND_DAYS:
                        value_cell.fill = PatternFill("solid", fgColor="FFF7ED")

            sheet.row_dimensions[current_row].height = 46
            current_row += 5

        sheet.freeze_panes = "C5"
        workbook.save(export_path)
        return export_path
