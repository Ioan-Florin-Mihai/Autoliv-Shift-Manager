@echo off
cd /d "%~dp0"
if exist "%~dp0dist\data\schedule_live.json" (
	set "APP_ROOT=%~dp0dist"
) else (
	set "APP_ROOT=%~dp0"
)
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
start "" "%PYTHON_EXE%" "%~dp0main.py" --tv-web
