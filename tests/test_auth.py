"""
Tests pentru logic/auth.py
Acopera: verify_login_detailed, brute-force lockout, change_password,
         add_user, delete_user, auto-migrare format vechi.
"""

import json

import bcrypt
import pytest

import logic.auth as auth_module
from logic.auth import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    _failed_attempts,
    _load_users,
    add_user,
    change_password,
    delete_user,
    get_lockout_remaining_seconds,
    verify_login,
    verify_login_detailed,
)
from logic.internal_credentials import DEFAULT_ADMIN_USERNAME


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
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    users_file([{"username": "admin", "password_hash": pw_hash, "role": "admin"}])
    return {"username": "admin", "password": password}


def test_internal_default_credentials_are_centralized():
    assert ADMIN_USERNAME == DEFAULT_ADMIN_USERNAME
    assert ADMIN_PASSWORD == "Autoliv2026!"


def _bootstrap_password() -> str:
    return ADMIN_PASSWORD


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

    def test_missing_users_file_creates_default(self, tmp_path, monkeypatch):
        fake_path = tmp_path / "missing.json"
        bootstrap_path = tmp_path / "bootstrap_admin.json"
        monkeypatch.setattr(auth_module, "USERS_PATH", fake_path)
        monkeypatch.setattr(auth_module, "BOOTSTRAP_INFO_PATH", bootstrap_path)
        users = _load_users()
        assert users and users[0]["username"] == "admin"
        assert fake_path.exists(), "users.json ar fi trebuit creat automat"
        assert not bootstrap_path.exists(), "bootstrap_admin.json nu trebuie generat pentru release local"
        data = json.loads(fake_path.read_text(encoding="utf-8"))
        assert isinstance(data, list) and data, "users.json trebuie sa contina lista de utilizatori"
        admin = next((u for u in data if u.get("username") == "admin"), None)
        assert admin is not None
        assert admin.get("must_change_password", False) is False
        ok, msg = verify_login_detailed("admin", ADMIN_PASSWORD)
        assert ok is True
        assert msg == ""

    def test_missing_users_file_default_password_works(self, tmp_path, monkeypatch):
        fake_path = tmp_path / "missing.json"
        bootstrap_path = tmp_path / "bootstrap_admin.json"
        monkeypatch.setattr(auth_module, "USERS_PATH", fake_path)
        monkeypatch.setattr(auth_module, "BOOTSTRAP_INFO_PATH", bootstrap_path)
        ok, msg = verify_login_detailed("admin", ADMIN_PASSWORD)
        assert ok is True
        assert msg == ""
        assert not bootstrap_path.exists()

    def test_existing_bootstrap_state_migrates_to_default_password(self, tmp_path, monkeypatch):
        fake_path = tmp_path / "users.json"
        bootstrap_path = tmp_path / "bootstrap_admin.json"
        monkeypatch.setattr(auth_module, "USERS_PATH", fake_path)
        monkeypatch.setattr(auth_module, "BOOTSTRAP_INFO_PATH", bootstrap_path)
        old_password = "RandomBootstrap123"
        old_hash = bcrypt.hashpw(old_password.encode(), bcrypt.gensalt(rounds=4)).decode()
        users_file = [{"username": "admin", "password_hash": old_hash, "role": "admin", "must_change_password": True}]
        fake_path.write_text(json.dumps(users_file), encoding="utf-8")
        bootstrap_path.write_text(json.dumps({"username": "admin", "password": old_password}), encoding="utf-8")
        ok, msg = verify_login_detailed("admin", ADMIN_PASSWORD)
        assert ok is True
        assert msg == ""
        assert not bootstrap_path.exists()

    def test_legacy_admin_hash_is_migrated_to_current_password(self, users_file):
        users_file([
            {
                "username": "admin",
                "password_hash": next(iter(auth_module._LEGACY_ADMIN_HASHES)),
                "role": "admin",
                "must_change_password": True,
            }
        ])
        users = _load_users()
        admin = users[0]
        assert admin.get("must_change_password", False) is False
        assert bcrypt.checkpw(ADMIN_PASSWORD.encode("utf-8"), admin["password_hash"].encode("utf-8")) is True

    def test_legacy_admin_password_no_longer_works_after_migration(self, users_file):
        users_file([
            {
                "username": "admin",
                "password_hash": next(iter(auth_module._LEGACY_ADMIN_HASHES)),
                "role": "admin",
                "must_change_password": True,
            }
        ])
        _load_users()
        ok_new, msg_new = verify_login_detailed("admin", ADMIN_PASSWORD)
        ok_old, _ = verify_login_detailed("admin", "admin-legacy-invalid")
        assert ok_new is True
        assert msg_new == ""
        assert ok_old is False


