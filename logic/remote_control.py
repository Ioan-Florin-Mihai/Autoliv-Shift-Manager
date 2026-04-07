# ============================================================
# MODUL: remote_control.py
# Control remote OPȚIONAL via Firebase Realtime Database.
#
# PRINCIPIU FUNDAMENTAL: aplicația NICIODATĂ nu se oprește
# din cauza Firebase. Remote control este un feature non-critic.
#
# Dacă Firebase e indisponibil → app rulează în LOCAL MODE.
# Singura situație de blocare: status "blocked" setat ACTIV
# în Firebase de administrator (anti-furt confirmat).
#
# Configurare: data/remote_config.json
# Credentiale: data/firebase_service_account.json
# ============================================================

import json
import threading
import time
import uuid
from queue import Queue

from logic.app_logger import log_exception, log_warning, log_info
from logic.app_paths import APP_DIR, ensure_runtime_file, get_sensitive_path


# Căile fișierelor de configurare Firebase
REMOTE_CONFIG_PATH    = ensure_runtime_file("data/remote_config.json")
FIREBASE_SERVICE_PATH = get_sensitive_path("data/firebase_service_account.json")


class RemoteControlService:
    """
    Serviciu de control remote prin Firebase Realtime Database.
    FAIL-SAFE: dacă Firebase nu e disponibil, aplicația continuă normal.
    """

    def __init__(self):
        self.device_id = self._get_or_create_device_id()

        # Stare internă Firebase
        self._firebase_ready  = False
        self._firebase_failed = False
        self._db  = None
        self._app = None

        self._offline_started_at = None
        self._lock = threading.Lock()

        self.config = self._load_config()

    def _get_or_create_device_id(self):
        """Generează un device ID unic persistent."""
        device_id_path = ensure_runtime_file("data/device_id.json")

        if device_id_path.exists():
            try:
                with device_id_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    device_id = data.get("device_id")
                    if device_id:
                        return device_id
            except (json.JSONDecodeError, OSError):
                pass

        device_id = str(uuid.uuid4())
        try:
            with device_id_path.open("w", encoding="utf-8") as f:
                json.dump({"device_id": device_id}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return device_id

    def _load_config(self):
        """
        Încarcă configurația Firebase. Dacă lipsește/corrupt → default SAFE
        cu firebase_enabled=False (fără protecție remote).
        """
        default_config = {
            "firebase_enabled":              False,
            "database_url":                  "",
            "service_account_path":          "data/firebase_service_account.json",
            "status_path":                   "settings/app_status",
            "allowed_devices_path":          "settings/allowed_devices",
            "check_interval_seconds":        10,
            "block_on_unauthorized_device":  False,
            "fail_safe_mode":                True,
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
        """Inițializează Firebase Admin SDK (lazy, la primul check)."""
        if self._firebase_ready or self._firebase_failed:
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, db
        except ImportError:
            self._firebase_failed = True
            log_warning("firebase: firebase-admin nu e instalat — mod local activ.")
            return

        service_account_path = APP_DIR / self.config["service_account_path"]
        if self.config["service_account_path"] == "data/firebase_service_account.json":
            service_account_path = FIREBASE_SERVICE_PATH

        database_url = self.config["database_url"]

        if not database_url or not service_account_path.exists():
            self._firebase_failed = True
            log_warning("firebase: lipsește database_url sau service_account — mod local activ.")
            return

        try:
            with self._lock:
                import firebase_admin as _fa
                if _fa._apps:
                    self._app = _fa.get_app()
                else:
                    cred      = credentials.Certificate(str(service_account_path))
                    self._app = _fa.initialize_app(cred, {"databaseURL": database_url})
                self._db             = db
                self._firebase_ready = True
                log_info("firebase: inițializare reușită (device_id=%s)", self.device_id)
        except Exception as exc:
            log_exception("firebase_init", exc)
            self._firebase_failed = True
            log_warning("firebase: inițializare eșuată — mod local activ.")

    def _get_reference_value(self, path: str):
        """Citește o valoare din Realtime Database."""
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase indisponibil.")
        return self._db.reference(path).get()

    def _set_reference_value(self, path: str, value):
        """Scrie o valoare în Realtime Database."""
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase indisponibil.")
        self._db.reference(path).set(value)

    def get_status(self):
        """Returnează statusul curent („active"/„blocked"/„firebase_disabled")."""
        if not self.config.get("firebase_enabled", False):
            return "firebase_disabled"
        value = self._get_reference_value(self.config["status_path"])
        return str(value).lower() if value is not None else "unknown"

    def set_status(self, status: str):
        """Setează statusul în Firebase."""
        normalized = status.strip().lower()
        if normalized not in {"active", "blocked"}:
            raise ValueError("Statusul trebuie să fie active sau blocked.")
        self._set_reference_value(self.config["status_path"], normalized)
        return normalized

    def check_access(self):
        """
        Verifică dreptul de acces al aplicației.
        Returnează dict cu:
          - "action": "allow" | "warn" | "block"
          - "message": descriere text

        REGULĂ FAIL-SAFE:
          - Orice eroare de conexiune → "allow" (cu warning log)
          - Singura blocare reală: status=="blocked" CONFIRMAT din Firebase
          - Timeout offline NU mai oprește aplicația
        """
        # Firebase dezactivat → acces permis mereu
        if not self.config.get("firebase_enabled", False):
            return {
                "action": "allow",
                "message": f"Control remote dezactivat. Device ID: {self.device_id}",
            }

        try:
            status          = self._get_reference_value(self.config["status_path"])
            allowed_devices = self._get_reference_value(self.config["allowed_devices_path"])
        except Exception as exc:
            # ── FAIL-SAFE: Firebase indisponibil → app continuă normal ──
            now = time.time()
            if self._offline_started_at is None:
                self._offline_started_at = now
                log_warning("firebase: conexiune pierdută — se continuă în mod local.")

            offline_seconds = now - self._offline_started_at

            # Doar log + warn, NICIODATĂ block
            return {
                "action":  "warn",
                "message": f"Mod offline ({int(offline_seconds)}s). Control remote indisponibil.",
            }

        # Conexiune reușită — resetăm contorul offline
        if self._offline_started_at is not None:
            log_info("firebase: conexiune restabilită după offline.")
        self._offline_started_at = None

        # Status „blocked" setat ACTIV de administrator — singura blocare reală
        if str(status).lower() == "blocked":
            return {"action": "block", "message": "Aplicația a fost blocată remote de administrator."}

        # Verificare device autorizat — doar dacă e activată explicit
        if self.config.get("block_on_unauthorized_device", False):
            if not self._is_device_allowed(allowed_devices):
                return {"action": "block", "message": f"Device neautorizat: {self.device_id}"}

        return {"action": "allow", "message": f"Aplicația este activă. Device ID: {self.device_id}"}

    def _is_device_allowed(self, allowed_devices):
        """Verifică dacă device-ul curent e în lista albă Firebase."""
        if allowed_devices is None:
            return False
        if isinstance(allowed_devices, list):
            return self.device_id in {str(item) for item in allowed_devices}
        if isinstance(allowed_devices, dict):
            return bool(allowed_devices.get(self.device_id))
        return str(allowed_devices) == self.device_id


# ── Backoff constants ─────────────────────────────────────────
_BACKOFF_SCHEDULE = [5, 10, 30, 60]  # secunde — ciclic


class RemoteChecker(threading.Thread):
    """
    Thread daemon care verifică periodic accesul remote.
    NICIODATĂ nu oprește thread-ul din cauza erorilor.
    Folosește exponential backoff la erori de conexiune.
    """

    def __init__(self, service: RemoteControlService, events: Queue):
        super().__init__(daemon=True)
        self.service   = service
        self.events    = events
        self._running  = True
        self._backoff_idx = 0

    def run(self):
        """Buclă infinită: verifică accesul și pune rezultatul în coadă."""
        while self._running:
            try:
                result = self.service.check_access()
                self.events.put(result)

                if result["action"] == "warn":
                    # Backoff progresiv la probleme de conexiune
                    delay = _BACKOFF_SCHEDULE[min(self._backoff_idx, len(_BACKOFF_SCHEDULE) - 1)]
                    self._backoff_idx += 1
                    time.sleep(delay)
                    continue

                # Conexiune OK sau block — resetăm backoff
                self._backoff_idx = 0

                # La block CONFIRMAT (admin a blocat activ), thread-ul se oprește
                if result["action"] == "block":
                    break

            except Exception as exc:
                # NICIODATĂ crash — orice eroare e logată și ignorată
                log_exception("remote_checker_run", exc)
                delay = _BACKOFF_SCHEDULE[min(self._backoff_idx, len(_BACKOFF_SCHEDULE) - 1)]
                self._backoff_idx += 1
                time.sleep(delay)
                continue

            interval = max(3, int(self.service.config.get("check_interval_seconds", 10)))
            time.sleep(interval)

    def stop(self):
        """Semnalează thread-ului să se oprească."""
        self._running = False
