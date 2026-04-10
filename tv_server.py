"""
tv_server.py
─────────────────────────────────────────────────────────────
FastAPI web TV server — Autoliv Shift Manager

Serves an industrial dashboard to factory TVs over LAN.
All TVs open the same URL → perfectly synced, zero interaction.

Usage:
    python main.py --tv-web

TV URL:
    http://<LAN_IP>:8000/tv
"""

from __future__ import annotations

import json
import socket
from datetime import date, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
DATA_FILE  = ROOT / "data" / "schedule_data.json"
STATIC_DIR = ROOT / "static"
TPL_DIR    = ROOT / "templates"

# ─── Domain constants (mirrored from schedule_store, no import to keep server
#     dependency-free and usable with --tv-web without loading the full app) ──
ABSENCE_NAMES: frozenset[str] = frozenset({"CO", "CM", "ABSENT"})
COLOR_12H = "#C0392B"   # stored in cell["colors"][employee_name]
SHIFTS     = ["Sch1", "Sch2", "Sch3"]
DAYS       = [
    ("Luni", 0), ("Marti", 1), ("Miercuri", 2),
    ("Joi", 3),  ("Vineri", 4), ("Sambata", 5), ("Duminica", 6),
]
DAY_OFFSETS   = {name: offset for name, offset in DAYS}
WEEKEND_DAYS  = frozenset({"Sambata", "Duminica"})
MODE_NAMES    = ["Magazie", "Bucle"]


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _load_json() -> dict:
    """Read schedule_data.json fresh on every call — no caching."""
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def _get_week(data: dict, d: date) -> dict:
    key = _week_start(d).isoformat()
    return data.get("weeks", {}).get(key) or {}


def _is_active(name: str) -> bool:
    return name.strip().upper() not in ABSENCE_NAMES


def _is_12h(colors: dict, employee: str) -> bool:
    """Return True if the employee is assigned a 12h colour (case-insensitive)."""
    for k, v in colors.items():
        if k.casefold() == employee.casefold():
            return (v or "").strip().upper() == COLOR_12H.upper()
    return False


def _has_weekend_data(week: dict) -> bool:
    """Return True if any active employee is scheduled on Sat or Sun."""
    for mode_rec in week.get("modes", {}).values():
        for dept_sched in mode_rec.get("schedule", {}).values():
            for day_name in ("Sambata", "Duminica"):
                for shift in SHIFTS:
                    cell = dept_sched.get(day_name, {}).get(shift, {})
                    for emp in cell.get("employees", []):
                        if _is_active(emp):
                            return True
    return False


# ─── Main data builder ────────────────────────────────────────────────────────

def _build_tv_data() -> dict:
    raw          = _load_json()
    today        = date.today()
    current_week = _get_week(raw, today)
    next_week    = _get_week(raw, today + timedelta(days=7))

    has_weekend = _has_weekend_data(current_week) if current_week else False

    if has_weekend:
        display_days = ["Sambata", "Duminica", "Luni", "Marti", "Miercuri", "Joi", "Vineri"]
    else:
        display_days = ["Luni", "Marti", "Miercuri", "Joi", "Vineri"]

    # Each display day maps to the week record it belongs to
    data_map: dict[str, dict] = {
        d: (current_week if d in WEEKEND_DAYS else next_week)
        for d in display_days
    }

    # Compute display date labels per day
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

    # Week range label (from next week)
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

    # Build per-mode departments and schedule
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
        "week_label":     week_label,
        "week_range":     week_range,
        "departments":    departments,
        "schedule":       schedule,
    }


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
    """Called from main.py when --tv-web flag is present."""
    ip = _local_ip()
    sep = "=" * 56
    print(f"\n{sep}")
    print("  AUTOLIV TV SERVER — pornit")
    print(f"  Local :  http://127.0.0.1:{port}/tv")
    print(f"  Rețea :  http://{ip}:{port}/tv")
    print("  Deschide URL-ul de mai sus pe fiecare TV")
    print(f"{sep}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
