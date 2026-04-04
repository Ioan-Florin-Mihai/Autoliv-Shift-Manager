"""
Tests pentru logic/auth.py
Acopera: verify_login_detailed, brute-force lockout, change_password,
         add_user, delete_user, auto-migrare format vechi.
"""

import json
import time
import pytest

import bcrypt

import logic.auth as auth_module
from logic.auth import (
    _clear_failures,
    _failed_attempts,
    _load_users,
    _save_users,
    add_user,
    change_password,
    delete_user,
    verify_login,
    verify_login_detailed,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_brute_force():
    """Curata starea brute-force inainte de fiecare test."""
    _failed_attempts.clear()
    yield
    _failed_attempts.clear()


@pytest.fixture()
def users_file(tmp_path, monkeypatch):
    """
    Inlocuieste calea USERS_PATH cu un fisier temporar.
    Returneaza helper care scrie continutul dorit.
    """
    fake_path = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "USERS_PATH", fake_path)

    def _write(content):
        fake_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    return _write


@pytest.fixture()
def single_user(users_file):
    """Pregateste un fisier users.json cu un singur utilizator admin."""
    password = "TestParola123!"
    pw_hash  = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    users_file([{"username": "admin", "password_hash": pw_hash, "role": "admin"}])
    return {"username": "admin", "password": password}


# ── verify_login_detailed ─────────────────────────────────────────────────────

class TestVerifyLoginDetailed:
    def test_valid_credentials_return_true(self, single_user):
        ok, msg = verify_login_detailed(single_user["username"], single_user["password"])
        assert ok is True
        assert msg == ""

    def test_wrong_password_return_false(self, single_user):
        ok, msg = verify_login_detailed(single_user["username"], "gresit")
        assert ok is False
        assert msg

    def test_wrong_username_return_false(self, single_user):
        ok, msg = verify_login_detailed("nimeni", single_user["password"])
        assert ok is False
        assert msg

    def test_empty_username_rejected(self, single_user):
        ok, _ = verify_login_detailed("", single_user["password"])
        assert ok is False

    def test_empty_password_rejected(self, single_user):
        ok, _ = verify_login_detailed(single_user["username"], "")
        assert ok is False

    def test_username_too_long_rejected(self, single_user):
        ok, _ = verify_login_detailed("a" * 200, single_user["password"])
        assert ok is False

    def test_password_too_long_rejected(self, single_user):
        ok, _ = verify_login_detailed(single_user["username"], "b" * 300)
        assert ok is False

    def test_case_insensitive_username(self, single_user):
        ok, _ = verify_login_detailed("ADMIN", single_user["password"])
        assert ok is True

    def test_missing_users_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auth_module, "USERS_PATH", tmp_path / "missing.json")
        with pytest.raises(FileNotFoundError):
            verify_login_detailed("admin", "parola")


# ── verify_login (backward compat) ───────────────────────────────────────────

class TestVerifyLoginBool:
    def test_returns_true_on_valid(self, single_user):
        assert verify_login(single_user["username"], single_user["password"]) is True

    def test_returns_false_on_invalid(self, single_user):
        assert verify_login(single_user["username"], "gresit") is False


# ── Brute-force lockout ───────────────────────────────────────────────────────

