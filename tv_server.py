"""
tv_server.py
─────────────────────────────────────────────────────────────
Server web TV FastAPI — Autoliv Shift Manager

Livreaza un dashboard industrial catre televizoarele din fabrica prin LAN.
Toate TV-urile deschid acelasi URL -> sincronizare perfecta, fara interactiune.

Utilizare:
    python main.py --tv-web

URL TV:
    http://<LAN_IP>:8000/tv
"""

from __future__ import annotations

import hmac
import json
import logging
import socket
import time
from datetime import date, timedelta

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from logic.app_config import get_config
from logic.app_logger import log_error, log_exception, log_info
from logic.app_paths import (
    BACKUP_DIR,
    BASE_DIR,
    BUNDLE_DIR,
    SCHEDULE_DRAFT,
    SCHEDULE_LIVE,
    bootstrap_runtime_root,
)
from logic.constants import HOURS_12_COLOR as _HOURS_12_COLOR
from logic.tv_update import load_tv_version
from logic.tv_update import trigger_tv_update as _shared_trigger_tv_update

# ─── Paths ────────────────────────────────────────────────────────────────────
RESOURCE_ROOT = BUNDLE_DIR if (BUNDLE_DIR / "templates").exists() else BASE_DIR
DATA_FILE  = SCHEDULE_LIVE
DRAFT_FILE = SCHEDULE_DRAFT
TPL_DIR    = RESOURCE_ROOT / "templates"

# ─── Constante domeniu (oglindite din schedule_store, fara import ca serverul
#     sa ramana fara dependinte si utilizabil cu --tv-web fara incarcarea aplicatiei complete) ──
ABSENCE_NAMES: frozenset[str] = frozenset({"CO", "CM", "ABSENT"})
COLOR_12H = "#" + _HOURS_12_COLOR   # stocat in cell["colors"][nume_angajat]
SHIFTS     = ["Sch1", "Sch2", "Sch3"]
DAYS       = [
    ("Luni", 0), ("Marti", 1), ("Miercuri", 2),
    ("Joi", 3),  ("Vineri", 4), ("Sambata", 5), ("Duminica", 6),
]
DAY_OFFSETS   = {name: offset for name, offset in DAYS}
WEEKEND_DAYS  = frozenset({"Sambata", "Duminica"})
MODE_NAMES    = ["Magazie", "Bucle"]

_LAST_MTIME: float = 0.0
_CACHED_DATA: dict | None = None
TV_VERSION = load_tv_version()
_LAST_LOGGED_TV_VERSION = TV_VERSION


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _iter_weeks(data: dict) -> list[tuple[date, dict]]:
    weeks = data.get("weeks", {})
    if not isinstance(weeks, dict):
        return []

    items: list[tuple[date, dict]] = []
    for week_key, week_record in weeks.items():
        if not isinstance(week_record, dict):
            continue
        week_start_value = week_record.get("week_start")
        if not isinstance(week_start_value, str) or not week_start_value:
            week_start_value = week_key if isinstance(week_key, str) else ""
        try:
            week_start_date = date.fromisoformat(week_start_value)
        except ValueError:
            continue
        items.append((week_start_date, week_record))

    items.sort(key=lambda item: item[0])
    return items


def _latest_published_week(data: dict) -> tuple[date, dict] | None:
    published_candidates: list[tuple[str, date, dict]] = []
    for week_start_date, week_record in _iter_weeks(data):
        published_at = week_record.get("published_at")
        if isinstance(published_at, str) and published_at:
            published_candidates.append((published_at, week_start_date, week_record))

    if not published_candidates:
        return None

    _, week_start_date, week_record = max(
        published_candidates,
        key=lambda item: (item[0], item[1].isoformat()),
    )
    return week_start_date, week_record


def _select_reference_week(data: dict, today: date) -> tuple[date | None, dict]:
    latest_published = _latest_published_week(data)
    if latest_published is not None:
        return latest_published

    week_items = _iter_weeks(data)
    if not week_items:
        return None, {}

    current_week_start = _week_start(today)
    for week_start_date, week_record in week_items:
        if week_start_date == current_week_start:
            return week_start_date, week_record

    for week_start_date, week_record in week_items:
        if week_start_date >= current_week_start:
            return week_start_date, week_record

    return week_items[-1]


def _get_week_by_start(data: dict, week_start_date: date | None) -> dict:
    if week_start_date is None:
        return {}
    return data.get("weeks", {}).get(week_start_date.isoformat()) or {}


