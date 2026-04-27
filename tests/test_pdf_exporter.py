from datetime import date

import pytest
from pypdf import PdfReader

from logic.schedule_store import DAY_NAMES, SHIFTS, TEMPLATES, ScheduleStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    import logic.schedule_store as store_module

    monkeypatch.setattr(store_module, "SCHEDULE_PATH", tmp_path / "schedule_data.json")
    monkeypatch.setattr(store_module, "BACKUP_DIR", tmp_path / "backups")
    return ScheduleStore()


def test_export_full_week_plan_pdf_creates_complete_structural_pdf(store, tmp_path):
    week = store.get_or_create_week(date(2026, 4, 7))
    long_name = "Șerban-Ionescu Alexandru cu nume foarte lung pentru wrap intern"

    for mode_name in TEMPLATES:
        mode_record = week["modes"][mode_name]
        for dept_index, dept in enumerate(mode_record["departments"]):
            for day_index, day in enumerate(DAY_NAMES[:5]):
                shift = SHIFTS[day_index % len(SHIFTS)]
                employees = [
                    f"Ion Popescu {dept_index}-{day_index}",
                    long_name,
                    f"Maria Țăran Întreținere {mode_name}",
                ]
                cell = mode_record["schedule"][dept][day][shift]
                cell["employees"] = employees
                cell["colors"][long_name] = "#E74C3C"

    out = tmp_path / "plan.pdf"
    from logic.pdf_exporter import export_full_week_plan_pdf

    export_full_week_plan_pdf(week_record=week, output_path=out)

    data = out.read_bytes()
    assert data.startswith(b"%PDF"), "Fisierul exportat trebuie sa fie un PDF valid"
    assert len(data) > 10_000, "PDF-ul complet trebuie sa contina date reale, nu doar header gol"
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        assert width > height
        assert width == pytest.approx(1190.55, abs=1.0)
        assert height == pytest.approx(841.89, abs=1.0)


def test_pdf_export_includes_all_defined_departments_even_when_empty(store, tmp_path):
    week = store.get_or_create_week(date(2026, 4, 20))
    week["modes"]["Magazie"]["schedule"]["Sef schimb"]["Luni"]["Sch1"]["employees"] = ["Munteanu M"]

    from logic.pdf_exporter import _iter_export_departments, export_full_week_plan_pdf

    export_departments = _iter_export_departments(week["modes"])
    expected_count = sum(len(departments) for departments in TEMPLATES.values())
    assert len(export_departments) == expected_count
    assert [department for _, _, department in export_departments] == [
        department for departments in TEMPLATES.values() for department in departments
    ]

    out = tmp_path / "plan_complet.pdf"
    export_full_week_plan_pdf(week_record=week, output_path=out)
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2


def test_full_week_pdf_matches_excel_approved_two_sheet_order(store, tmp_path):
    week = store.get_or_create_week(date(2026, 4, 20))

    from logic.pdf_exporter import export_full_week_plan_pdf

    out = tmp_path / "plan_2_planse.pdf"
    export_full_week_plan_pdf(week_record=week, output_path=out)

    reader = PdfReader(str(out))
    assert len(reader.pages) == 2

    page_1_text = reader.pages[0].extract_text() or ""
    page_2_text = reader.pages[1].extract_text() or ""

    assert "Planificare magazie" in page_1_text
    assert "Planificare magazie" in page_2_text
    assert "Autoliv" in page_1_text
    assert "Autoliv" in page_2_text

    for department in [
        "BUCLA RA + RB",
        "BUCLA TA + TB",
        "BUCLA 02",
        "BUCLA 03",
        "BUCLA 04",
        "BUCLA 05 + 07",
        "Ambalaje",
    ]:
        assert department in page_1_text
        assert department not in page_2_text

    for department in [
        "Sef Schimb",
        "Receptii",
        "Livrari",
        "Etichetare / Scanare",
        "Retragere finite",
        "Baloare / Asamblare",
    ]:
        assert department in page_2_text
        assert department not in page_1_text


def test_custom_pdf_layout_helpers_produce_multi_page_positions():
    from reportlab.lib.pagesizes import A3, landscape

    from logic.pdf_exporter import _layout_positions, _page_geometry

    geometry = _page_geometry(landscape(A3))
    positions = _layout_positions(20, geometry)

    assert positions[0][0] == 0
    assert positions[-1][0] >= 1
    assert len({(page, x, y) for page, x, y in positions}) == len(positions)


def test_custom_pdf_geometry_uses_dense_industrial_block_layout():
    from reportlab.lib.pagesizes import A3

    from logic.pdf_exporter import _page_geometry

    geometry = _page_geometry(A3)

    assert geometry["usable_width"] > geometry["page_width"] * 0.7
    assert geometry["usable_height"] > geometry["page_height"] * 0.7
    assert geometry["right_band"] > 0
    assert geometry["content_top"] > geometry["content_bottom"]


def test_build_cell_lines_compacts_long_employee_lists():
    from logic.pdf_exporter import _build_cell_lines

    cell = {
        "employees": [
            "Popescu Ion cu nume foarte lung",
            "Ionescu Mihai",
            "Georgescu Ana",
            "Marinescu Șerban",
            "Dumitru Elena",
        ],
        "colors": {"Marinescu Șerban": "#E74C3C"},
    }

    lines = _build_cell_lines(cell, "Helvetica", 6, 90, 4)
    assert lines
    assert len(lines) <= 4
    assert any("12h" in line for line in lines) or any(line.startswith("+") for line in lines)
