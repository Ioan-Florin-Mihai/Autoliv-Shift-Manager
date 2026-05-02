@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" tools\support_bundle.py --source-root "%~dp0" --output-root "support_bundles"
exit /b %ERRORLEVEL%
