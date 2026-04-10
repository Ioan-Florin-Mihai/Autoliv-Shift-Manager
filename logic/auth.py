# ============================================================
# MODUL: auth.py - AUTENTIFICARE SI MANAGEMENT UTILIZATORI
# ============================================================
#
# Functionalitati:
#   - Verificare credentiale cu bcrypt (cost factor 12)
#   - Suport multi-utilizator (users.json = lista de obiecte)
#   - Protectie brute-force: blocare 60s dupa 5 incercari esuate
#   - Schimbare parola cu validare lungime minima (8 caractere)
#   - Adaugare si stergere utilizatori (rol admin)
#
# Format users.json (lista):
#   [
#     {"username": "admin", "password_hash": "$2b$12$...", "role": "admin"},
#     {"username": "user1", "password_hash": "$2b$12$...", "role": "user"}
#   ]
#
# SECURITATE:
#   - users.json NU este inclus in .exe (nu e in PyInstaller datas)
#   - Fisierul trebuie furnizat separat de administrator
#   - app_paths.get_sensitive_path() nu face bundle-copy
# ============================================================

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import bcrypt

from logic.app_config import get_config
from logic.app_logger import log_exception, log_info, log_warning
from logic.app_paths import get_sensitive_path

# Calea fisierului cu credentiale â€” NU este copiat din bundle
USERS_PATH: Path = get_sensitive_path("data/users.json")

# Hash dummy pre-calculat folosit pentru a preveni timing-attack cand
# username-ul nu exista (evita diferenta de timp bcrypt vs. no-bcrypt).
# Costul redus (4) minimizeaza overhead-ul in test; in productie e neobservabil.
_DUMMY_HASH: bytes = bcrypt.hashpw(b"timing_attack_prevention_dummy", bcrypt.gensalt(rounds=4))

# â”€â”€ Protectie brute-force â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_MAX_ATTEMPTS    = 5      # Incercari inainte de blocare
_LOCKOUT_SECONDS = 60     # Durata blocarii (secunde)
_bf_lock         = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}  # username -> [timestamps]


# â”€â”€ Operatii pe fisier â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _load_users() -> list[dict]:
    """
    Citeste lista de utilizatori din users.json.
    Suporta atat format vechi (dict unic) cat si format nou (lista).
    Daca fisierul lipseste, CREEAZA un cont admin default.
    """
    if not USERS_PATH.exists():
        log_warning(
            "auth: users.json lipseste (%s) — se creeaza cont admin default.",
            USERS_PATH,
        )
        default_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=12))
        default_users = [
            {
                "username": "admin",
                "password_hash": default_hash.decode("utf-8"),
                "role": "admin",
                "must_change_password": True,
            }
        ]
        _save_users(default_users)
        log_info(
            "auth: cont admin creat (user: admin, parola: admin123). "
            "SCHIMBATI PAROLA IMEDIAT!"
        )
        return default_users
    try:
        with USERS_PATH.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"users.json este corupt: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Nu se poate citi users.json: {exc}") from exc

    # Migrare automata format vechi (dict) â†’ format nou (lista)
    if isinstance(raw, dict):
        log_warning("auth: users.json in format vechi (dict), se migreaza automat la lista.")
        raw = [{
            "username":      raw.get("username", ""),
            "password_hash": raw.get("password_hash", ""),
            "role":          "admin",
        }]
        _save_users(raw)   # scrie imediat formatul nou

    if not isinstance(raw, list):
        raise ValueError("Format invalid users.json: se asteapta o lista.")

    return raw


def _save_users(users: list[dict]) -> None:
    """Scrie lista de utilizatori in users.json â€” scriere atomica."""
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=USERS_PATH.parent, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                json.dump(users, tmp, ensure_ascii=False, indent=2)
        except Exception:
            os.unlink(tmp_path)
            raise
        os.replace(tmp_path, USERS_PATH)
    except OSError as exc:
        log_exception("auth_save_users", exc)
        raise


