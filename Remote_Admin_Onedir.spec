# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

try:
    hiddenimports = collect_submodules("tkcalendar")
except Exception:
    hiddenimports = []

datas = [
    ("assets/autoliv_logo.png", "assets"),
    ("assets/autoliv_app.ico", "assets"),
    ("assets/autoliv_app_icon.png", "assets"),
    ("data/remote_config.json", "data"),
    ("data/firebase_service_account.json", "data"),
]


a = Analysis(
    ["remote_admin.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyinstaller_runtime_hook.py"],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Autoliv Remote Control",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon="assets/autoliv_app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Autoliv Remote Control",
)