class TestBruteForce:
    MAX = auth_module._MAX_ATTEMPTS

    def test_lockout_after_max_attempts(self, single_user):
        for _ in range(self.MAX):
            verify_login_detailed(single_user["username"], "gresit")
        ok, msg = verify_login_detailed(single_user["username"], single_user["password"])
        assert ok is False
        assert "secunde" in msg.lower()

    def test_lockout_cleared_on_success(self, single_user):
        """Dupa un login reusit, contorul e resetat si loginul urmator merge."""
        # Inregistram cateva esecuri (dar nu cat sa blocheze)
        for _ in range(self.MAX - 2):
            verify_login_detailed(single_user["username"], "gresit")
        # Login valid — curata esecurile
        ok, _ = verify_login_detailed(single_user["username"], single_user["password"])
        assert ok is True
        # Urmatoarea incercare cu parola gresita nu blocheaza imediat
        ok, _ = verify_login_detailed(single_user["username"], "gresit")
        assert ok is False  # gresit, dar nu blocat

    def test_different_usernames_independent_lockout(self, users_file):
        pw_hash = bcrypt.hashpw(b"parola123", bcrypt.gensalt(rounds=4)).decode()
        users_file([
            {"username": "alice", "password_hash": pw_hash, "role": "user"},
            {"username": "bob",   "password_hash": pw_hash, "role": "user"},
        ])
        # Blocam alice
        for _ in range(self.MAX):
            verify_login_detailed("alice", "gresit")
        # Bob nu e blocat
        ok, _ = verify_login_detailed("bob", "parola123")
        assert ok is True


# ── change_password ───────────────────────────────────────────────────────────

class TestChangePassword:
    def test_success(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], "NoiParola999!")
        assert ok is True
        assert msg

        # Noua parola functioneaza
        ok2, _ = verify_login_detailed(single_user["username"], "NoiParola999!")
        assert ok2 is True

    def test_wrong_old_password(self, single_user):
        ok, msg = change_password(single_user["username"], "gresit", "NoiParola999!")
        assert ok is False

    def test_new_password_too_short(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], "scurt1")
        assert ok is False
        assert "8" in msg

    def test_same_password_rejected(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], single_user["password"])
        assert ok is False
        assert "diferita" in msg.lower()


# ── add_user ──────────────────────────────────────────────────────────────────

class TestAddUser:
    def test_add_new_user(self, single_user):
        ok, _ = add_user("newuser", "Parola.Noua1", "user")
        assert ok is True
        users = _load_users()
        assert any(u["username"] == "newuser" for u in users)

    def test_duplicate_username_rejected(self, single_user):
        ok, msg = add_user("admin", "OriceParo1a!", "user")
        assert ok is False
        assert "exista" in msg.lower()

    def test_invalid_role_rejected(self, single_user):
        ok, msg = add_user("nou", "Parola123!", "superadmin")
        assert ok is False
        assert "rol" in msg.lower()

    def test_short_password_rejected(self, single_user):
        ok, msg = add_user("nou", "scurt", "user")
        assert ok is False
        assert "8" in msg


# ── delete_user ───────────────────────────────────────────────────────────────

class TestDeleteUser:
    def test_delete_other_user(self, users_file):
        pw_hash = bcrypt.hashpw(b"TestParola1", bcrypt.gensalt(rounds=4)).decode()
        users_file([
            {"username": "admin",  "password_hash": pw_hash, "role": "admin"},
            {"username": "target", "password_hash": pw_hash, "role": "user"},
        ])
        ok, _ = delete_user("target", "admin")
        assert ok is True
        users = _load_users()
        assert not any(u["username"] == "target" for u in users)

    def test_cannot_delete_self(self, single_user):
        ok, msg = delete_user("admin", "admin")
        assert ok is False
        assert "propriul" in msg.lower()

    def test_cannot_delete_last_user(self, single_user):
        ok, msg = delete_user("admin", "system")
        assert ok is False
        assert "ultim" in msg.lower()

    def test_delete_nonexistent_user(self, single_user):
        ok, msg = delete_user("nimeni", "admin")
        assert ok is False


# ── Auto-migrare format vechi ─────────────────────────────────────────────────

class TestLegacyMigration:
    def test_old_dict_format_migrated(self, users_file, tmp_path, monkeypatch):
        pw_hash = bcrypt.hashpw(b"veche123456", bcrypt.gensalt(rounds=4)).decode()
        users_file({"username": "legacy", "password_hash": pw_hash})

        raw = _load_users()
        assert isinstance(raw, list)
        assert raw[0]["username"] == "legacy"
        assert raw[0]["role"] == "admin"