# â”€â”€ Brute-force helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _is_locked_out(username: str) -> tuple[bool, float]:
    """Returneaza (este_blocat, secunde_ramase)."""
    with _bf_lock:
        now     = time.monotonic()
        attempts = [t for t in _failed_attempts.get(username, [])
                    if now - t < _LOCKOUT_SECONDS]
        _failed_attempts[username] = attempts
        if len(attempts) >= _MAX_ATTEMPTS:
            oldest   = min(attempts)
            remaining = _LOCKOUT_SECONDS - (now - oldest)
            return True, max(0.0, remaining)
        return False, 0.0


def _record_failure(username: str) -> None:
    with _bf_lock:
        lst = _failed_attempts.get(username, [])
        lst.append(time.monotonic())
        _failed_attempts[username] = lst


def _clear_failures(username: str) -> None:
    with _bf_lock:
        _failed_attempts.pop(username, None)


def _find_user(users: list[dict], username: str) -> dict | None:
    """Cauta utilizatorul dupa username (case-insensitive)."""
    return next(
        (u for u in users if u.get("username", "").casefold() == username.casefold()),
        None,
    )


def _normalize_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value == "user":
        return "operator"
    return value


# â”€â”€ API public â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def verify_login(username: str, password: str) -> bool:
    """
    Verifica credentialele. Returneaza True/False.
    Compatibil cu apelul existent din dashboard.py.
    Arunca exceptie daca fisierul users.json lipseste/e corupt.
    """
    success, _msg = verify_login_detailed(username, password)
    return success


def verify_login_detailed(username: str, password: str) -> tuple[bool, str]:
    """
    Verifica credentialele si returneaza (succes, mesaj_eroare).
    Mesajul este intentionat generic pentru a nu dezvalui ce camp e gresit.
    """
    if not username or not password:
        return False, "Username si parola sunt obligatorii."

    # Validare baza â€” previne injectie prin input lung
    if len(username) > 128 or len(password) > 256:
        return False, "Input prea lung."

    # Verificare blocare brute-force
    locked, remaining = _is_locked_out(username.casefold())
    if locked:
        log_warning("auth: login blocat pentru '%s' (%.0fs ramasi)", username, remaining)
        return False, f"Prea multe incercari esuate. Asteptati {remaining:.0f} secunde."

    # Incarcare utilizatori
    try:
        users = _load_users()
    except Exception:
        raise   # Propagam â€” dashboard.py afiseaza eroarea de configurare

    user = _find_user(users, username)
    if user is None:
        # Executam bcrypt dummy pentru a preveni timing-attack bazat pe timp raspuns
        bcrypt.checkpw(b"dummy", _DUMMY_HASH)
        _record_failure(username.casefold())
        return False, "Username sau parola incorecta."

    password_hash = user.get("password_hash", "")
    if not password_hash:
        _record_failure(username.casefold())
        return False, "Configuratie cont invalida. Contactati administratorul."

    try:
        is_valid = bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception as exc:
        log_exception("auth_bcrypt_check", exc)
        return False, "Eroare interna la verificarea parolei."

    if not is_valid:
        _record_failure(username.casefold())
        return False, "Username sau parola incorecta."

    _clear_failures(username.casefold())
    log_info("auth: login reusit pentru '%s'", username)
    return True, ""


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """
    Schimba parola unui utilizator.
    Returneaza (succes, mesaj).
    """
    if len(new_password) < 8:
        return False, "Parola noua trebuie sa aiba cel putin 8 caractere."
    if len(new_password) > 256:
        return False, "Parola noua este prea lunga."
    if new_password == old_password:
        return False, "Parola noua trebuie sa fie diferita de cea curenta."

    # Verifica parola curenta (include si brute-force guard)
    try:
        valid, err = verify_login_detailed(username, old_password)
    except Exception as exc:
        return False, f"Eroare la verificare: {exc}"
    if not valid:
        return False, f"Parola curenta gresita: {err}"

    # Actualizeaza hash-ul
    try:
        users = _load_users()
    except Exception as exc:
        return False, f"Eroare la citirea utilizatorilor: {exc}"

    user = _find_user(users, username)
    if user is None:
        return False, "Utilizatorul nu exista."

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    user["password_hash"] = new_hash
    user.pop("must_change_password", None)

    try:
        _save_users(users)
    except Exception as exc:
        return False, f"Eroare la salvarea parolei: {exc}"

    log_info("auth: parola schimbata pentru '%s'", username)
    return True, "Parola a fost schimbata cu succes."


