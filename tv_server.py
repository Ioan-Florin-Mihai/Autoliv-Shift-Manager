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

import json
import logging
import socket
import time
from datetime import date, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
DATA_FILE  = ROOT / "data" / "schedule_live.json"
STATIC_DIR = ROOT / "static"
TPL_DIR    = ROOT / "templates"

# ─── Constante domeniu (oglindite din schedule_store, fara import ca serverul
#     sa ramana fara dependinte si utilizabil cu --tv-web fara incarcarea aplicatiei complete) ──
ABSENCE_NAMES: frozenset[str] = frozenset({"CO", "CM", "ABSENT"})
COLOR_12H = "#C0392B"   # stocat in cell["colors"][nume_angajat]
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


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _load_schedule() -> dict:
    """Citeste schedule_live.json cu cache pe mtime pentru throughput stabil pe mai multe TV-uri."""
    global _LAST_MTIME, _CACHED_DATA
    if not DATA_FILE.exists():
        _CACHED_DATA = {"weeks": {}}
        _LAST_MTIME = 0.0
        return _CACHED_DATA

    mtime = DATA_FILE.stat().st_mtime
    if _CACHED_DATA is not None and mtime == _LAST_MTIME:
        return _CACHED_DATA

    with open(DATA_FILE, encoding="utf-8") as f:
        loaded = json.load(f)
    _CACHED_DATA = loaded if isinstance(loaded, dict) else {"weeks": {}}
    _LAST_MTIME = mtime
    return _CACHED_DATA


def _get_week(data: dict, d: date) -> dict:
    key = _week_start(d).isoformat()
    return data.get("weeks", {}).get(key) or {}


def _is_active(name: str) -> bool:
    return name.strip().upper() not in ABSENCE_NAMES


def _is_12h(colors: dict, employee: str) -> bool:
    """Returneaza True daca angajatul are culoarea de 12h (case-insensitive)."""
    for k, v in colors.items():
        if k.casefold() == employee.casefold():
            return (v or "").strip().upper() == COLOR_12H.upper()
    return False


def _has_weekend_data(week: dict) -> bool:
    """Returneaza True daca exista cel putin un angajat activ planificat Sambata sau Duminica."""
    for mode_rec in week.get("modes", {}).values():
        for dept_sched in mode_rec.get("schedule", {}).values():
            for day_name in ("Sambata", "Duminica"):
                for shift in SHIFTS:
                    cell = dept_sched.get(day_name, {}).get(shift, {})
                    for emp in cell.get("employees", []):
                        if _is_active(emp):
                            return True
    return False


def _get_display_days(current_week: dict, next_week: dict) -> list[str]:
    """
    CAZ 1 (normal): saptamana urmatoare Luni-Vineri.
    CAZ 2 (weekend publicat): saptamana curenta Sambata-Duminica + saptamana urmatoare Luni-Vineri.
    """
    has_weekend = _has_weekend_data(current_week) if current_week else False
    if has_weekend:
        return ["Sambata", "Duminica", "Luni", "Marti", "Miercuri", "Joi", "Vineri"]
    return ["Luni", "Marti", "Miercuri", "Joi", "Vineri"]


# ─── Main data builder ────────────────────────────────────────────────────────

def _build_tv_data() -> dict:
    raw          = _load_schedule()
    today        = date.today()
    current_week = _get_week(raw, today)
    next_week    = _get_week(raw, today + timedelta(days=7))

    display_days = _get_display_days(current_week, next_week)
    has_weekend = display_days[0] == "Sambata" if display_days else False

    # Fiecare zi afisata se mapeaza la saptamana din care face parte
    data_map: dict[str, dict] = {
        d: (current_week if d in WEEKEND_DAYS else next_week)
        for d in display_days
    }

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

    # Eticheta intervalului de saptamana (din saptamana urmatoare)
    week_label = next_week.get("week_label", "") if next_week else ""
    week_range = ""
    try:
        ws_str = next_week.get("week_start", "") if next_week else ""
        we_str = next_week.get("week_end",   "") if next_week else ""
        if ws_str and we_str:
            ws = date.fromisoformat(ws_str)
            we = date.fromisoformat(we_str)
            week_range = f"{ws.strftime('%d %b')} – {we.strftime('%d %b')}"
        if has_weekend and current_week.get("week_start"):
            cws = date.fromisoformat(current_week["week_start"])
            sat = cws + timedelta(days=5)
            week_range = f"Weekend {sat.strftime('%d %b')} + {week_range}"
    except Exception:  # noqa: BLE001
        pass

    # Construieste departamentele si planificarea pe fiecare mod
    departments: dict[str, list]  = {}
    schedule: dict[str, dict]     = {}

    for mode_name in MODE_NAMES:
        mode_rec_nxt  = next_week.get("modes", {}).get(mode_name, {}) if next_week else {}
        depts_list    = mode_rec_nxt.get("departments", [])
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
                        {
                            "name":    " ".join(e.split()),
                            "hours12": _is_12h(colors, e),
                        }
                        for e in emps if _is_active(e)
                    ]
                dept_data[day_name] = day_shifts
            mode_schedule[dept] = dept_data

        departments[mode_name] = depts_list
        schedule[mode_name]    = mode_schedule

    return {
        "has_weekend":    has_weekend,
        "display_days":   display_days,
        "day_dates":      day_dates,
        "day_dates_iso":  day_dates_iso,
        "today_iso":      today.isoformat(),
        "server_time_ms": int(time.time() * 1000),
        "rotation_step_ms": 10_000,
        "last_update_ms": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
        "week_label":     week_label,
        "week_range":     week_range,
        "departments":    departments,
        "schedule":       schedule,
    }


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


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/tv", response_class=HTMLResponse)
async def tv_page(_req: Request) -> HTMLResponse:
    html = (TPL_DIR / "tv.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/api/tv-data")
async def tv_data() -> JSONResponse:
    try:
        return JSONResponse(content=_build_tv_data())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(content={"error": str(exc)}, status_code=500)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "ok",
            "last_update": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
            "data_loaded": _CACHED_DATA is not None,
        }
    )


@app.get("/metrics")
async def metrics() -> JSONResponse:
    payload = _build_tv_data()
    return JSONResponse(
        content={
            "departments": _count_departments(payload),
            "employees_total": _count_all_employees(payload),
            "last_refresh": int(_LAST_MTIME * 1000) if _LAST_MTIME else 0,
        }
    )


# ─── LAN IP helper ────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


# ─── Entry point ──────────────────────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Apelata din main.py cand este prezent flag-ul --tv-web."""
    logger = logging.getLogger("tv_server")
    ip = _local_ip()
    sep = "=" * 56
    logger.warning("\n%s", sep)
    logger.warning("  AUTOLIV TV SERVER - pornit")
    logger.warning("  Local :  http://127.0.0.1:%s/tv", port)
    logger.warning("  Retea :  http://%s:%s/tv", ip, port)
    logger.warning("  Deschide URL-ul de mai sus pe fiecare TV")
    logger.warning("%s\n", sep)
    uvicorn.run(app, host=host, port=port, log_level="warning")