def _resolve_display_window(data: dict, today: date) -> tuple[dict, dict, list[str]]:
    reference_week_start, reference_week = _select_reference_week(data, today)
    if not reference_week:
        return {}, {}, []

    return reference_week, {}, ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]


def _sync_tv_version() -> int:
    global TV_VERSION
    TV_VERSION = load_tv_version()
    return TV_VERSION


def trigger_tv_update() -> int:
    global TV_VERSION
    TV_VERSION = _shared_trigger_tv_update()
    return TV_VERSION


def _load_schedule() -> dict:
    """Citeste schedule_live.json cu cache pe mtime pentru throughput stabil pe mai multe TV-uri."""
    global _LAST_MTIME, _CACHED_DATA
    if _CACHED_DATA is None:
        log_info("[TV] Loading data from: %s", DATA_FILE)
    if not DATA_FILE.exists():
        restored = _restore_live_from_sources()
        if not restored:
            _CACHED_DATA = {"weeks": {}}
            _LAST_MTIME = 0.0
            return _CACHED_DATA

    mtime = DATA_FILE.stat().st_mtime
    if _CACHED_DATA is not None and mtime == _LAST_MTIME:
        return _CACHED_DATA

    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
    except OSError as exc:
        # If the file is temporarily locked (Windows), keep serving the last cached data.
        is_lock_related = isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32, 33}
        if is_lock_related and _CACHED_DATA is not None:
            return _CACHED_DATA
        restored = _restore_live_from_sources()
        if not restored:
            return _CACHED_DATA if _CACHED_DATA is not None else {"weeks": {}}
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            return _CACHED_DATA if _CACHED_DATA is not None else {"weeks": {}}
    except json.JSONDecodeError:
        restored = _restore_live_from_sources()
        if not restored:
            return _CACHED_DATA if _CACHED_DATA is not None else {"weeks": {}}
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            return _CACHED_DATA if _CACHED_DATA is not None else {"weeks": {}}
    _CACHED_DATA = loaded if isinstance(loaded, dict) else {"weeks": {}}
    _LAST_MTIME = mtime
    return _CACHED_DATA


def _restore_live_from_sources() -> bool:
    candidates = []
    if DRAFT_FILE.exists():
        candidates.append(DRAFT_FILE)
    if BACKUP_DIR.exists():
        candidates.extend(sorted(BACKUP_DIR.glob("schedule_backup_*.json"), reverse=True))
        candidates.extend(sorted(BACKUP_DIR.glob("schedule_daily_*.json"), reverse=True))
    for candidate in candidates:
        try:
            with candidate.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict) or not isinstance(data.get("weeks", {}), dict):
                continue
            from logic.utils.io import atomic_write_json
            atomic_write_json(DATA_FILE, data)
            return True
        except (OSError, json.JSONDecodeError):
            continue
    return False


def _is_active(name: str) -> bool:
    return name.strip().upper() not in ABSENCE_NAMES


def _is_12h(colors: dict, employee: str) -> bool:
    """Returneaza True daca angajatul are culoarea de 12h (case-insensitive)."""
    target = " ".join((employee or "").split()).casefold()
    for k, v in colors.items():
        key = " ".join((k or "").split()).casefold()
        if key == target:
            # Pastreaza semantica din schedule_store: culoarea poate fi stocata cu sau fara prefixul '#'
            return str(v or "").strip().upper().lstrip("#") == _HOURS_12_COLOR.upper()
    return False


def _employee_tv_payload(colors: dict, employee: object) -> dict:
    raw = str(employee or "")
    name = " ".join(raw.split())
    is12 = _is_12h(colors, raw)
    return {
        "name": name,
        # Pastreaza boolean-ul pentru compatibilitate, dar trimite si un label explicit de program
        # ca UI-ul TV sa oglindeasca logica din desktop (8h vs 12h) fara presupuneri.
        "hours12": is12,
        "program": "12h" if is12 else "8h",
    }


# ─── Main data builder ────────────────────────────────────────────────────────