def add_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    """Adauga un utilizator nou. Returneaza (succes, mesaj)."""
    config = get_config()
    username = username.strip()
    role = _normalize_role(role)
    if not username or not password:
        return False, "Username si parola sunt obligatorii."
    if len(username) > 64:
        return False, "Username prea lung (max 64 caractere)."
    if len(password) < 8:
        return False, "Parola trebuie sa aiba cel putin 8 caractere."
    if len(password) > 256:
        return False, "Parola este prea lunga."
    if role not in {"admin", "operator"}:
        return False, "Rol invalid. Valori acceptate: admin, operator."

    try:
        users = _load_users()
    except FileNotFoundError:
        users = []
    except Exception as exc:
        return False, f"Eroare: {exc}"

    if _find_user(users, username) is not None:
        return False, f"Utilizatorul '{username}' exista deja."
    if len(users) >= int(config.get("max_users", 3)):
        return False, f"Sistemul permite maximum {int(config.get('max_users', 3))} utilizatori."

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    users.append({"username": username, "password_hash": password_hash, "role": role})

    try:
        _save_users(users)
    except Exception as exc:
        return False, f"Eroare la salvare: {exc}"

    log_info("auth: utilizator nou adaugat '%s' (rol: %s)", username, role)
    return True, f"Utilizatorul '{username}' a fost adaugat."


def delete_user(username: str, requesting_username: str) -> tuple[bool, str]:
    """
    Sterge un utilizator. Nu se poate sterge propriul cont.
    Returneaza (succes, mesaj).
    """
    if username.casefold() == requesting_username.casefold():
        return False, "Nu iti poti sterge propriul cont."

    try:
        users = _load_users()
    except Exception as exc:
        return False, f"Eroare: {exc}"

    initial_count = len(users)
    users = [u for u in users if u.get("username", "").casefold() != username.casefold()]

    if len(users) == initial_count:
        return False, f"Utilizatorul '{username}' nu a fost gasit."
    if len(users) == 0:
        return False, "Nu se poate sterge ultimul utilizator."

    try:
        _save_users(users)
    except Exception as exc:
        return False, f"Eroare la salvare: {exc}"

    log_info("auth: utilizatorul '%s' sters de catre '%s'", username, requesting_username)
    return True, f"Utilizatorul '{username}' a fost sters."


def list_users() -> list[dict]:
    """
    Returneaza lista utilizatorilor (fara campul password_hash).
    """
    try:
        users = _load_users()
    except Exception:
        return []
    return [{"username": u.get("username", ""), "role": _normalize_role(u.get("role", "operator"))} for u in users]


def get_user_role(username: str) -> str:
    try:
        users = _load_users()
    except Exception:
        return "operator"
    user = _find_user(users, username)
    if not user:
        return "operator"
    return _normalize_role(user.get("role", "operator")) or "operator"


def is_admin(username: str) -> bool:
    return get_user_role(username) == "admin"


def must_change_password(username: str) -> bool:
    """Returneaza True dacă utilizatorul trebuie să schimbe parola (flag setat la creare cont)."""
    try:
        users = _load_users()
        user = _find_user(users, username)
        if user:
            return bool(user.get("must_change_password", False))
    except Exception:
        pass
    return False

