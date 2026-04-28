from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from logic.constants import HOURS_12_COLOR
from logic.schedule_store import DAY_NAMES, DEPARTMENT_COLORS, SHIFTS

PDF_SHEET_DEPARTMENTS: dict[str, list[tuple[str, str]]] = {
    "Bucle": [
        ("BUCLA RA+RB", "BUCLA RA + RB"),
        ("BUCLA TA+TB", "BUCLA TA + TB"),
        ("BUCLA 02", "BUCLA 02"),
        ("BUCLA 03", "BUCLA 03"),
        ("BUCLA 04", "BUCLA 04"),
        ("BUCLA 05", "BUCLA 05 + 07"),
        ("Ambalaje", "Ambalaje"),
    ],
    "Magazie": [
        ("Sef schimb", "Sef Schimb"),
        ("Receptii", "Receptii"),
        ("Livrari", "Livrari"),
        ("Etichetare scanare", "Etichetare / Scanare"),
        ("Retragere finite", "Retragere finite"),
        ("Balotare ambalare", "Baloare / Asamblare"),
    ],
}

PDF_DEPARTMENT_COLORS = {
    "sef schimb": "5B9BD5",
    "receptii": "4472C4",
    "livrari": "A9D18E",
    "etichetare scanare": "C9B0D9",
    "retragere finite": "D9A35F",
    "ambalaje": "D99694",
    "balotare ambalare": "BFBFBF",
}

DISPLAY_DAY_NAMES = {
    "Luni": "Luni",
    "Marti": "Marti",
    "Miercuri": "Miercuri",
    "Joi": "Joi",
    "Vineri": "Vineri",
    "Sambata": "Sambata",
    "Duminica": "Duminica",
}


@dataclass(frozen=True)
class PdfExportContext:
    week_start: str
    week_end: str
    week_label: str
    mode: str = ""
    department: str = ""


@dataclass(frozen=True)
class PdfSection:
    mode_name: str
    department: str
    mode_record: dict


def _hours_label_for_employee(cell: dict, employee: str) -> str:
    colors = cell.get("colors", {}) if isinstance(cell, dict) else {}
    if not isinstance(colors, dict):
        return "8h"
    for key, value in colors.items():
        if isinstance(key, str) and key.casefold() == employee.casefold():
            if str(value or "").strip().upper().lstrip("#") == HOURS_12_COLOR:
                return "12h"
            return "8h"
    return "8h"


def _safe_cell(mode_record: dict, department: str, day_name: str, shift: str) -> dict:
    try:
        cell = mode_record["schedule"][department][day_name][shift]
    except (KeyError, TypeError):
        return {"employees": [], "colors": {}}
    if not isinstance(cell, dict):
        return {"employees": [], "colors": {}}
    employees = cell.get("employees", [])
    colors = cell.get("colors", {})
    return {
        "employees": employees if isinstance(employees, list) else [],
        "colors": colors if isinstance(colors, dict) else {},
    }


def _parse_week_start(week_start: str) -> date | None:
    try:
        return date.fromisoformat(str(week_start))
    except ValueError:
        return None


def _day_date_labels(week_start: str) -> list[tuple[str, str]]:
    base = _parse_week_start(week_start)
    if base is None:
        return [(day, "") for day in DAY_NAMES]

    def fmt(current_date: date) -> str:
        month = current_date.strftime("%b").lower()
        month_map = {
            "jan": "ian",
            "feb": "feb",
            "mar": "mar",
            "apr": "apr",
            "may": "mai",
            "jun": "iun",
            "jul": "iul",
            "aug": "aug",
            "sep": "sep",
            "oct": "oct",
            "nov": "nov",
            "dec": "dec",
        }
        return f"{current_date.day}-{month_map.get(month, month)}.-{current_date.strftime('%y')}"

    return [(day_name, fmt(base + timedelta(days=offset))) for offset, day_name in enumerate(DAY_NAMES)]


def _iter_export_departments(modes: dict) -> list[tuple[str, dict, str]]:
    result: list[tuple[str, dict, str]] = []
    if not isinstance(modes, dict):
        return result
    for mode_name, mode_record in modes.items():
        if not isinstance(mode_record, dict):
            continue
        departments = mode_record.get("departments", [])
        if not isinstance(departments, list):
            continue
        for department in departments:
            if isinstance(department, str) and department.strip():
                result.append((str(mode_name), mode_record, department))
    return result