def _build_tv_data() -> dict:
    config = get_config()
    raw = _load_schedule()
    today = date.today()
    current_week, next_week, display_days = _resolve_display_window(raw, today)
    current_tv_version = _sync_tv_version()

    # Fiecare zi afisata se mapeaza la saptamana din care face parte
    data_map: dict[str, dict] = {d: current_week for d in display_days}

    # Calculeaza etichetele de data afisata pentru fiecare zi
    day_dates: dict[str, str]     = {}
    day_dates_iso: dict[str, str] = {}
    for day_name in display_days:
        week_rec  = data_map[day_name]
        ws_str    = week_rec.get("week_start")
        if ws_str:
            ws       = date.fromisoformat(ws_str)
            day_date = ws + timedelta(days=DAY_OFFSETS[day_name])
            day_dates[day_name]     = day_date.strftime("%d %b")
            day_dates_iso[day_name] = day_date.isoformat()
        else:
            day_dates[day_name]     = day_name
            day_dates_iso[day_name] = ""

    # Eticheta intervalului de saptamana publicate
    primary_week = current_week
    week_label = primary_week.get("week_label", "") if primary_week else ""
    week_range = ""
    try:
        ws_str = primary_week.get("week_start", "") if primary_week else ""
        we_str = primary_week.get("week_end", "") if primary_week else ""
        if ws_str and we_str:
            ws = date.fromisoformat(ws_str)
            we = date.fromisoformat(we_str)
            week_range = f"{ws.strftime('%d %b')} – {we.strftime('%d %b')}"
    except (TypeError, ValueError):  # noqa: BLE001
        pass

    # Construieste departamentele si planificarea pe fiecare mod
    departments: dict[str, list]  = {}
    schedule: dict[str, dict]     = {}

    for mode_name in MODE_NAMES:
        mode_rec_primary = primary_week.get("modes", {}).get(mode_name, {}) if primary_week else {}
        depts_list = mode_rec_primary.get("departments", [])
        mode_schedule: dict[str, dict] = {}

        for dept in depts_list:
            dept_data: dict[str, dict] = {}
            for day_name in display_days:
                week_rec   = data_map[day_name]
                day_shifts: dict[str, list] = {}
                for shift in SHIFTS:
                    cell = (
                        week_rec.get("modes", {})
                        .get(mode_name, {})
                        .get("schedule", {})
                        .get(dept, {})
                        .get(day_name, {})
                        .get(shift, {})
                    )
                    colors = cell.get("colors", {}) if isinstance(cell, dict) else {}
                    emps   = cell.get("employees", []) if isinstance(cell, dict) else []
                    day_shifts[shift] = [
                        _employee_tv_payload(colors, e)
                        for e in emps
                        if _is_active(str(e or ""))
                    ]
                dept_data[day_name] = day_shifts
            mode_schedule[dept] = dept_data

        departments[mode_name] = depts_list
        schedule[mode_name]    = mode_schedule

    payload = {
        "display_days":   display_days,
        "day_dates":      day_dates,
        "day_dates_iso":  day_dates_iso,
        "today_iso":      today.isoformat(),
        "tv_version":     current_tv_version,
        "server_time_ms": int(time.time() * 1000),
        "refresh_interval_ms": int(config.get("refresh_interval", 5)) * 1000,
        "tv_stale_ms": int(config.get("tv_stale_seconds", 15)) * 1000,
        "last_update_ms": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
        "week_label":     week_label,
        "week_range":     week_range,
        "departments":    departments,
        "schedule":       schedule,
        "published_week_start": current_week.get("week_start", "") if current_week else "",
        "has_data": False,
        "message": "Nu există date publicate",
    }

    has_departments = _count_departments(payload) > 0
    has_entries = _count_all_employees(payload) > 0
    payload["has_data"] = has_departments or has_entries
    if payload["has_data"]:
        payload["message"] = ""

    return payload


def _extract_last_publish_time(raw: dict) -> str | None:
    latest: str | None = None
    for week_record in raw.get("weeks", {}).values():
        if not isinstance(week_record, dict):
            continue
        published_at = week_record.get("published_at")
        if isinstance(published_at, str) and published_at:
            if latest is None or published_at > latest:
                latest = published_at
    return latest


def _count_all_employees(payload: dict) -> int:
    total = 0
    for mode_schedule in payload.get("schedule", {}).values():
        if not isinstance(mode_schedule, dict):
            continue
        for dept_data in mode_schedule.values():
            if not isinstance(dept_data, dict):
                continue
            for day_data in dept_data.values():
                if not isinstance(day_data, dict):
                    continue
                for shift_entries in day_data.values():
                    if isinstance(shift_entries, list):
                        total += len(shift_entries)
    return total


def _count_departments(payload: dict) -> int:
    all_departments: set[str] = set()
    for dep_list in payload.get("departments", {}).values():
        if isinstance(dep_list, list):
            all_departments.update(item for item in dep_list if isinstance(item, str))
    return len(all_departments)



# Instanta FastAPI trebuie definita inainte de utilizare
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

def _no_store_headers() -> dict[str, str]:
    # Make kiosk behavior more predictable (avoid intermediary caches).
    return {"Cache-Control": "no-store"}

