import json

import pytest
from fastapi.testclient import TestClient


def test_atomic_write_json_retries_on_permission_error(monkeypatch, tmp_path):
    from logic.utils import io as io_module

    target = tmp_path / "file.json"

    calls = {"count": 0}
    real_replace = io_module.os.replace

    def replace_flaky(src, dst):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError("locked")
        return real_replace(src, dst)

    monkeypatch.setattr(io_module.os, "replace", replace_flaky)

    io_module.atomic_write_json(target, {"ok": True}, replace_retries=2)
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert calls["count"] >= 2


def test_tv_page_returns_503_if_template_missing(monkeypatch, tmp_path):
    import tv_server

    monkeypatch.setattr(tv_server, "TPL_DIR", tmp_path)
    client = TestClient(tv_server.app)

    resp = client.get("/tv", headers={"X-API-Key": tv_server.get_api_key()})
    assert resp.status_code in (200, 503)
    if resp.status_code == 503:
        assert "template" in resp.text.lower()


def test_tv_metrics_returns_500_on_unhandled_build_errors(monkeypatch):
    import tv_server

    client = TestClient(tv_server.app)

    monkeypatch.setattr(tv_server, "get_api_key", lambda: "test-suite-key")
    monkeypatch.setattr(tv_server, "_build_tv_data", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = client.get("/metrics", headers={"X-API-Key": "test-suite-key"})
    assert resp.status_code == 500
    assert resp.json().get("error")


def test_tv_load_schedule_uses_cache_when_file_locked(monkeypatch, tmp_path):
    import tv_server
    import builtins

    live = tmp_path / "schedule_live.json"
    live.write_text(json.dumps({"weeks": {"2026-04-06": {"week_start": "2026-04-06"}}}), encoding="utf-8")
    monkeypatch.setattr(tv_server, "DATA_FILE", live)
    tv_server._CACHED_DATA = {"weeks": {"cached": {"week_start": "2026-01-01"}}}
    tv_server._LAST_MTIME = 0.0

    real_open = builtins.open

    def open_locked(*_args, **_kwargs):
        # Only lock the live file reads used by tv_server._load_schedule().
        path = _args[0] if _args else None
        if str(path) == str(live):
            raise PermissionError("locked")
        return real_open(*_args, **_kwargs)

    monkeypatch.setattr(builtins, "open", open_locked)
    data = tv_server._load_schedule()
    assert data == tv_server._CACHED_DATA
