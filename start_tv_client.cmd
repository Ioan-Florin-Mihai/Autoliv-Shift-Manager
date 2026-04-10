@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$c = Get-Content 'config.json' -Raw | ConvertFrom-Json; Write-Output ('http://{0}:{1}/tv' -f $c.server_ip, $c.server_port)"`) do set "TV_URL=%%I"
if "%TV_URL%"=="" set "TV_URL=http://127.0.0.1:8000/tv"
where msedge >nul 2>&1
if %errorlevel%==0 (
    start "" msedge --kiosk "%TV_URL%" --edge-kiosk-type=fullscreen --no-first-run --disable-features=msImplicitSignin
    exit /b 0
)
where chrome >nul 2>&1
if %errorlevel%==0 (
    start "" chrome --kiosk "%TV_URL%" --no-first-run
    exit /b 0
)
start "" "%TV_URL%"
