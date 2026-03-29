# ============================================================
# MODUL: app_paths.py
# Defineste toate caile importante ale aplicatiei.
# Functioneaza atat in modul dezvoltare (Python direct) cat si
# in modul executabil (.exe generat cu PyInstaller).
# ============================================================

import shutil
import sys
from pathlib import Path


def get_app_dir():
    """
    Returneaza directorul radacina al aplicatiei.
    - Daca ruleaza ca .exe → directorul unde se afla .exe-ul
    - Daca ruleaza ca Python → directorul proiectului
    """
    if getattr(sys, "frozen", False):
        # Mod .exe — executabilul e in root-ul aplicatiei
        return Path(sys.executable).resolve().parent
    # Mod dezvoltare — urcam 2 nivele din logic/ -> root/
    return Path(__file__).resolve().parent.parent


def get_bundle_dir():
    """
    Returneaza directorul unde PyInstaller a extras fisierele
    embedded (assets, data) la rularea .exe-ului.
    In modul dezvoltare, e acelasi cu radacina proiectului.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Directorul temporar unde PyInstaller extrage fisierele
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


# ── Cai globale utilizate in toata aplicatia ──────────────────
APP_DIR    = get_app_dir()     # Radacina aplicatiei (unde e .exe sau proiectul)
BUNDLE_DIR = get_bundle_dir()  # Fisiere embedded (assets, data default)
DATA_DIR   = APP_DIR / "data"  # Folder date utilizzator (schedule, users etc.)
EXPORT_DIR = APP_DIR / "Exports"  # Folder export Excel
ASSETS_DIR = APP_DIR / "assets"   # Imagini, iconuri


def ensure_directory(path: Path):
    """Creaza directorul daca nu exista (inclusiv subdirectoare)."""
    path.mkdir(parents=True, exist_ok=True)


def ensure_runtime_file(relative_path: str):
    """
    Asigura ca un fisier de date exista in APP_DIR.
    Daca lipseste si exista o versiune default in BUNDLE_DIR,
    o copiaza automat (util la primul rulaj al .exe-ului).
    Returneaza calea finala a fisierului.
    """
    target_path = APP_DIR / relative_path
    source_path = BUNDLE_DIR / relative_path

    ensure_directory(target_path.parent)

    # Copie fisierul default din bundle doar daca target-ul lipseste
    if not target_path.exists() and source_path.exists():
        shutil.copy2(source_path, target_path)

    return target_path
