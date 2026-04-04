# -*- mode: python ; coding: utf-8 -*-
# Spec pentru un singur .exe portabil (onefile)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

try:
    hiddenimports = collect_submodules("tkcalendar")
except Exception:
    hiddenimports = []

hiddenimports += [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "tkinter.font",
    "tkinter.constants",
]

datas = [
    ("assets/autoliv_logo.png",       "assets"),
    ("assets/autoliv_app.ico",         "assets"),
    ("assets/autoliv_app_icon.png",    "assets"),
    # NOTA SECURITATE: users.json si firebase_service_account.json sunt
    # fisiere SENSIBILE — NU se includ niciodata in bundle (.exe).
    # Se depun manual langa executabil de catre administrator.
    ("data/remote_config.json",        "data"),
    ("data/schedule_data.json",        "data"),
    ("data/employees.json",            "data"),
]

binaries = []

python_base = Path(sys.executable).resolve().parent
tcl_dll_dir = python_base / "DLLs"
tcl_binaries = ["_tkinter.pyd", "tcl86t.dll", "tk86t.dll"]
tcl_root = python_base / "tcl"
tkinter_root = python_base / "Lib" / "tkinter"

if tkinter_root.exists():
    for path in tkinter_root.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc":
            continue
        relative_parent = path.parent.relative_to(tkinter_root)
        target_dir = "tkinter"
        if str(relative_parent) != ".":
            target_dir = f"{target_dir}/{relative_parent}"
        datas.append((str(path), target_dir))

for binary_name in tcl_binaries:
    binary_path = tcl_dll_dir / binary_name
    if binary_path.exists():
        binaries.append((str(binary_path), "."))

for relative_dir in ("tcl8.6", "tk8.6"):
    source_dir = tcl_root / relative_dir
    if source_dir.exists():
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            relative_parent = path.parent.relative_to(source_dir)
            target_dir = f"tcl/{relative_dir}"
            if str(relative_parent) != ".":
                target_dir = f"{target_dir}/{relative_parent}"
            datas.append((str(path), target_dir))


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyinstaller_runtime_hook.py"],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

# ONEFILE: toate fisierele sunt comprimate intr-un singur .exe
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Autoliv Shift Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon="assets/autoliv_app.ico",
    onefile=True,
)
