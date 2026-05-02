# ============================================================
# MODUL: auth.py - AUTENTIFICARE SI MANAGEMENT UTILIZATORI
# ============================================================
#
# Functionalitati:
#   - verificare credentiale cu bcrypt (cost factor 12)
#   - suport multi-utilizator (users.json = lista de obiecte)
#   - protectie brute-force: blocare 60s dupa 5 incercari esuate
#   - schimbare parola cu validare lungime minima (8 caractere)
#   - adaugare si stergere utilizatori (rol admin)
#
# Release local:
#   - la primul rulaj se creeaza contul admin local cu parola initiala documentata
#   - starile bootstrap vechi sunt migrate automat la credentialul local curent
# ============================================================

import json
import secrets
import string
import threading
import time
from datetime import datetime
from pathlib import Path

import bcrypt

from logic.app_config import get_config
from logic.app_logger import log_exception, log_info, log_warning
from logic.app_paths import get_sensitive_path
from logic.internal_credentials import (
    BOOTSTRAP_PASSWORD_LENGTH,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
)
from logic.utils.io import atomic_write_json

USERS_PATH: Path = get_sensitive_path("data/users.json")
BOOTSTRAP_INFO_PATH: Path = get_sensitive_path("data/bootstrap_admin.json")
ADMIN_USERNAME = DEFAULT_ADMIN_USERNAME
ADMIN_PASSWORD = DEFAULT_ADMIN_PASSWORD
_LEGACY_ADMIN_HASHES = {
    "$2b$12$ggzp6vQQ8MJm3RfngmJxCuF.ZfMaA.JSuQsSkNGOmIb8kyCT.RyDW",
}

_DUMMY_HASH: bytes = bcrypt.hashpw(b"timing_attack_prevention_dummy", bcrypt.gensalt(rounds=4))

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
_bf_lock = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}


def _generate_bootstrap_password(length: int = BOOTSTRAP_PASSWORD_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(12, int(length))))


def _resolve_bootstrap_info_path() -> Path:
    users_path = Path(USERS_PATH)
    if users_path.name.casefold() == "users.json":
        return users_path.with_name("bootstrap_admin.json")
    return BOOTSTRAP_INFO_PATH


def _write_bootstrap_info(username: str, password: str) -> None:
    payload = {
        "username": username,
        "password": password,
        "must_change_password": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    atomic_write_json(_resolve_bootstrap_info_path(), payload)


def _remove_bootstrap_info() -> None:
    bootstrap_path = _resolve_bootstrap_info_path()
    if bootstrap_path.exists():
        try:
            bootstrap_path.unlink()
        except OSError as exc:
            log_warning("auth: nu pot sterge %s: %s", bootstrap_path, exc)


def get_bootstrap_info_path() -> Path:
    return _resolve_bootstrap_info_path()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _create_bootstrap_admin() -> list[dict]:
    default_users = [
        {
            "username": ADMIN_USERNAME,
            "password_hash": _hash_password(ADMIN_PASSWORD),
            "role": "admin",
        }
    ]
    _save_users(default_users)
    _remove_bootstrap_info()
    log_warning(
        "auth: users.json lipseste (%s) - a fost creat contul admin local implicit",
        USERS_PATH,
    )
    return default_users


def _load_users() -> list[dict]:
    """Citeste lista de utilizatori din users.json."""
    if not USERS_PATH.exists():
        return _create_bootstrap_admin()

    try:
        with USERS_PATH.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"users.json este corupt: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Nu se poate citi users.json: {exc}") from exc

    if isinstance(raw, dict):
        log_warning("auth: users.json in format vechi (dict), se migreaza automat la lista.")
        raw = [{
            "username": raw.get("username", ""),
            "password_hash": raw.get("password_hash", ""),
            "role": "admin",
        }]
        _save_users(raw)

    if not isinstance(raw, list):
        raise ValueError("Format invalid users.json: se asteapta o lista.")

    changed = False
    bootstrap_path = _resolve_bootstrap_info_path()
    for user in raw:
        if (
            user.get("username", "").casefold() == ADMIN_USERNAME
            and isinstance(user.get("password_hash"), str)
            and user["password_hash"] in _LEGACY_ADMIN_HASHES
        ):
            user["password_hash"] = _hash_password(ADMIN_PASSWORD)
            user.pop("must_change_password", None)
            _remove_bootstrap_info()
            changed = True
            log_warning("auth: hash admin legacy inlocuit cu credentialul local curent.")
        elif bool(user.get("must_change_password", False)):
            password_hash = user.get("password_hash", "")
            if not isinstance(password_hash, str) or not password_hash:
                continue
            try:
                if bootstrap_path.exists():
                    payload = json.loads(bootstrap_path.read_text(encoding="utf-8"))
                    bootstrap_password = str(payload.get("password") or "")
                    if bootstrap_password and bcrypt.checkpw(
                        bootstrap_password.encode("utf-8"),
                        password_hash.encode("utf-8"),
                    ):
                        user["password_hash"] = _hash_password(ADMIN_PASSWORD)
                        user.pop("must_change_password", None)
                        _remove_bootstrap_info()
                        changed = True
                        log_warning("auth: stare bootstrap migrata la credentialul admin local curent.")
            except (OSError, json.JSONDecodeError, ValueError):
                pass

    if changed:
        _save_users(raw)

    return raw