def _build_export_sections(
    week_record: dict,
    *,
    mode_name: str | None = None,
    department: str | None = None,
) -> list[PdfSection]:
    modes = week_record.get("modes", {}) if isinstance(week_record, dict) else {}
    sections: list[PdfSection] = []
    for found_mode, mode_record, found_department in _iter_export_departments(modes):
        if mode_name and found_mode != mode_name:
            continue
        if department and found_department != department:
            continue
        sections.append(PdfSection(mode_name=found_mode, department=found_department, mode_record=mode_record))
    return sections


def _register_font_family():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return "Helvetica", "Helvetica-Bold"

    regular = "Helvetica"
    bold = "Helvetica-Bold"
    try:
        segoe = Path(r"C:\Windows\Fonts\segoeui.ttf")
        segoe_bold = Path(r"C:\Windows\Fonts\segoeuib.ttf")
        if segoe.exists():
            pdfmetrics.registerFont(TTFont("ASM", str(segoe)))
            regular = "ASM"
        if segoe_bold.exists():
            pdfmetrics.registerFont(TTFont("ASM-B", str(segoe_bold)))
            bold = "ASM-B"
        elif regular == "ASM":
            bold = "ASM"
    except (OSError, RuntimeError, ValueError):
        return "Helvetica", "Helvetica-Bold"
    return regular, bold


def _hex_to_rgb(color: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[index:index + 2], 16) / 255.0 for index in (0, 2, 4))
    except ValueError:
        return fallback


def _section_palette(section: PdfSection) -> dict[str, tuple[float, float, float]]:
    fallback = (0.85, 0.70, 0.34) if section.mode_name.casefold() == "bucle" else (0.42, 0.60, 0.86)
    accent = _hex_to_rgb(DEPARTMENT_COLORS.get(section.department, ""), fallback)
    return {
        "accent": accent,
        "grid": (0.52, 0.52, 0.52),
        "header_fill": (0.97, 0.97, 0.97),
        "body_fill": (1.0, 1.0, 1.0),
        "weekend_fill": (0.992, 0.990, 0.975),
    }


