# ============================================================
# MODUL: remote_control.py
# Implementeaza sistemul de control remote via Firebase.
# Permite blocarea aplicatiei de la distanta (anti-furt).
#
# Flux:
#   1. RemoteControlService verifica Firebase la fiecare N secunde
#   2. Daca statusul e "blocked" → aplicatia se inchide
#   3. Daca nu exista conexiune > max_offline_seconds → se inchide
#   4. Daca device-ul nu e in allowed_devices → se blocheaza
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


# Caile fisierelor de configurare Firebase
# remote_config.json e non-sensibil, poate fi in bundle
REMOTE_CONFIG_PATH    = ensure_runtime_file("data/remote_config.json")
# firebase_service_account.json contine cheia privata GCP — NU e in bundle
FIREBASE_SERVICE_PATH = get_sensitive_path("data/firebase_service_account.json")


class RemoteControlService:
    """
    Serviciu de control remote prin Firebase Realtime Database.
    Instanta unica creata la pornirea aplicatiei.
    """

    def __init__(self):
        # ID-ul unic al acestui dispozitiv - generat o data si salvat persistent
        self.device_id = self._get_or_create_device_id()

        # Stare interna Firebase
        self._firebase_ready  = False   # True dupa initializare reusita
        self._firebase_failed = False   # True daca initializarea a esuat
        self._db  = None
        self._app = None

        # Timestamp de cand s-a pierdut conexiunea (pentru timeout offline)
        self._offline_started_at = None
        self._lock = threading.Lock()

        # Incarcam configuratia din remote_config.json
        self.config = self._load_config()

    def _get_or_create_device_id(self):
        """
        Genereaza o ID unica la prima rulare si o salveaza in data/device_id.json.
        La rulari viitoare, incarca ID-ul salvat (nu se mai schimba).
        Asta evita probleme cu MAC address rotativ sau adaptatoare virtuale.
        """
        device_id_path = ensure_runtime_file("data/device_id.json")
        
        # Daca fisierul exista, citim ID-ul din el
        if device_id_path.exists():
            try:
                with device_id_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    device_id = data.get("device_id")
                    if device_id:
                        return device_id
            except (json.JSONDecodeError, OSError):
                pass
        
        # Generam o ID noua (UUID)
        device_id = str(uuid.uuid4())
        
        # O salvam pt. viitoare rulari
        try:
            with device_id_path.open("w", encoding="utf-8") as f:
                json.dump({"device_id": device_id}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        
        return device_id

    def _load_config(self):
        """
        Incarca configuratia Firebase din remote_config.json.
        Daca fisierul lipseste sau e invalid, foloseste valorile default
        cu firebase_enabled=False (fara protectie remote).
        """
        default_config = {
            "firebase_enabled":        False,
            "database_url":            "",
            "service_account_path":    "data/firebase_service_account.json",
            "status_path":             "settings/app_status",
            "allowed_devices_path":    "settings/allowed_devices",
            "check_interval_seconds":  10,
            "max_offline_seconds":     120,
        }

        if not REMOTE_CONFIG_PATH.exists():
            return default_config

        try:
            with REMOTE_CONFIG_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return default_config

        # Suprascriem valorile default cu cele din fisier
        default_config.update(data)
        return default_config

    def _init_firebase(self):
        """
        Initializeaza conexiunea Firebase Admin SDK.
        Apelata lazy (la primul check_access) pentru a nu bloca pornirea.
        Seteaza _firebase_ready=True la succes sau _firebase_failed=True la esec.
        """
        # Evitam re-initializarea
        if self._firebase_ready or self._firebase_failed:
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, db
        except ImportError:
            # firebase-admin nu e instalat
            self._firebase_failed = True
            return

        # Determinam calea catre service account JSON
        service_account_path = APP_DIR / self.config["service_account_path"]
        if self.config["service_account_path"] == "data/firebase_service_account.json":
            service_account_path = FIREBASE_SERVICE_PATH

        database_url = self.config["database_url"]

        # Nu continuam fara URL sau fara fisierul de credentiale
        if not database_url or not service_account_path.exists():
            self._firebase_failed = True
            return

        try:
            with self._lock:
                # Evitam initializarea dubla daca app-ul Firebase exista deja
                if firebase_admin._apps:
                    self._app = firebase_admin.get_app()
                else:
                    cred      = credentials.Certificate(str(service_account_path))
                    self._app = firebase_admin.initialize_app(cred, {"databaseURL": database_url})
                self._db            = db
                self._firebase_ready = True
                log_info("firebase: initializare reusita (device_id=%s)", self.device_id)
        except Exception as exc:
            log_exception("firebase_init", exc)
            self._firebase_failed = True

    def _get_reference_value(self, path: str):
        """Citeste o valoare dintr-un path al Realtime Database."""
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase nu este configurat sau nu poate fi accesat.")
        return self._db.reference(path).get()

    def _set_reference_value(self, path: str, value):
        """Scrie o valoare intr-un path al Realtime Database."""
        self._init_firebase()
        if not self._firebase_ready or self._db is None:
            raise ConnectionError("Firebase nu este configurat sau nu poate fi accesat.")
        self._db.reference(path).set(value)

    def get_status(self):
        """
        Returneaza statusul curent din Firebase ("active" / "blocked").
        Daca Firebase e dezactivat, returneaza "firebase_disabled".
        """
        if not self.config.get("firebase_enabled", False):
            return "firebase_disabled"
        value = self._get_reference_value(self.config["status_path"])
        return str(value).lower() if value is not None else "unknown"

    def set_status(self, status: str):
        """
        Seteaza statusul in Firebase ("active" sau "blocked").
        Arunca ValueError pentru valori invalide.
        """
        normalized = status.strip().lower()
        if normalized not in {"active", "blocked"}:
            raise ValueError("Statusul trebuie sa fie active sau blocked.")
        self._set_reference_value(self.config["status_path"], normalized)
        return normalized

    def check_access(self):
        """
        Verifica daca aplicatia are dreptul sa ruleze.
        Returneaza un dict cu cheile:
          - "action": "allow" | "warn" | "block"
          - "message": descriere text
        """
        # Firebase dezactivat → accesul e permis mereu
        if not self.config.get("firebase_enabled", False):
            return {"action": "allow", "message": f"Control remote dezactivat. Device ID: {self.device_id}"}

        try:
            status          = self._get_reference_value(self.config["status_path"])
            allowed_devices = self._get_reference_value(self.config["allowed_devices_path"])
        except Exception:
            # Nu putem contacta Firebase — masuram cat timp suntem offline
            now = time.time()
            if self._offline_started_at is None:
                self._offline_started_at = now

            offline_seconds = now - self._offline_started_at
            max_offline     = self.config.get("max_offline_seconds", 120)

            if offline_seconds >= max_offline:
                # Depasit timeout-ul offline → blocam aplicatia
                return {
                    "action":  "block",
                    "message": f"Conexiunea la controlul remote lipseste de {int(offline_seconds)} secunde.",
                }

            # Inca in fereastra de gratie offline → avertizam
            return {
                "action":  "warn",
                "message": f"Fara conexiune la Firebase de {int(offline_seconds)} secunde.",
            }

        # Conexiune reusita — resetam contorul offline
        self._offline_started_at = None

        # Verificam daca statusul e "blocked"
        if str(status).lower() == "blocked":
            return {"action": "block", "message": "Aplicatia a fost blocata remote."}

        # Verificam daca device-ul curent e autorizat
        if not self._is_device_allowed(allowed_devices):
            return {"action": "block", "message": f"Device neautorizat: {self.device_id}"}

        return {"action": "allow", "message": f"Aplicatia este activa. Device ID: {self.device_id}"}

    def _is_device_allowed(self, allowed_devices):
        """
        Verifica daca device-ul curent (dupa MAC address) e in lista alba.
        Accepta mai multe formate de stocare in Firebase:
          - lista: ["123456", "789012"]
          - dict:  {"123456": true, "789012": false}
          - string: "123456"
        """
        if allowed_devices is None:
            return False

        if isinstance(allowed_devices, list):
            return self.device_id in {str(item) for item in allowed_devices}

        if isinstance(allowed_devices, dict):
            return bool(allowed_devices.get(self.device_id))

        return str(allowed_devices) == self.device_id


class RemoteChecker(threading.Thread):
    """
    Thread daemon care verifica periodic accesul remote.
    Ruleaza in fundal si pune rezultatele intr-o coada (Queue).
    PlannerDashboard consuma coada via process_remote_events().
    """

    def __init__(self, service: RemoteControlService, events: Queue):
        super().__init__(daemon=True)  # daemon=True: se opreste cand se inchide app-ul
        self.service   = service
        self.events    = events
        self._running  = True

    def run(self):
        """Bucla principala: verifica accesul si pune rezultatul in coada."""
        while self._running:
            result = self.service.check_access()
            self.events.put(result)

            # La blocare, oprim thread-ul (nu mai are rost sa continue)
            if result["action"] == "block":
                break

            # Asteptam intervalul configurat (minim 3 secunde)
            interval = max(3, int(self.service.config.get("check_interval_seconds", 10)))
            time.sleep(interval)

    def stop(self):
        """Semnaleaza thread-ului sa se opreasca la urmatoarea iteratie."""
        self._running = False