class TestVerifyLoginBool:
    def test_returns_true_on_valid(self, single_user):
        assert verify_login(single_user["username"], single_user["password"]) is True

    def test_returns_false_on_invalid(self, single_user):
        assert verify_login(single_user["username"], "gresit") is False


class TestBruteForce:
    MAX = auth_module._MAX_ATTEMPTS

    def test_lockout_after_max_attempts(self, single_user):
        for _ in range(self.MAX):
            verify_login_detailed(single_user["username"], "gresit")
        ok, msg = verify_login_detailed(single_user["username"], single_user["password"])
        assert ok is False
        assert "secunde" in msg.lower()
        assert get_lockout_remaining_seconds(single_user["username"]) > 0

    def test_lockout_remaining_is_zero_without_lockout(self, single_user):
        assert get_lockout_remaining_seconds(single_user["username"]) == 0

    def test_lockout_cleared_on_success(self, single_user):
        for _ in range(self.MAX - 2):
            verify_login_detailed(single_user["username"], "gresit")
        ok, _ = verify_login_detailed(single_user["username"], single_user["password"])
        assert ok is True
        ok, _ = verify_login_detailed(single_user["username"], "gresit")
        assert ok is False

    def test_different_usernames_independent_lockout(self, users_file):
        pw_hash = bcrypt.hashpw(b"parola123", bcrypt.gensalt(rounds=4)).decode()
        users_file([
            {"username": "alice", "password_hash": pw_hash, "role": "user"},
            {"username": "bob", "password_hash": pw_hash, "role": "user"},
        ])
        for _ in range(self.MAX):
            verify_login_detailed("alice", "gresit")
        ok, _ = verify_login_detailed("bob", "parola123")
        assert ok is True


class TestChangePassword:
    def test_success(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], "NoiParola999!")
        assert ok is True
        assert msg

        ok2, _ = verify_login_detailed(single_user["username"], "NoiParola999!")
        assert ok2 is True

    def test_wrong_old_password(self, single_user):
        ok, _ = change_password(single_user["username"], "gresit", "NoiParola999!")
        assert ok is False

    def test_new_password_too_short(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], "scurt1")
        assert ok is False
        assert "8" in msg

    def test_same_password_rejected(self, single_user):
        ok, msg = change_password(single_user["username"], single_user["password"], single_user["password"])
        assert ok is False
        assert "diferita" in msg.lower()


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


class TestDeleteUser:
    def test_delete_other_user(self, users_file):
        pw_hash = bcrypt.hashpw(b"TestParola1", bcrypt.gensalt(rounds=4)).decode()
        users_file([
            {"username": "admin", "password_hash": pw_hash, "role": "admin"},
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
        ok, _ = delete_user("nimeni", "admin")
        assert ok is False


class TestLegacyMigration:
    def test_old_dict_format_migrated(self, users_file):
        pw_hash = bcrypt.hashpw(b"veche123456", bcrypt.gensalt(rounds=4)).decode()
        users_file({"username": "legacy", "password_hash": pw_hash})

        raw = _load_users()
        assert isinstance(raw, list)
        assert raw[0]["username"] == "legacy"
        assert raw[0]["role"] == "admin"