def _split_text_to_width(text: str, max_width: float, font_name: str, font_size: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return []
    words = clean.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _trim_line_to_width(text: str, max_width: float, font_name: str, font_size: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    value = str(text or "").strip()
    if not value:
        return ""
    if stringWidth(value, font_name, font_size) <= max_width:
        return value
    suffix = "..."
    while value and stringWidth(f"{value}{suffix}", font_name, font_size) > max_width:
        value = value[:-1]
    return f"{value}{suffix}" if value else suffix


def _build_cell_lines(cell: dict, font_name: str, font_size: float, max_width: float, max_lines: int) -> list[str]:
    employees = [employee for employee in cell.get("employees", []) if isinstance(employee, str) and employee.strip()]
    if not employees:
        return ["-"]

    lines: list[str] = []
    hidden = 0
    for employee in employees:
        hours = _hours_label_for_employee(cell, employee)
        entry = f"{employee}/{hours}"
        wrapped = _split_text_to_width(entry, max_width, font_name, font_size) or [entry]
        for piece in wrapped:
            if len(lines) >= max_lines:
                hidden += 1
                continue
            lines.append(_trim_line_to_width(piece, max_width, font_name, font_size))
        if len(lines) >= max_lines and employee != employees[-1]:
            hidden += len(employees) - employees.index(employee) - 1
            break

    if hidden > 0:
        if len(lines) >= max_lines:
            lines = lines[: max_lines - 1]
        lines.append(f"+{hidden}")
    return lines[:max_lines]


def _page_geometry(page_size: tuple[float, float]) -> dict[str, float]:
    from reportlab.lib.units import mm

    page_width, page_height = page_size
    margin_x = 7 * mm
    margin_y = 7 * mm
    right_band = 13 * mm
    gap_to_band = 3 * mm
    inter_section_gap = 1.6 * mm
    title_height = 12 * mm
    usable_width = page_width - margin_x - right_band - gap_to_band - margin_x
    usable_height = page_height - (2 * margin_y) - title_height
    return {
        "page_width": page_width,
        "page_height": page_height,
        "margin_x": margin_x,
        "margin_y": margin_y,
        "right_band": right_band,
        "gap_to_band": gap_to_band,
        "title_height": title_height,
        "usable_width": usable_width,
        "usable_height": usable_height,
        "inter_section_gap": inter_section_gap,
        "content_x": margin_x,
        "content_y": margin_y,
        "content_top": page_height - margin_y - title_height,
        "content_bottom": margin_y,
    }


def _layout_positions(section_count: int, geometry: dict[str, float]) -> list[tuple[int, float, float]]:
    max_columns_per_page = 8
    positions: list[tuple[int, float, float]] = []
    remaining = section_count
    page_index = 0
    while remaining > 0:
        columns_this_page = min(max_columns_per_page, remaining)
        block_width = (
            geometry["usable_width"] - ((columns_this_page - 1) * geometry["inter_section_gap"])
        ) / columns_this_page
        for column_index in range(columns_this_page):
            x = geometry["content_x"] + column_index * (block_width + geometry["inter_section_gap"])
            positions.append((page_index, x, geometry["content_top"]))
        remaining -= columns_this_page
        page_index += 1
    return positions


def _draw_rotated_center_text(canvas, text: str, center_x: float, center_y: float, angle: float, font_name: str, font_size: float, fill_color: tuple[float, float, float]) -> None:
    canvas.saveState()
    canvas.translate(center_x, center_y)
    canvas.rotate(angle)
    canvas.setFillColorRGB(*fill_color)
    canvas.setFont(font_name, font_size)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()


def _draw_page_header(canvas, ctx: PdfExportContext, geometry: dict[str, float], regular_font: str, bold_font: str, page_no: int) -> None:
    width = geometry["page_width"]
    height = geometry["page_height"]
    right_x = width - geometry["margin_x"] - geometry["right_band"]

    canvas.setFillColorRGB(0.33, 0.45, 0.74)
    canvas.rect(right_x, geometry["margin_y"], geometry["right_band"], height - (2 * geometry["margin_y"]), stroke=0, fill=1)

    _draw_rotated_center_text(
        canvas,
        f"Planificare magazie : {ctx.week_label or 'Saptamana'}",
        right_x + (geometry["right_band"] / 2.0),
        height / 2.0,
        -90,
        bold_font,
        12.5,
        (1, 1, 1),
    )
    _draw_rotated_center_text(
        canvas,
        "Autoliv",
        right_x + (geometry["right_band"] / 2.0),
        height - geometry["margin_y"] - 18,
        -90,
        bold_font,
        8,
        (0.94, 0.96, 1.0),
    )
    _draw_rotated_center_text(
        canvas,
        f"Pagina {page_no}",
        right_x + (geometry["right_band"] / 2.0),
        geometry["margin_y"] + 18,
        -90,
        regular_font,
        7,
        (0.94, 0.96, 1.0),
    )


def _draw_cell_text(
    canvas,
    *,
    lines: list[str],
    x: float,
    y_top: float,
    height: float,
    font_name: str,
    font_size: float,
) -> None:
    leading = font_size + 0.7
    max_visible = max(1, int((height - 3) // leading))
    text = canvas.beginText()
    text.setTextOrigin(x + 1.3, y_top - 5)
    text.setFont(font_name, font_size)
    text.setLeading(leading)
    text.setFillColorRGB(0.13, 0.13, 0.15)
    for line in lines[:max_visible]:
        text.textLine(line)
    canvas.drawText(text)


def _draw_section_header(
    canvas,
    *,
    section: PdfSection,
    x: float,
    y: float,
    width: float,
    height: float,
    bold_font: str,
) -> tuple[float, float, dict[str, tuple[float, float, float]]]:
    from reportlab.lib.units import mm

    palette = _section_palette(section)
    title_height = 18 * mm
    shift_col_width = 12.5 * mm

    canvas.setStrokeColorRGB(*palette["grid"])
    canvas.setLineWidth(0.5)
    canvas.setFillColorRGB(*palette["accent"])
    canvas.rect(x, y - title_height, width, title_height, stroke=1, fill=1)
    _draw_rotated_center_text(
        canvas,
        section.department,
        x + (width / 2.0),
        y - (title_height / 2.0),
        -90,
        bold_font,
        9.2,
        (0.12, 0.12, 0.12),
    )
    return title_height, shift_col_width, palette


def _draw_section_grid(
    canvas,
    *,
    section: PdfSection,
    ctx: PdfExportContext,
    x: float,
    y: float,
    width: float,
    height: float,
    regular_font: str,
    bold_font: str,
) -> None:
    from reportlab.lib.units import mm

    title_height, shift_col_width, palette = _draw_section_header(
        canvas,
        section=section,
        x=x,
        y=y,
        width=width,
        height=height,
        bold_font=bold_font,
    )

    grid_y = y - title_height
    grid_height = height - title_height
    day_header_height = 11 * mm
    body_height = grid_height - day_header_height
    row_height = body_height / len(SHIFTS)
    day_col_width = (width - shift_col_width) / len(DAY_NAMES)

    canvas.setFillColorRGB(*palette["body_fill"])
    canvas.rect(x, grid_y - grid_height, width, grid_height, stroke=1, fill=1)

    canvas.setFillColorRGB(*palette["header_fill"])
    canvas.rect(x, grid_y - day_header_height, width, day_header_height, stroke=0, fill=1)

    for weekend_name in ("Sambata", "Duminica"):
        if weekend_name not in DAY_NAMES:
            continue
        index = DAY_NAMES.index(weekend_name)
        weekend_x = x + shift_col_width + (index * day_col_width)
        canvas.setFillColorRGB(*palette["weekend_fill"])
        canvas.rect(weekend_x, grid_y - grid_height, day_col_width, grid_height, stroke=0, fill=1)
        canvas.setFillColorRGB(*palette["header_fill"])
        canvas.rect(weekend_x, grid_y - day_header_height, day_col_width, day_header_height, stroke=0, fill=1)

    canvas.setStrokeColorRGB(*palette["grid"])
    canvas.setLineWidth(0.45)
    canvas.rect(x, grid_y - grid_height, width, grid_height, stroke=1, fill=0)
    canvas.line(x + shift_col_width, grid_y, x + shift_col_width, grid_y - grid_height)

    for index in range(len(DAY_NAMES) + 1):
        pos_x = x + shift_col_width + (index * day_col_width)
        canvas.line(pos_x, grid_y, pos_x, grid_y - grid_height)

    for index in range(len(SHIFTS) + 1):
        pos_y = grid_y - day_header_height - (index * row_height)
        canvas.line(x, pos_y, x + width, pos_y)

    canvas.setFont(bold_font, 6.1)
    canvas.setFillColorRGB(0.16, 0.16, 0.18)
    canvas.drawCentredString(x + (shift_col_width / 2.0), grid_y - 7, "Schimbul")

    day_labels = _day_date_labels(ctx.week_start)
    for index, (day_name, date_label) in enumerate(day_labels):
        day_x = x + shift_col_width + (index * day_col_width)
        center_x = day_x + (day_col_width / 2.0)
        canvas.setFont(bold_font, 5.8)
        canvas.drawCentredString(center_x, grid_y - 5.3, day_name)
        canvas.setFont(regular_font, 5.1)
        canvas.setFillColorRGB(0.28, 0.30, 0.34)
        canvas.drawCentredString(center_x, grid_y - 11.8, date_label)
        canvas.setFillColorRGB(0.16, 0.16, 0.18)

    for row_index, shift in enumerate(SHIFTS):
        row_top = grid_y - day_header_height - (row_index * row_height)
        canvas.setFont(regular_font, 5.8)
        canvas.drawString(x + 1.3, row_top - 6, shift)

        for col_index, day_name in enumerate(DAY_NAMES):
            cell = _safe_cell(section.mode_record, section.department, day_name, shift)
            cell_x = x + shift_col_width + (col_index * day_col_width)
            lines = _build_cell_lines(
                cell,
                regular_font,
                4.3,
                day_col_width - 2.5,
                max_lines=max(2, int((row_height - 2) // 5.0)),
            )
            _draw_cell_text(
                canvas,
                lines=lines,
                x=cell_x,
                y_top=row_top,
                height=row_height,
                font_name=regular_font,
                font_size=4.3,
            )


def _draw_section_block(
    canvas,
    *,
    section: PdfSection,
    ctx: PdfExportContext,
    x: float,
    y: float,
    width: float,
    height: float,
    regular_font: str,
    bold_font: str,
) -> None:
    _draw_section_grid(
        canvas,
        section=section,
        ctx=ctx,
        x=x,
        y=y,
        width=width,
        height=height,
        regular_font=regular_font,
        bold_font=bold_font,
    )


def _render_mode_page(
    canvas,
    *,
    ctx: PdfExportContext,
    geometry: dict[str, float],
    regular_font: str,
    bold_font: str,
    page_no: int,
    sections: list[PdfSection],
) -> None:
    _draw_page_header(canvas, ctx, geometry, regular_font, bold_font, page_no)
    if not sections:
        return
    section_count = len(sections)
    block_width = (
        geometry["usable_width"] - ((section_count - 1) * geometry["inter_section_gap"])
    ) / max(1, section_count)
    for index, section in enumerate(sections):
        x = geometry["content_x"] + index * (block_width + geometry["inter_section_gap"])
        _draw_section_block(
            canvas,
            section=section,
            ctx=ctx,
            x=x,
            y=geometry["content_top"],
            width=block_width,
            height=geometry["usable_height"],
            regular_font=regular_font,
            bold_font=bold_font,
        )


def _render_sections_pdf(
    *,
    output_path: str | Path,
    ctx: PdfExportContext,
    sections: list[PdfSection],
    page_size: tuple[float, float],
) -> None:
    try:
        from reportlab.pdfgen import canvas as pdf_canvas
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Lipseste dependinta pentru PDF (reportlab). Instaleaza: pip install reportlab") from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    regular_font, bold_font = _register_font_family()
    geometry = _page_geometry(page_size)

    pdf = pdf_canvas.Canvas(str(output_path), pagesize=page_size)
    pdf.setTitle("Autoliv Shift Manager - Planificare saptamanala")

    if not sections:
        _draw_page_header(pdf, ctx, geometry, regular_font, bold_font, 1)
        pdf.setFont(regular_font, 11)
        pdf.setFillColorRGB(0.2, 0.25, 0.30)
        pdf.drawString(geometry["content_x"], geometry["content_top"] - 14, "Nu exista posturi de exportat.")
        pdf.save()
        return

    grouped: dict[str, list[PdfSection]] = {}
    for section in sections:
        grouped.setdefault(section.mode_name, []).append(section)

    page_no = 1
    first_page = True
    for _, mode_sections in grouped.items():
        start = 0
        while start < len(mode_sections):
            current_slice = mode_sections[start:start + 8]
            if not first_page:
                pdf.showPage()
            _render_mode_page(
                pdf,
                ctx=ctx,
                geometry=geometry,
                regular_font=regular_font,
                bold_font=bold_font,
                page_no=page_no,
                sections=current_slice,
            )
            first_page = False
            page_no += 1
            start += 8

    pdf.save()


def _pdf_department_color(department: str) -> tuple[float, float, float]:
    normalized = " ".join(str(department or "").split()).casefold()
    if normalized.startswith("bucla"):
        color = "D9A35F"
    else:
        color = PDF_DEPARTMENT_COLORS.get(normalized, DEPARTMENT_COLORS.get(department, "D9D9D9"))
    return _hex_to_rgb(color, (0.82, 0.82, 0.82))


def _normalize_week_label(label: str) -> str:
    return str(label or "").replace("Saptamana", "saptamana").replace("Săptămâna", "saptamana")


def _draw_plan_header(canvas, *, title: str, x: float, y: float, width: float, height: float, bold_font: str) -> None:
    brand_width = width * 0.13
    canvas.setFillColorRGB(0.31, 0.44, 0.71)
    canvas.setStrokeColorRGB(0.46, 0.46, 0.46)
    canvas.setLineWidth(0.6)
    canvas.rect(x, y - height, width, height, stroke=1, fill=1)
    canvas.line(x + width - brand_width, y, x + width - brand_width, y - height)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont(bold_font, 15)
    canvas.drawCentredString(x + (width - brand_width) / 2, y - height / 2 - 5, title)
    canvas.setFont(bold_font, 12)
    canvas.drawCentredString(x + width - brand_width / 2, y - height / 2 - 4, "Autoliv")


def _draw_wrapped_lines(
    canvas,
    *,
    lines: list[str],
    x: float,
    y_top: float,
    width: float,
    height: float,
    font_name: str,
    font_size: float,
    color: tuple[float, float, float] = (0.12, 0.12, 0.14),
) -> None:
    leading = font_size + 1.1
    max_lines = max(1, int((height - 4) // leading))
    canvas.setFillColorRGB(*color)
    text = canvas.beginText()
    text.setTextOrigin(x + 2.0, y_top - 6.0)
    text.setFont(font_name, font_size)
    text.setLeading(leading)
    for line in lines[:max_lines]:
        text.textLine(line)
    canvas.drawText(text)


def _draw_plan_block(
    canvas,
    *,
    mode_record: dict,
    department_key: str,
    department_label: str,
    day_labels: list[tuple[str, str]],
    x: float,
    y_top: float,
    width: float,
    height: float,
    regular_font: str,
    bold_font: str,
) -> None:
    dept_width = width * 0.055
    shift_width = width * 0.095
    day_width = (width - dept_width - shift_width) / len(DAY_NAMES)
    header_height = height * 0.24
    row_height = (height - header_height) / len(SHIFTS)
    grid_color = (0.52, 0.52, 0.52)
    header_fill = (0.95, 0.95, 0.95)
    weekend_fill = (0.985, 0.985, 0.965)
    accent = _pdf_department_color(department_key)

    canvas.setStrokeColorRGB(*grid_color)
    canvas.setLineWidth(0.45)

    canvas.setFillColorRGB(*accent)
    canvas.rect(x, y_top - height, dept_width, height, stroke=1, fill=1)
    _draw_rotated_center_text(
        canvas,
        department_label,
        x + dept_width / 2,
        y_top - height / 2,
        90,
        bold_font,
        8.4,
        (0.08, 0.08, 0.08),
    )

    canvas.setFillColorRGB(*header_fill)
    canvas.rect(x + dept_width, y_top - header_height, width - dept_width, header_height, stroke=1, fill=1)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.rect(x + dept_width, y_top - height, width - dept_width, height - header_height, stroke=1, fill=1)

    for day_name in ("Sambata", "Duminica"):
        if day_name not in DAY_NAMES:
            continue
        index = DAY_NAMES.index(day_name)
        day_x = x + dept_width + shift_width + index * day_width
        canvas.setFillColorRGB(*weekend_fill)
        canvas.rect(day_x, y_top - height, day_width, height - header_height, stroke=0, fill=1)
        canvas.setFillColorRGB(*header_fill)
        canvas.rect(day_x, y_top - header_height, day_width, header_height, stroke=0, fill=1)

    canvas.setStrokeColorRGB(*grid_color)
    canvas.rect(x, y_top - height, width, height, stroke=1, fill=0)
    canvas.line(x + dept_width, y_top, x + dept_width, y_top - height)
    canvas.line(x + dept_width + shift_width, y_top, x + dept_width + shift_width, y_top - height)
    canvas.line(x + dept_width, y_top - header_height, x + width, y_top - header_height)

    for index in range(len(DAY_NAMES) + 1):
        pos_x = x + dept_width + shift_width + index * day_width
        canvas.line(pos_x, y_top, pos_x, y_top - height)
    for index in range(len(SHIFTS) + 1):
        pos_y = y_top - header_height - index * row_height
        canvas.line(x + dept_width, pos_y, x + width, pos_y)

    canvas.setFillColorRGB(0.08, 0.08, 0.09)
    canvas.setFont(bold_font, 8)
    canvas.drawCentredString(x + dept_width + shift_width / 2, y_top - header_height / 2 - 3, "Schimbul")

    for index, (day_name, date_label) in enumerate(day_labels):
        center_x = x + dept_width + shift_width + index * day_width + day_width / 2
        canvas.setFont(bold_font, 7.4)
        canvas.drawCentredString(center_x, y_top - header_height * 0.40, DISPLAY_DAY_NAMES.get(day_name, day_name))
        canvas.setFont(regular_font, 6.3)
        canvas.drawCentredString(center_x, y_top - header_height * 0.72, date_label)

    for row_index, shift in enumerate(SHIFTS):
        row_top = y_top - header_height - row_index * row_height
        canvas.setFont(bold_font, 7.4)
        canvas.setFillColorRGB(0.08, 0.08, 0.09)
        canvas.drawCentredString(x + dept_width + shift_width / 2, row_top - row_height / 2 - 3, shift)

        for col_index, day_name in enumerate(DAY_NAMES):
            cell = _safe_cell(mode_record, department_key, day_name, shift)
            employees = [employee for employee in cell.get("employees", []) if isinstance(employee, str) and employee.strip()]
            cell_x = x + dept_width + shift_width + col_index * day_width
            is_special = any(_hours_label_for_employee(cell, employee) == "12h" for employee in employees)
            lines = _build_cell_lines(
                cell,
                regular_font,
                6.1,
                day_width - 4,
                max_lines=max(2, int((row_height - 4) // 7.2)),
            )
            _draw_wrapped_lines(
                canvas,
                lines=lines,
                x=cell_x,
                y_top=row_top,
                width=day_width,
                height=row_height,
                font_name=regular_font,
                font_size=6.1,
                color=(0.75, 0.10, 0.10) if is_special else (0.12, 0.12, 0.14),
            )


def _render_plan_sheet_page(
    canvas,
    *,
    ctx: PdfExportContext,
    sheet_name: str,
    mode_record: dict,
    page_size: tuple[float, float],
    regular_font: str,
    bold_font: str,
) -> None:
    from reportlab.lib.units import mm

    page_width, page_height = page_size
    margin_x = 8 * mm
    margin_y = 8 * mm
    header_height = 14 * mm
    gap = 1.8 * mm
    content_width = page_width - 2 * margin_x
    content_top = page_height - margin_y
    title = f"Planificare magazie : {_normalize_week_label(ctx.week_label)}"
    _draw_plan_header(
        canvas,
        title=title,
        x=margin_x,
        y=content_top,
        width=content_width,
        height=header_height,
        bold_font=bold_font,
    )

    departments = PDF_SHEET_DEPARTMENTS[sheet_name]
    blocks_top = content_top - header_height - gap
    blocks_height = blocks_top - margin_y
    block_height = (blocks_height - gap * (len(departments) - 1)) / len(departments)
    day_labels = _day_date_labels(ctx.week_start)

    for index, (department_key, department_label) in enumerate(departments):
        y_top = blocks_top - index * (block_height + gap)
        _draw_plan_block(
            canvas,
            mode_record=mode_record,
            department_key=department_key,
            department_label=department_label,
            day_labels=day_labels,
            x=margin_x,
            y_top=y_top,
            width=content_width,
            height=block_height,
            regular_font=regular_font,
            bold_font=bold_font,
        )


def export_full_week_plan_pdf(*, week_record: dict, output_path: str | Path) -> None:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas as pdf_canvas

    ctx = PdfExportContext(
        week_start=str(week_record.get("week_start") or ""),
        week_end=str(week_record.get("week_end") or ""),
        week_label=str(week_record.get("week_label") or ""),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_size = landscape(A3)
    regular_font, bold_font = _register_font_family()
    pdf = pdf_canvas.Canvas(str(output_path), pagesize=page_size)
    pdf.setTitle("Autoliv Shift Manager - Planificare magazie")

    modes = week_record.get("modes", {}) if isinstance(week_record, dict) else {}
    for page_index, sheet_name in enumerate(("Bucle", "Magazie")):
        if page_index:
            pdf.showPage()
        mode_record = modes.get(sheet_name, {}) if isinstance(modes, dict) else {}
        if not isinstance(mode_record, dict):
            mode_record = {}
        _render_plan_sheet_page(
            pdf,
            ctx=ctx,
            sheet_name=sheet_name,
            mode_record=mode_record,
            page_size=page_size,
            regular_font=regular_font,
            bold_font=bold_font,
        )
    pdf.save()


def export_week_plan_pdf(
    *,
    week_record: dict,
    mode_name: str,
    department: str,
    output_path: str | Path,
) -> None:
    from reportlab.lib.pagesizes import A4

    ctx = PdfExportContext(
        week_start=str(week_record.get("week_start") or ""),
        week_end=str(week_record.get("week_end") or ""),
        week_label=str(week_record.get("week_label") or ""),
        mode=str(mode_name or ""),
        department=str(department or ""),
    )
    sections = _build_export_sections(week_record, mode_name=mode_name, department=department)
    _render_sections_pdf(
        output_path=output_path,
        ctx=ctx,
        sections=sections,
        page_size=A4,
    )
