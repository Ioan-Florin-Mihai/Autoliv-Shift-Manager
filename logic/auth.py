import json

import bcrypt

from logic.app_paths import ensure_runtime_file


USERS_PATH = ensure_runtime_file("data/users.json")


def load_user_credentials():
    if not USERS_PATH.exists():
        raise FileNotFoundError(f"Lipseste fisierul de utilizatori: {USERS_PATH}")

    with USERS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    username = data.get("username", "").strip()
    password_hash = data.get("password_hash", "").encode("utf-8")

    if not username or not password_hash:
        raise ValueError("Fisierul users.json nu contine credentiale valide.")

    return username, password_hash


def verify_login(username: str, password: str):
    saved_username, saved_password_hash = load_user_credentials()

    if username.strip() != saved_username:
        return False

    return bcrypt.checkpw(password.encode("utf-8"), saved_password_hash)
