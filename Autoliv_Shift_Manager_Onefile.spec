# -*- mode: python ; coding: utf-8 -*-
# Spec pentru un singur .exe portabil (onefile)

import sys
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo,
    FixedFileInfo,
    StringFileInfo,
    StringTable,
    StringStruct,
    VarFileInfo,
    VarStruct,
)

from logic.version import APP_NAME, VERSION

try:
    hiddenimports = collect_submodules("tkcalendar")
except Exception:
    hiddenimports = []

hiddenimports += collect_submodules("logic")
hiddenimports += collect_submodules("ui")

hiddenimports += [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "tkinter.font",
    "tkinter.constants",
    "logic.app_logger",
    "logic.app_config",
    "logic.app_paths",
    "logic.auth",
    "logic.employee_store",
    "logic.personnel_manager",
    "logic.runtime_bootstrap",
    "logic.schedule_store",
    "logic.ui_state_store",
    "logic.validation",
    "logic.version",
    "ui.common_ui",
    "ui.dashboard",
    "ui.employee_form",
    "ui.planner_dashboard",
]

version_parts = [int(part) for part in VERSION.split(".")]
while len(version_parts) < 3:
    version_parts.append(0)
file_version = tuple(version_parts + [0])

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=file_version,
        prodvers=file_version,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Autoliv"),
                        StringStruct("FileDescription", APP_NAME),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "Autoliv Shift Manager"),
                        StringStruct("OriginalFilename", "Autoliv Shift Manager.exe"),
                        StringStruct("ProductName", APP_NAME),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    ("config.json",                    "."),
    ("assets/autoliv_logo.png",       "assets"),
    ("assets/autoliv_app.ico",         "assets"),
    ("assets/autoliv_app_icon.png",    "assets"),
    ("templates/tv.html",              "templates"),
    # NOTA SECURITATE: users.json este fisier sensibil.
    # fisiere SENSIBILE — NU se includ niciodata in bundle (.exe).
    # Se depun manual langa executabil de catre administrator.
    ("data/schedule_draft.json",       "data"),
    ("data/schedule_live.json",        "data"),
    ("data/audit_log.json",            "data"),
    ("data/employees.json",            "data"),
]

binaries = []

# IMPORTANT (venv): when running PyInstaller from a venv, sys.executable points to
# ".venv\\Scripts\\python.exe", but Tcl/Tk + stdlib live under sys.base_prefix.
# If we derive paths from sys.executable, PyInstaller's tkinter hook can mark the
# installation as "broken" and exclude tkinter from the bundle.
python_base = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
if not python_base.exists():
    python_base = Path(sys.executable).resolve().parent
tcl_dll_dir = python_base / "DLLs"
tcl_binaries = ["_tkinter.pyd", "tcl86t.dll", "tk86t.dll"]
tcl_root = python_base / "tcl"
tkinter_root = python_base / "Lib" / "tkinter"

# Help PyInstaller's hook-tkinter locate Tcl/Tk when building from a venv.
try:
    tcl_lib = tcl_root / "tcl8.6"
    tk_lib = tcl_root / "tk8.6"
    if tcl_lib.exists() and not os.environ.get("TCL_LIBRARY"):
        os.environ["TCL_LIBRARY"] = str(tcl_lib)
    if tk_lib.exists() and not os.environ.get("TK_LIBRARY"):
        os.environ["TK_LIBRARY"] = str(tk_lib)
except Exception:
    pass

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
            # PyInstaller's runtime hook `pyi_rth__tkinter` expects these exact
            # directories in onefile extraction:
            # - sys._MEIPASS\\_tcl_data
            # - sys._MEIPASS\\_tk_data
            # If they are missing, the app fails before the GUI is shown.
            target_dir = "_tcl_data" if relative_dir == "tcl8.6" else "_tk_data"
            if str(relative_parent) != ".":
                target_dir = f"{target_dir}/{relative_parent}"
            datas.append((str(path), target_dir))


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["pyinstaller_hooks"],
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
    version=version_info,
    onefile=True,
)
