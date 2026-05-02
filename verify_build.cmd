@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "DIST_DIR=dist"
if not "%~1"=="" set "DIST_DIR=%~1"

"%PYTHON_EXE%" tools\post_build_verify.py --dist "%DIST_DIR%"
exit /b %ERRORLEVEL%
