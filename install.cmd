@echo off
setlocal
cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=planner"

echo [1/6] Pregatesc mediul Python...
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv >nul 2>&1
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 (
        echo [EROARE] Nu am putut crea mediul virtual.
        exit /b 1
    )
)
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

echo [2/6] Instalez dependintele...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [3/6] Initializez fisierele si directoarele runtime...
if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "backups" mkdir "backups"
if not exist "Exports" mkdir "Exports"
"%PYTHON_EXE%" -c "from logic.app_config import ensure_config; from logic.auth import _load_users; ensure_config(); _load_users()"
if errorlevel 1 exit /b 1

echo [4/6] Configurez IP-ul serverului pentru TV (AUTO)...
set "SERVER_IP=AUTO"
"%PYTHON_EXE%" -c "import json; from pathlib import Path; p=Path('config.json'); cfg=json.loads(p.read_text(encoding='utf-8')); cfg['server_ip']='AUTO'; p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')"
if errorlevel 1 (
    echo [EROARE] Nu am putut actualiza config.json cu IP-ul serverului.
    exit /b 1
)

echo [5/6] Configurez auto-start pentru modul %MODE%...
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP_DIR%" mkdir "%STARTUP_DIR%"
del /f /q "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd" >nul 2>&1
if /i "%MODE%"=="planner" copy /y "start_planner.cmd" "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd" >nul
if /i "%MODE%"=="server" copy /y "start_tv_server.cmd" "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd" >nul
if /i "%MODE%"=="tv" copy /y "start_tv_client.cmd" "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd" >nul
if /i "%MODE%"=="kiosk" copy /y "start_kiosk.cmd" "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd" >nul

echo [6/6] Instalare finalizata.
echo.
echo Server TV configurat pe IP: AUTO (detectie automata la runtime)
echo Mod auto-start activ: %MODE%
echo Script startup: "%STARTUP_DIR%\Autoliv Shift Manager Startup.cmd"
echo.
echo Exemple:
echo   install.cmd planner
echo   install.cmd server
echo   install.cmd tv
echo   install.cmd kiosk
endlocal