def _save_users(users: list[dict]) -> None:
    """Scrie lista de utilizatori in users.json prin scriere atomica."""
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_json(USERS_PATH, users)
    except OSError as exc:
        log_exception("auth_save_users", exc)
        raise


def _is_locked_out(username: str) -> tuple[bool, float]:
    with _bf_lock:
        now = time.monotonic()
        attempts = [t for t in _failed_attempts.get(username, []) if now - t < _LOCKOUT_SECONDS]
        _failed_attempts[username] = attempts
        if len(attempts) >= _MAX_ATTEMPTS:
            oldest = min(attempts)
            remaining = _LOCKOUT_SECONDS - (now - oldest)
            return True, max(0.0, remaining)
        return False, 0.0


def get_lockout_remaining_seconds(username: str) -> int:
    """Returneaza secundele ramase de blocare pentru afisarea non-blocanta in UI."""
    if not username:
        return 0
    locked, remaining = _is_locked_out(username.casefold())
    return int(round(remaining)) if locked else 0


def _record_failure(username: str) -> None:
    with _bf_lock:
        lst = _failed_attempts.get(username, [])
        lst.append(time.monotonic())
        _failed_attempts[username] = lst


def _clear_failures(username: str) -> None:
    with _bf_lock:
        _failed_attempts.pop(username, None)


def _find_user(users: list[dict], username: str) -> dict | None:
    return next((u for u in users if u.get("username", "").casefold() == username.casefold()), None)


def _normalize_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value == "user":
        return "operator"
    return value


def verify_login(username: str, password: str) -> bool:
    success, _msg = verify_login_detailed(username, password)
    return success


