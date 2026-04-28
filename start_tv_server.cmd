@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PORT=8000"
if exist "%~dp0dist\data\schedule_live.json" (
	set "APP_ROOT=%~dp0dist"
) else (
	set "APP_ROOT=%~dp0"
)

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$port = %PORT%; try { $socket = [Net.Sockets.Socket]::new([Net.Sockets.AddressFamily]::InterNetwork, [Net.Sockets.SocketType]::Dgram, [Net.Sockets.ProtocolType]::Udp); $socket.Connect('8.8.8.8', 80); $ip = $socket.LocalEndPoint.Address.ToString(); $socket.Close() } catch { $ip = '127.0.0.1' }; Write-Output ('http://{0}:{1}/tv' -f $ip, $port)"`) do set "TV_NETWORK_URL=%%I"
if "%TV_NETWORK_URL%"=="" set "TV_NETWORK_URL=http://127.0.0.1:%PORT%/tv"

echo ========================================================
echo  AUTOLIV TV SERVER
echo ========================================================
echo  Date folosite: %APP_ROOT%
echo.
echo  DESCHIDE PE ACEST PC:
echo    http://127.0.0.1:%PORT%/tv
echo.
echo  DESCHIDE PE TELEVIZOARE:
echo    %TV_NETWORK_URL%
echo.
echo  Foloseste linkul de televizoare pe fiecare TV din retea.
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conn = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if ($conn) { Write-Host '[INFO] Serverul TV este deja pornit pe portul %PORT%.'; exit 10 }"

if "%ERRORLEVEL%"=="10" (
	echo.
	echo Serverul ruleaza deja. Foloseste:
	echo.
	echo   Pe acest PC:  http://127.0.0.1:%PORT%/tv
	echo   Pe TV-uri:   %TV_NETWORK_URL%
	echo.
	pause
	exit /b 0
)

echo Pornesc serverul TV...
echo.
"%PYTHON_EXE%" "%~dp0main.py" --tv-web

echo.
echo [INFO] Serverul TV s-a oprit.
pause
