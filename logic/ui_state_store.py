import json
from datetime import date, datetime

from logic.app_logger import log_exception
from logic.app_paths import ensure_runtime_file
from logic.schedule_store import get_week_start


UI_STATE_PATH = ensure_runtime_file("data/ui_state.json")


class UIStateStore:
    def load_last_selected_date(self):
        if not UI_STATE_PATH.exists():
            return None

        try:
            with UI_STATE_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            log_exception("ui_state_load", exc)
            return None

        if not isinstance(data, dict):
            return None

        value = data.get("last_selected_date", "").strip()
        if not value:
            return None

        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def resolve_startup_date(self):
        today = date.today()
        saved_date = self.load_last_selected_date()
        if saved_date is None:
            return today

        if get_week_start(saved_date) != get_week_start(today):
            return today

        return saved_date

    def save_last_selected_date(self, selected_date: date):
        payload = {"last_selected_date": selected_date.isoformat()}
        try:
            UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with UI_STATE_PATH.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            log_exception("ui_state_save", exc)
