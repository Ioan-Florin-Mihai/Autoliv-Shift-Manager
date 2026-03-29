# ============================================================
# MODUL: auth.py
# Gestioneaza autentificarea utilizatorului.
# Credentialele (username + hash parola) sunt stocate in
# data/users.json. Parola este hashata cu bcrypt.
# ============================================================

import json

import bcrypt

from logic.app_paths import ensure_runtime_file


# Calea fisierului cu credentiale — copiat din bundle la primul rulaj
USERS_PATH = ensure_runtime_file("data/users.json")


def load_user_credentials():
    """
    Citeste username-ul si hash-ul parolei din users.json.
    Arunca exceptie daca fisierul lipseste sau e invalid.
    """
    if not USERS_PATH.exists():
        raise FileNotFoundError(f"Lipseste fisierul de utilizatori: {USERS_PATH}")

    with USERS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    username      = data.get("username", "").strip()
    password_hash = data.get("password_hash", "").encode("utf-8")

    # Verificam ca ambele campuri sunt completate
    if not username or not password_hash:
        raise ValueError("Fisierul users.json nu contine credentiale valide.")

    return username, password_hash


def verify_login(username: str, password: str):
    """
    Verifica daca username si parola introduse sunt corecte.
    Returneaza True daca autentificarea a reusit, False altfel.
    Bcrypt compara parola introdusa cu hash-ul stocat.
    """
    saved_username, saved_password_hash = load_user_credentials()

    # Comparatie username case-sensitive (cu strip)
    if username.strip() != saved_username:
        return False

    # Bcrypt verifica parola fara a o des-hasha
    return bcrypt.checkpw(password.encode("utf-8"), saved_password_hash)
