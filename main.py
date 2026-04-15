# ============================================================
# AUTOLIV SHIFT MANAGER - PUNCT DE INTRARE
# ============================================================
# 
# Fișierul principal care pornește aplicația.
# Rulează: python main.py (din IDE) sau Autoliv Shift Manager.exe
#
# Flux:
#   1. Configureaza mediul Tcl/Tk (initializare runtime)
#   2. Importă UI-ul (dashboard) - care gestionează autentificarea
#   3. Pornește bucla główna a aplicației (GUI)
#
# NOTE: În modul .exe (PyInstaller), bootstrapping-ul e inclus automat.
#       Doar în dev mode (Python direct) e nevoie de setup suplimentar.
# ============================================================

import argparse
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from logic.app_config import get_config
from logic.app_logger import log_error, log_exception, log_info, log_warning
from logic.app_paths import BASE_DIR, bootstrap_runtime_root
from logic.runtime_bootstrap import configure_tk_runtime


def _global_crash_handler(exc_type, exc_value, exc_tb):
    """Handler global pentru excepții necapturate pe main thread."""
    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        import tkinter.messagebox as _mb
        _mb.showerror(
            "Eroare neașteptată",
            f"A apărut o eroare neașteptată:\n\n{err_text[:600]}\n\nReporniți aplicația.",
        )
    except Exception:
        pass
    log_error("exceptie necapturata: %s", err_text[:2000])


def _thread_crash_handler(args):
    """Handler global pentru excepții necapturate în thread-uri background."""
    _global_crash_handler(args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = _global_crash_handler
threading.excepthook = _thread_crash_handler


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autoliv Shift Manager")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--planner", action="store_true", help="Porneste interfata planner (implicit).")
    group.add_argument("--tv-web", action="store_true", help="Porneste serverul web pentru TV cu auto-restart.")
    group.add_argument("--kiosk", action="store_true", help="Porneste serverul TV si browserul in mod kiosk.")
    parser.add_argument("--tv-worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _self_command(*extra_args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra_args]
    return [sys.executable, str(Path(__file__).resolve()), *extra_args]


def _run_planner() -> None:
    log_info("[BOOT] BASE_DIR=%s", BASE_DIR)
    mismatch = bootstrap_runtime_root("planner")
    if mismatch:
        log_error(mismatch)
    configure_tk_runtime()
    from ui.dashboard import run_app
    run_app()


def _run_tv_worker() -> None:
    log_info("[BOOT] BASE_DIR=%s", BASE_DIR)
    mismatch = bootstrap_runtime_root("tv_server")
    if mismatch:
        log_error(mismatch)
    from tv_server import start_server
    config = get_config()
    start_server(
        host=str(config.get("server_host", "0.0.0.0")),
        port=int(config.get("server_port", 8000)),
    )


def _supervise_tv_server() -> None:
    config = get_config()
    restart_delay = max(1, int(config.get("server_restart_delay", 5)))
    while True:
        log_info("server_tv: pornire worker")
        child = subprocess.Popen(_self_command("--tv-worker"))
        exit_code = child.wait()
        if exit_code == 0:
            log_info("server_tv: worker oprit curat")
            return
        log_warning("server_tv: worker oprit cu cod %s, restart in %s secunde", exit_code, restart_delay)
        time.sleep(restart_delay)


def _detect_browser_command(url: str) -> list[str] | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("msedge.exe"),
    ]
    browser = next((item for item in candidates if item), None)
    if not browser:
        return None
    if "edge" in browser.lower():
        return [
            browser,
            "--kiosk",
            url,
            "--edge-kiosk-type=fullscreen",
            "--no-first-run",
            "--disable-features=msImplicitSignin",
        ]
    return [browser, "--kiosk", url, "--no-first-run"]


def _run_kiosk() -> None:
    config = get_config()
    port = int(config.get("server_port", 8000))
    server_thread = threading.Thread(target=_supervise_tv_server, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{port}/tv"
    browser_delay = max(1, int(config.get("browser_restart_delay", 3)))
    browser_cmd = _detect_browser_command(url)
    if browser_cmd is None:
        raise RuntimeError("Nu am gasit Microsoft Edge sau Google Chrome pentru modul kiosk.")
    log_info("kiosk: pornit pentru %s", url)
    while True:
        browser = subprocess.Popen(browser_cmd)
        exit_code = browser.wait()
        log_warning("kiosk: browser inchis cu cod %s, relansare in %s secunde", exit_code, browser_delay)
        time.sleep(browser_delay)


def run_cli(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    try:
        if args.tv_worker:
            _run_tv_worker()
        elif args.tv_web:
            _supervise_tv_server()
        elif args.kiosk:
            _run_kiosk()
        else:
            _run_planner()
    except Exception as exc:
        log_exception("main", exc)
        raise


if __name__ == "__main__":
    run_cli()
