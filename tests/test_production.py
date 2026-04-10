import json
from datetime import date

import bcrypt
from fastapi.testclient import TestClient

import logic.app_config as app_config
import logic.audit_logger as audit_logger
import logic.auth as auth_module
import logic.schedule_store as schedule_store_module
import main as main_module
import tv_server
from logic.schedule_store import ScheduleStore


def _make_minimal_week_payload(week_start: str) -> dict:
    return {
        "weeks": {
            week_start: {
                "week_start": week_start,
                "week_end": "2026-04-12",
                "week_label": "Saptamana 15",
                "published_at": "2026-04-10T08:00:00",
                "modes": {
                    "Magazie": {
                        "departments": [],
                        "schedule": {},
                    },
                    "Bucle": {
                        "departments": [],
                        "schedule": {},
                    },
                },
            }
        }
    }


def test_publish_flow_atomic_and_locked(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule_store_module, "DRAFT_SCHEDULE_PATH", tmp_path / "schedule_draft.json")
    monkeypatch.setattr(schedule_store_module, "LIVE_SCHEDULE_PATH", tmp_path / "schedule_live.json")
    monkeypatch.setattr(schedule_store_module, "LEGACY_SCHEDULE_PATH", tmp_path / "schedule_data.json")
    monkeypatch.setattr(schedule_store_module, "SCHEDULE_PATH", tmp_path / "schedule_draft.json")
    monkeypatch.setattr(schedule_store_module, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(schedule_store_module, "auth_is_admin", lambda user: user == "admin")

    store = ScheduleStore()
    week = store.get_or_create_week(date(2026, 4, 6))
    store.update_week(week)

    week_key = week["week_start"]

    try:
        store.publish_week(week_key, "operator")
        assert False, "publish_week should reject non-admin users"
    except PermissionError:
        pass

    store.publish_week(week_key, "admin")

    draft_data = json.loads((tmp_path / "schedule_draft.json").read_text(encoding="utf-8"))
    live_data = json.loads((tmp_path / "schedule_live.json").read_text(encoding="utf-8"))

    assert draft_data == live_data
    assert bool(store.data["weeks"][week_key].get("locked")) is True
    assert store.data["weeks"][week_key].get("published_by") == "admin"
    assert list(tmp_path.glob("*.tmp")) == []


def test_tv_endpoints_health_and_data(monkeypatch, tmp_path):
    live_path = tmp_path / "schedule_live.json"
    live_path.write_text(json.dumps(_make_minimal_week_payload("2026-04-06")), encoding="utf-8")

    monkeypatch.setattr(tv_server, "DATA_FILE", live_path)
    monkeypatch.setattr(tv_server, "DRAFT_FILE", tmp_path / "schedule_draft.json")
    monkeypatch.setattr(tv_server, "BACKUP_DIR", tmp_path / "backups")
    tv_server._CACHED_DATA = None
    tv_server._LAST_MTIME = 0.0

    client = TestClient(tv_server.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json().get("status") == "ok"

    data_resp = client.get("/api/tv-data")
    assert data_resp.status_code == 200
    payload = data_resp.json()
    assert "server_time" in payload
    assert "last_publish_time" in payload
    assert isinstance(payload.get("data"), dict)


def test_config_invalid_values_are_sanitized(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(app_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(app_config, "_cached_config", None)

    config_path.write_text(
        json.dumps(
            {
                "server_port": "bad",
                "refresh_interval": -10,
                "max_backups": 0,
                "auto_lock_on_publish": "yes",
                "log_max_bytes": 10,
            }
        ),
        encoding="utf-8",
    )

    cfg = app_config.get_config(force_reload=True)
    assert isinstance(cfg["server_port"], int)
    assert cfg["server_port"] == 8000
    assert cfg["refresh_interval"] >= 1
    assert cfg["max_backups"] >= 1
    assert cfg["auto_lock_on_publish"] is True
    assert cfg["log_max_bytes"] >= 1024


def test_audit_log_append_and_rotation(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit_log.json"
    monkeypatch.setattr(audit_logger, "AUDIT_LOG_PATH", audit_path)
    monkeypatch.setattr(audit_logger, "MAX_AUDIT_ENTRIES", 3)

    for idx in range(5):
        audit_logger.log_event(action=f"action_{idx}", user="admin", week="2026-W15")

    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data[-1]["action"] == "action_4"


def test_entry_modes_dispatch(monkeypatch):
    called = {"planner": 0, "tv_web": 0}

    monkeypatch.setattr(main_module, "_run_planner", lambda: called.__setitem__("planner", called["planner"] + 1))
    monkeypatch.setattr(main_module, "_supervise_tv_server", lambda: called.__setitem__("tv_web", called["tv_web"] + 1))

    main_module.run_cli(["--planner"])
    main_module.run_cli(["--tv-web"])

    assert called["planner"] == 1
    assert called["tv_web"] == 1


def test_password_verification_uses_config_hash(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                **app_config.DEFAULT_CONFIG,
                "app_password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=12)).decode("utf-8"),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(app_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(app_config, "_cached_config", None)
    monkeypatch.setattr(auth_module, "USERS_PATH", tmp_path / "users.json")

    ok, _ = auth_module.verify_login_detailed("admin", "admin123")
    assert ok is True

    ok_wrong_password, _ = auth_module.verify_login_detailed("admin", "wrong")
    assert ok_wrong_password is False


def test_publish_week_atomic_single_domain_call(monkeypatch, tmp_path):
    monkeypatch.setattr(schedule_store_module, "DRAFT_SCHEDULE_PATH", tmp_path / "schedule_draft.json")
    monkeypatch.setattr(schedule_store_module, "LIVE_SCHEDULE_PATH", tmp_path / "schedule_live.json")
    monkeypatch.setattr(schedule_store_module, "LEGACY_SCHEDULE_PATH", tmp_path / "schedule_data.json")
    monkeypatch.setattr(schedule_store_module, "SCHEDULE_PATH", tmp_path / "schedule_draft.json")
    monkeypatch.setattr(schedule_store_module, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(schedule_store_module, "auth_is_admin", lambda user: user == "admin")

    store = ScheduleStore()
    week = store.get_or_create_week(date(2026, 4, 6))
    week_key = week["week_start"]
    store.data.setdefault("weeks", {})[week_key] = week

    counters = {"save": 0, "live": 0}
    original_save = store.save
    original_live = store._save_live_snapshot

    def save_spy():
        counters["save"] += 1
        return original_save()

    def live_spy():
        counters["live"] += 1
        return original_live()

    monkeypatch.setattr(store, "save", save_spy)
    monkeypatch.setattr(store, "_save_live_snapshot", live_spy)

    store.publish_week(week_key, "admin")

    assert counters["save"] == 1
    assert counters["live"] == 1
    assert bool(store.data["weeks"][week_key].get("locked")) is True


def test_auto_ip_detection_from_config_auto(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                **app_config.DEFAULT_CONFIG,
                "server_ip": "AUTO",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(app_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(app_config, "_cached_config", None)
    monkeypatch.setattr(app_config, "get_local_ip", lambda: "192.168.50.77")

    cfg = app_config.get_config(force_reload=True)
    assert cfg["server_ip"] == "192.168.50.77"
