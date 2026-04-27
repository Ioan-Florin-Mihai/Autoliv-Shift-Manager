# ============================================================
# MODUL: app_paths.py - GESTIONARE CĂI APLICAȚIE
# ============================================================
#
# Singura sursă de adevăr pentru TOATE căile din aplicație.
#
# Regulă de aur:
#   - EXE (PyInstaller): BASE_DIR = folderul unde se află .exe-ul
#   - DEV (Python):       BASE_DIR = rădăcina proiectului
#   - USB (portabil):     funcționează identic cu EXE
#
# NICIUN alt modul nu trebuie să folosească __file__ sau
# os.path.dirname() direct. Totul se importă de aici.
# ============================================================

import os
import shutil
import sys
import tempfile
from pathlib import Path

# ── Funcții de rezolvare cale ──────────────────────────────────

def _app_root_override() -> Path | None:
    value = os.environ.get("APP_ROOT", "").strip()
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except OSError:
        return Path(value).expanduser()

def get_base_path() -> Path:
    """
    Returnează directorul rădăcină al aplicației.
    - EXE  → folderul în care se află .exe-ul (portabil)
    - DEV  → rădăcina proiectului (parent al logic/)
    """
    app_root = _app_root_override()
    if app_root is not None:
        return app_root
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    """
    Returnează directorul temporar unde PyInstaller extrage
    fișierele embedded (assets, data default).
    În DEV mode returnează rădăcina proiectului.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


# ── Căi globale — SINGURA SURSĂ DE ADEVĂR ─────────────────────

BASE_DIR    = get_base_path()       # Rădăcina aplicației
BUNDLE_DIR  = get_bundle_dir()      # Fișiere PyInstaller extracted
DATA_DIR    = BASE_DIR / "data"     # Date utilizator (users, schedule)
ASSETS_DIR  = BASE_DIR / "assets"   # Logo, iconuri
BACKUP_DIR  = BASE_DIR / "backups"  # Backup-uri planificări
SCHEDULE_LIVE = DATA_DIR / "schedule_live.json"
SCHEDULE_DRAFT = DATA_DIR / "schedule_draft.json"
SCHEDULE_LEGACY = DATA_DIR / "schedule_data.json"
RUNTIME_FILE = DATA_DIR / "runtime_root.txt"

# Backward-compatibility aliases (modulele vechi importă APP_DIR)
APP_DIR     = BASE_DIR
BACKUPS_DIR = BACKUP_DIR

# ── Auto-creare directoare critice ────────────────────────────

for _d in (DATA_DIR, ASSETS_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def get_runtime_root_path() -> Path:
    return RUNTIME_FILE


def _shared_runtime_root_path() -> Path:
    app_root = os.environ.get("APP_ROOT", "").strip()
    if app_root:
        root = Path(app_root).expanduser().resolve()
        ensure_directory(root)
        return root / "runtime_root.txt"

    temp_root = Path(tempfile.gettempdir()).resolve() / "Autoliv_Shift_Manager"
    ensure_directory(temp_root)
    return temp_root / "runtime_root.txt"


def _read_runtime_root(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def _write_runtime_root(path: Path, root_value: Path) -> None:
    ensure_directory(path.parent)
    path.write_text(str(root_value), encoding="utf-8")


def bootstrap_runtime_root(role: str) -> str | None:
    current_root = BASE_DIR.resolve()
    local_marker = RUNTIME_FILE
    shared_marker = _shared_runtime_root_path()
    messages: list[str] = []

    existing_local_root = _read_runtime_root(local_marker)
    if existing_local_root:
        try:
            resolved_existing_local_root = Path(existing_local_root).expanduser().resolve()
        except OSError:
            resolved_existing_local_root = Path(existing_local_root)
        if resolved_existing_local_root != current_root:
            messages.append(
                "⚠ Runtime mismatch detected: different BASE_DIR between components "
                f"({role}: {current_root}, runtime_file: {resolved_existing_local_root})"
            )
    _write_runtime_root(local_marker, current_root)

    app_root = os.environ.get("APP_ROOT", "").strip()
    if app_root:
        try:
            hinted_root = Path(app_root).expanduser().resolve()
        except OSError:
            hinted_root = Path(app_root).expanduser()
        if hinted_root != current_root:
            messages.append(
                "⚠ Runtime mismatch detected: different BASE_DIR between components "
                f"({role}: {current_root}, APP_ROOT: {hinted_root})"
            )

    existing_root = _read_runtime_root(shared_marker)
    if existing_root:
        try:
            resolved_existing_root = Path(existing_root).expanduser().resolve()
        except OSError:
            resolved_existing_root = Path(existing_root)
        if resolved_existing_root != current_root:
            messages.append(
                "⚠ Runtime mismatch detected: different BASE_DIR between components "
                f"({role}: {current_root}, marker: {resolved_existing_root})"
            )

    _write_runtime_root(shared_marker, current_root)
    return " | ".join(messages) if messages else None


# ── Utilități cale ─────────────────────────────────────────────

def ensure_directory(path: Path):
    """Creează directorul dacă nu există (inclusiv subdirectoare)."""
    path.mkdir(parents=True, exist_ok=True)


def ensure_runtime_file(relative_path: str) -> Path:
    """
    Asigură că un fișier de date există în BASE_DIR.
    Dacă lipsește și există o versiune default în BUNDLE_DIR,
    o copiază automat (util la primul rulaj al .exe-ului).

    NU folosi pentru fișiere sensibile → get_sensitive_path().
    """
    target_path = BASE_DIR / relative_path
    source_path = BUNDLE_DIR / relative_path

    ensure_directory(target_path.parent)

    if not target_path.exists() and source_path.exists():
        shutil.copy2(source_path, target_path)

    return target_path


def get_sensitive_path(relative_path: str) -> Path:
    """
    Returnează calea unui fișier sensibil din BASE_DIR.
    NU copiază niciodată din bundle — fișierul trebuie să existe deja
    (pus de administrator) sau modulul apelant trebuie să creeze un default.
    """
    target_path = BASE_DIR / relative_path
    ensure_directory(target_path.parent)
    return target_path
