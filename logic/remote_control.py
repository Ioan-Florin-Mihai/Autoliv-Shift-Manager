import json
import threading
import time
import uuid
from queue import Queue

from logic.app_paths import APP_DIR, ensure_runtime_file


REMOTE_CONFIG_PATH = ensure_runtime_file("data/remote_config.json")
FIREBASE_SERVICE_PATH = ensure_runtime_file("data/firebase_service_account.json")


class RemoteControlService:
    def __init__(self):
        self.device_id = str(uuid.getnode())
        self._firebase_ready = False
        self._firebase_failed = False
        self._db = None
        self._app = None
        self._offline_started_at = None
        self._lock = threading.Lock()
        self.config = self._load_config()

    def _load_config(self):
        default_config = {
            "firebase_enabled": False,
            "database_url": "",
            "service_account_path": "data/firebase_service_account.json",
            "status_path": "settings/app_status",
            "allowed_devices_path": "settings/allowed_devices",
            "check_interval_seconds": 10,
            "max_offline_seconds": 120,
        }

        if not REMOTE_CONFIG_PATH.exists():
            return default_config

        try:
            with REMOTE_CONFIG_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return default_config

        default_config.update(data)
        return default_config

    def _init_firebase(self):
        if self._firebase_ready or self._firebase_failed:
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, db
        except ImportError:
            self._firebase_failed = True
            return

        service_account_path = APP_DIR / self.config["service_account_path"]
        if self.config["service_account_path"] == "data/firebase_service_account.json":
            service_account_path = FIREBASE_SERVICE_PATH
        database_url = self.config["database_url"]

        if not database_url or not service_account_path.exists():
            self._firebase_failed = True
            return

        try:
            with self._lock:
                if firebase_admin._apps:
                    self._app = firebase_admin.get_app()
                else:
                    cred = credentials.Certificate(str(service_account_path))
                    self._app = firebase_admin.initialize_app(cred, {"databaseURL": database_url})
                self._db = db
                self._firebase_ready = True
        except Exception:
            self._firebase_failed = True

    def _get_reference_value(self, path: str):
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase nu este configurat sau nu poate fi accesat.")

        return self._db.reference(path).get()

    def _set_reference_value(self, path: str, value):
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase nu este configurat sau nu poate fi accesat.")

        self._db.reference(path).set(value)

    def get_status(self):
        if not self.config.get("firebase_enabled", False):
            return "firebase_disabled"
        value = self._get_reference_value(self.config["status_path"])
        return str(value).lower() if value is not None else "unknown"

    def set_status(self, status: str):
        normalized = status.strip().lower()
        if normalized not in {"active", "blocked"}:
            raise ValueError("Statusul trebuie sa fie active sau blocked.")
        self._set_reference_value(self.config["status_path"], normalized)
        return normalized

    def check_access(self):
        if not self.config.get("firebase_enabled", False):
            return {"action": "allow", "message": f"Control remote dezactivat. Device ID: {self.device_id}"}

        try:
            status = self._get_reference_value(self.config["status_path"])
            allowed_devices = self._get_reference_value(self.config["allowed_devices_path"])
        except Exception:
            now = time.time()
            if self._offline_started_at is None:
                self._offline_started_at = now

            offline_seconds = now - self._offline_started_at
            max_offline = self.config.get("max_offline_seconds", 120)

            if offline_seconds >= max_offline:
                return {
                    "action": "block",
                    "message": f"Conexiunea la controlul remote lipseste de {int(offline_seconds)} secunde.",
                }

            return {
                "action": "warn",
                "message": f"Fara conexiune la Firebase de {int(offline_seconds)} secunde.",
            }

        self._offline_started_at = None

        if str(status).lower() == "blocked":
            return {"action": "block", "message": "Aplicatia a fost blocata remote."}

        if not self._is_device_allowed(allowed_devices):
            return {"action": "block", "message": f"Device neautorizat: {self.device_id}"}

        return {"action": "allow", "message": f"Aplicatia este activa. Device ID: {self.device_id}"}

    def _is_device_allowed(self, allowed_devices):
        if allowed_devices is None:
            return False

        if isinstance(allowed_devices, list):
            return self.device_id in {str(item) for item in allowed_devices}

        if isinstance(allowed_devices, dict):
            return bool(allowed_devices.get(self.device_id))

        return str(allowed_devices) == self.device_id


class RemoteChecker(threading.Thread):
    def __init__(self, service: RemoteControlService, events: Queue):
        super().__init__(daemon=True)
        self.service = service
        self.events = events
        self._running = True

    def run(self):
        while self._running:
            result = self.service.check_access()
            self.events.put(result)

            if result["action"] == "block":
                break

            interval = max(3, int(self.service.config.get("check_interval_seconds", 10)))
            time.sleep(interval)

    def stop(self):
        self._running = False