def get_api_key():
    config = get_config()
    return str(config.get("api_key") or "").strip()

def _tv_auth_warning() -> str | None:
    if get_api_key():
        return None
    return "TV API key lipseste. Endpointurile read-only ruleaza in mod insecure."

def require_api_key(request: Request, *, allow_insecure: bool = False) -> bool:
    provided_api_key = request.headers.get("X-API-Key")
    expected_api_key = get_api_key()
    if not expected_api_key:
        return allow_insecure
    return bool(
        provided_api_key
        and expected_api_key
        and hmac.compare_digest(provided_api_key, expected_api_key)
    )

@app.get("/tv", response_class=HTMLResponse)
async def tv_page(request: Request) -> HTMLResponse:
    try:
        html = (TPL_DIR / "tv.html").read_text(encoding="utf-8")
    except OSError:
        return HTMLResponse(
            content="TV template missing. Contact administrator.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers=_no_store_headers(),
        )
    html = html.replace("__TV_API_KEY__", get_api_key())
    return HTMLResponse(content=html, headers=_no_store_headers())

@app.get("/api/tv-data")
async def tv_data(request: Request) -> JSONResponse:
    if not require_api_key(request, allow_insecure=True):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED, headers=_no_store_headers())
    try:
        raw = _load_schedule()
        payload = _build_tv_data()
        entries = _count_all_employees(payload)
        log_info("[TV] Loaded %s entries", entries)
        return JSONResponse(
            content={
                "server_time": int(time.time() * 1000),
                "last_publish_time": _extract_last_publish_time(raw),
                "data": payload,
                "auth_warning": _tv_auth_warning(),
            },
            headers=_no_store_headers(),
        )
    except (OSError, ValueError, RuntimeError) as exc:
        log_exception("tv_data", exc)
        return JSONResponse(content={"error": "Internal server error"}, status_code=500, headers=_no_store_headers())


@app.get("/tv/version")
async def get_tv_version(request: Request) -> JSONResponse:
    if not require_api_key(request, allow_insecure=True):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED, headers=_no_store_headers())
    global _LAST_LOGGED_TV_VERSION
    version = _sync_tv_version()
    if version != _LAST_LOGGED_TV_VERSION:
        log_info("[TV] Version changed -> reload")
        _LAST_LOGGED_TV_VERSION = version
    return JSONResponse(content={"version": version}, headers=_no_store_headers())


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        content={
            "status": "ok",
            "last_update": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
            "data_loaded": _CACHED_DATA is not None,
            "auth_mode": "secured" if get_api_key() else "insecure-readonly",
        },
        headers=_no_store_headers(),
    )


@app.get("/metrics")
async def metrics(request: Request) -> JSONResponse:
    if not get_api_key():
        return JSONResponse(content={"error": "TV API key required for metrics"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=_no_store_headers())
    if not require_api_key(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED, headers=_no_store_headers())
    try:
        payload = _build_tv_data()
        return JSONResponse(
            content={
                "departments": _count_departments(payload),
                "employees_total": _count_all_employees(payload),
                "last_refresh": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
            },
            headers=_no_store_headers(),
        )
    except (OSError, ValueError, RuntimeError) as exc:
        log_exception("tv_metrics", exc)
        return JSONResponse(content={"error": "Internal server error"}, status_code=500, headers=_no_store_headers())


# ─── LAN IP helper ────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = str(s.getsockname()[0])
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# ─── Entry point ──────────────────────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Apelata din main.py cand este prezent flag-ul --tv-web."""
    mismatch = bootstrap_runtime_root("tv_server")
    logger = logging.getLogger("tv_server")
    ip = _local_ip()
    sep = "=" * 56
    log_info("[TV] BASE_DIR=%s", BASE_DIR)
    log_info("[TV] DATA_PATH=%s", DATA_FILE)
    if mismatch:
        log_info(mismatch)
    auth_warning = _tv_auth_warning()
    if auth_warning:
        log_warning(auth_warning)
    logger.warning("\n%s", sep)
    logger.warning("  AUTOLIV TV SERVER - pornit")
    logger.warning("  Local :  http://127.0.0.1:%s/tv", port)
    logger.warning("  Retea :  http://%s:%s/tv", ip, port)
    logger.warning("  Deschide URL-ul de mai sus pe fiecare TV")
    if auth_warning:
        logger.warning("  WARNING: TV API key lipseste; endpointurile read-only sunt publice.")
    logger.warning("%s\n", sep)
    uvicorn.run(app, host=host, port=port, log_level="warning")
