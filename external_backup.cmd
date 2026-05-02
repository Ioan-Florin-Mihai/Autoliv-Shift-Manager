@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

if "%~1"=="" goto :usage

"%PYTHON_EXE%" tools\external_backup.py "%~1" --source-root "%~dp0"
exit /b %ERRORLEVEL%

:usage
echo.
echo Utilizare:
echo   external_backup.cmd "D:\Autoliv_Backups"
echo.
echo Pentru test fara copiere:
echo   .venv\Scripts\python.exe tools\external_backup.py "external_backups" --dry-run
exit /b 1
