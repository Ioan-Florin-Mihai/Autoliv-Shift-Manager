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


def test_new_employee_registration_does_not_auto_assign_to_selected_cell():
    source = _source("ui/planner_dashboard.py")
    start = source.index("    def add_new_employee")
    end = source.index("    def add_employee_from_search", start)
    method_source = source[start:end]
    assert "self.add_employee_to_selected_cell(employee)" not in method_source
    assert "initial_department=self.selected_department" in method_source


def test_suggestions_are_filtered_by_selected_department():
    source = _source("ui/components/right_panel.py")
    assert "def _department_suggestion_names" in source
    assert "department_suggestions = self._department_suggestion_names(suggestions)" in source
    assert "employees_with_profile_department" in source


def test_personnel_button_uses_management_wording():
    right_panel = _source("ui/components/right_panel.py")
    form = _source("ui/employee_form.py")
    assert "Gestionare Personal" in right_panel
    assert "Gestionare Incadrare" in form
    assert "Salveaza Incadrare" in form


def test_tv_template_uses_server_api_contract_and_valid_department_keys():
    source = _source("templates/tv.html")
    assert "__TV_API_KEY__" in source
    assert "X-API-Key" in source
    assert "DATA_URL" in source
    assert "BUCLA 05" in source
    assert "BUCLA TA+TB" in source
    assert "BUCLA RA+RB" in source
    assert "PAGE_SWITCH_MS" in source
    assert "__TV_uPI_KEY__" not in source
    assert "X-uPI-Key" not in source
    assert "BUCLu" not in source


def test_pyinstaller_bundle_includes_tv_template():
    source = _source("Autoliv_Shift_Manager_Onefile.spec")
    assert '("templates/tv.html",              "templates")' in source


def test_login_lockout_uses_tk_after_countdown_contract():
    source = _source("ui/dashboard.py")
    assert "get_lockout_remaining_seconds" in source
    assert "self.login_button.configure(state=\"disabled\")" in source
    assert "self.after(1000, self._render_lockout_countdown)" in source
    assert "self.after_cancel(self._lockout_after_id)" in source