def verify_login_detailed(
    username: str,
    password: str,
    allow_password_change_only: bool = False,
) -> tuple[bool, str]:
    if not username or not password:
        return False, "Username si parola sunt obligatorii."

    if len(username) > 128 or len(password) > 256:
        return False, "Input prea lung."

    locked, remaining = _is_locked_out(username.casefold())
    if locked:
        log_warning("auth: login blocat pentru '%s' (%.0fs ramasi)", username, remaining)
        return False, f"Prea multe incercari esuate. Asteptati {remaining:.0f} secunde."

    users_existed_before_login = USERS_PATH.exists()
    users = _load_users()
    bootstrap_hint = f"Parola initiala pentru admin este {ADMIN_PASSWORD}."

    user = _find_user(users, username)
    if user is None:
        bcrypt.checkpw(b"dummy", _DUMMY_HASH)
        _record_failure(username.casefold())
        if not users_existed_before_login and _resolve_bootstrap_info_path().exists():
            return False, bootstrap_hint
        return False, "Username sau parola incorecta."

    password_hash = user.get("password_hash", "")
    if not isinstance(password_hash, str) or not password_hash:
        _record_failure(username.casefold())
        return False, "Configuratie cont invalida. Contactati administratorul."

    try:
        is_valid = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError as exc:
        log_exception("auth_bcrypt_check", exc)
        return False, "Eroare interna la verificarea parolei."

    if not is_valid:
        _record_failure(username.casefold())
        if not users_existed_before_login and _resolve_bootstrap_info_path().exists():
            return False, bootstrap_hint
        return False, "Username sau parola incorecta."

    if bool(user.get("must_change_password", False)) and not allow_password_change_only:
        _clear_failures(username.casefold())
        user["password_hash"] = _hash_password(ADMIN_PASSWORD)
        user.pop("must_change_password", None)
        _save_users(users)
        _remove_bootstrap_info()
        log_warning("auth: stare must_change_password migrata pentru '%s'.", username)
        return True, ""

    _clear_failures(username.casefold())
    log_info("auth: login reusit pentru '%s'", username)
    return True, ""


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 8:
        return False, "Parola noua trebuie sa aiba cel putin 8 caractere."
    if len(new_password) > 256:
        return False, "Parola noua este prea lunga."
    if new_password == old_password:
        return False, "Parola noua trebuie sa fie diferita de cea curenta."

    try:
        valid, err = verify_login_detailed(username, old_password, allow_password_change_only=True)
    except (OSError, ValueError) as exc:
        return False, f"Eroare la verificare: {exc}"
    if not valid:
        return False, f"Parola curenta gresita: {err}"

    try:
        users = _load_users()
    except (OSError, ValueError) as exc:
        return False, f"Eroare la citirea utilizatorilor: {exc}"

    user = _find_user(users, username)
    if user is None:
        return False, "Utilizatorul nu exista."

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    user["password_hash"] = new_hash
    user.pop("must_change_password", None)

    try:
        _save_users(users)
    except OSError as exc:
        return False, f"Eroare la salvarea parolei: {exc}"

    bootstrap_path = _resolve_bootstrap_info_path()
    if bootstrap_path.exists():
        try:
            bootstrap_path.unlink()
        except OSError:
            pass

    log_info("auth: parola schimbata pentru '%s'", username)
    return True, "Parola a fost schimbata cu succes."


def add_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
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
    except (OSError, ValueError) as exc:
        return False, f"Eroare: {exc}"

    if _find_user(users, username) is not None:
        return False, f"Utilizatorul '{username}' exista deja."
    if len(users) >= int(config.get("max_users", 3)):
        return False, f"Sistemul permite maximum {int(config.get('max_users', 3))} utilizatori."

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    users.append({"username": username, "password_hash": password_hash, "role": role})

    try:
        _save_users(users)
    except OSError as exc:
        return False, f"Eroare la salvare: {exc}"

    log_info("auth: utilizator nou adaugat '%s' (rol: %s)", username, role)
    return True, f"Utilizatorul '{username}' a fost adaugat."


def delete_user(username: str, requesting_username: str) -> tuple[bool, str]:
    if username.casefold() == requesting_username.casefold():
        return False, "Nu iti poti sterge propriul cont."

    try:
        users = _load_users()
    except (OSError, ValueError) as exc:
        return False, f"Eroare: {exc}"

    initial_count = len(users)
    users = [u for u in users if u.get("username", "").casefold() != username.casefold()]

    if len(users) == initial_count:
        return False, f"Utilizatorul '{username}' nu a fost gasit."
    if len(users) == 0:
        return False, "Nu se poate sterge ultimul utilizator."

    try:
        _save_users(users)
    except OSError as exc:
        return False, f"Eroare la salvare: {exc}"

    log_info("auth: utilizatorul '%s' sters de catre '%s'", username, requesting_username)
    return True, f"Utilizatorul '{username}' a fost sters."


def list_users() -> list[dict]:
    try:
        users = _load_users()
    except (OSError, ValueError):
        return []
    return [{"username": u.get("username", ""), "role": _normalize_role(u.get("role", "operator"))} for u in users]


def get_user_role(username: str) -> str:
    try:
        users = _load_users()
    except (OSError, ValueError):
        return "operator"
    user = _find_user(users, username)
    if not user:
        return "operator"
    return _normalize_role(user.get("role", "operator")) or "operator"


def is_admin(username: str) -> bool:
    return get_user_role(username) == "admin"


def must_change_password(username: str) -> bool:
    """Returneaza True daca utilizatorul trebuie sa schimbe parola."""
    try:
        users = _load_users()
    except (OSError, ValueError):
        return False
    user = _find_user(users, username)
    return bool(user and user.get("must_change_password", False))
