#!/usr/bin/env python3
# ============================================================
# SCRIPT: setup_device_firebase.py
# Autorizeaza dispozitivul curent in Firebase automat.
# Genereaza device_id.json si o adauga in allowed_devices.
# ============================================================

import json
import uuid
from pathlib import Path

def ensure_runtime_file(filename):
    """Intoarce calea completa pentru fisiere din data/"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / filename

def get_or_create_device_id():
    """Genereaza device_id.json daca nu exista"""
    device_id_path = ensure_runtime_file("device_id.json")
    
    if device_id_path.exists():
        try:
            with device_id_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                device_id = data.get("device_id")
                if device_id:
                    return device_id, device_id_path
        except (json.JSONDecodeError, OSError):
            pass
    
    # Generam ID noua (UUID)
    device_id = str(uuid.uuid4())
    
    # O salvam
    try:
        with device_id_path.open("w", encoding="utf-8") as f:
            json.dump({"device_id": device_id}, f, ensure_ascii=False, indent=2)
        print(f"✅ Generat device_id.json: {device_id}")
    except OSError as e:
        print(f"❌ Eroare la salvare device_id.json: {e}")
        return None, device_id_path
    
    return device_id, device_id_path

def authorize_device_in_firebase(device_id):
    """Conecteaza la Firebase si adauga device-ul in allowed_devices"""
    try:
        import firebase_admin
        from firebase_admin import credentials, db
    except ImportError:
        print("❌ firebase-admin nu e instalat!")
        print("   Instaleaza cu: pip install firebase-admin")
        return False
    
    firebase_service_path = ensure_runtime_file("firebase_service_account.json")
    
    if not firebase_service_path.exists():
        print(f"❌ Lipseste: {firebase_service_path}")
        return False
    
    try:
        # Initializez Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(firebase_service_path))
            app = firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://autoliv-remote-default-rtdb.europe-west1.firebasedatabase.app'
            })
        else:
            app = firebase_admin._apps[0]
        
        # Citesc allowed_devices curente
        ref = db.reference("settings/allowed_devices")
        current_devices = ref.get()
        
        print(f"\n📋 Dispozitive autorizate actuale: {current_devices}")
        
        # Pentru compatibilitate, iau ca dict
        if current_devices is None:
            current_devices = {}
        elif isinstance(current_devices, list):
            current_devices = {d: True for d in current_devices}
        
        # Adaug device-ul nou
        current_devices[device_id] = True
        
        # Salvez
        ref.set(current_devices)
        print(f"✅ Dispozitiv autorizat in Firebase!")
        print(f"\n🎉 Device ID: {device_id}")
        print(f"   a fost adaugat in allowed_devices")
        
        return True
        
    except Exception as e:
        print(f"❌ Eroare la conectare Firebase: {e}")
        return False

def main():
    print("=" * 60)
    print("SETUP: Autorizare dispozitiv in Firebase")
    print("=" * 60)
    
    # 1. Genereaza device_id
    device_id, path = get_or_create_device_id()
    if not device_id:
        print("❌ Nu s-a putut genera device_id!")
        return False
    
    print(f"📝 Device ID: {device_id}")
    print(f"   Fisier: {path}")
    
    # 2. Conecteaza si autorizeaza
    print("\n🔗 Se conecteaza la Firebase...")
    success = authorize_device_in_firebase(device_id)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ GATA! Dispozitivul este autorizat!")
        print("=" * 60)
        return True
    else:
        print("\n⚠️  Nu s-a putut conecta la Firebase")
        print("   Adauga manual device ID-ul in Firebase:")
        print(f"   {device_id}")
        return False

if __name__ == "__main__":
    main()
