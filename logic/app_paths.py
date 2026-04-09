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

import shutil
import sys
from pathlib import Path

# ── Funcții de rezolvare cale ──────────────────────────────────

def get_base_path() -> Path:
    """
    Returnează directorul rădăcină al aplicației.
    - EXE  → folderul în care se află .exe-ul (portabil)
    - DEV  → rădăcina proiectului (parent al logic/)
    """
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
EXPORT_DIR  = BASE_DIR / "Exports"  # Export Excel
ASSETS_DIR  = BASE_DIR / "assets"   # Logo, iconuri
BACKUP_DIR  = BASE_DIR / "backups"  # Backup-uri planificări

# Backward-compatibility aliases (modulele vechi importă APP_DIR)
APP_DIR     = BASE_DIR
BACKUPS_DIR = BACKUP_DIR

# ── Diagnostic startup ────────────────────────────────────────

print(f"[app_paths] RUN MODE:   {'EXE' if getattr(sys, 'frozen', False) else 'DEV'}")
print(f"[app_paths] BASE_DIR:   {BASE_DIR}")
print(f"[app_paths] DATA_DIR:   {DATA_DIR}")
print(f"[app_paths] BUNDLE_DIR: {BUNDLE_DIR}")

# ── Auto-creare directoare critice ────────────────────────────

for _d in (DATA_DIR, ASSETS_DIR, EXPORT_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)


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
