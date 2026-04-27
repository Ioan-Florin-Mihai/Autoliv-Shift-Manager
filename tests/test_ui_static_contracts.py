from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pdf_export_button_is_present_in_left_panel():
    source = _source("ui/components/left_panel.py")
    assert "Export PDF" in source
    assert "self._export_pdf_button" in source
    assert "self.export_pdf_dialog" in source
    assert 'self._create_primary_button(' in source


def test_excel_export_button_is_present_in_left_panel():
    source = _source("ui/components/left_panel.py")
    assert "Export Excel" in source
    assert "self._export_excel_button" in source
    assert "self.export_excel_dialog" in source
    assert 'self._create_primary_button(' in source


def test_left_panel_does_not_expose_service_actions_or_scrollbar():
    source = _source("ui/components/left_panel.py")
    assert "CTkScrollableFrame" not in source
    assert "Mentenanta" not in source
    assert "Status Sistem" not in source
    assert "Restore backup" not in source


def test_publish_button_obeys_busy_action_guard():
    source = _source("ui/planner_dashboard.py")
    assert "def _set_busy_action" in source
    assert "can_publish = self._is_admin() and not self._busy_action" in source


def test_week_grid_has_horizontal_scrollbar_contract():
    source = _source("ui/planner_dashboard.py")
    assert "self.grid_hscroll = ctk.CTkScrollbar" in source
    assert 'orientation="horizontal"' in source
    assert "self.grid_days_canvas.configure(xscrollcommand=self.grid_hscroll.set)" in source


def test_unplanned_warning_is_non_blocking_right_panel_contract():
    right_panel = _source("ui/components/right_panel.py")
    dashboard = _source("ui/planner_dashboard.py")
    assert "find_unplanned_employees" in right_panel
    assert "def render_unplanned_warning" in right_panel
    assert "def toggle_unplanned_section" in right_panel
    assert "self._unplanned_expanded = False" in right_panel
    assert "self.unplanned_section.grid_remove()" in right_panel
    assert "messagebox" not in right_panel
    assert "self.render_unplanned_warning()" in dashboard
