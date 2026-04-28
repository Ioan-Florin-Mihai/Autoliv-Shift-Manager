@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "VERSION_TMP=%TEMP%\autoliv_build_version_%RANDOM%.txt"
set "DIST_RUNTIME_BACKUP=%TEMP%\autoliv_dist_runtime_%RANDOM%"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"

del /f /q "%VERSION_TMP%" >nul 2>&1
"%PYTHON_EXE%" -c "from logic.version import VERSION; print(VERSION)" > "%VERSION_TMP%"
if exist "%VERSION_TMP%" set /p APP_VERSION=<"%VERSION_TMP%"
del /f /q "%VERSION_TMP%" >nul 2>&1

if "%APP_VERSION%"=="" (
	echo.
	echo [EROARE] Nu pot citi versiunea aplicatiei din logic\version.py
	exit /b 1
)

echo Construiesc executabilul portabil...
echo Versiune: %APP_VERSION%

if exist "%DIST_RUNTIME_BACKUP%" (
	rmdir /s /q "%DIST_RUNTIME_BACKUP%" >nul 2>&1
)
mkdir "%DIST_RUNTIME_BACKUP%" >nul 2>&1

if exist "dist\data" (
	echo Pastrez datele runtime existente din dist\data...
	xcopy /E /I /Y "dist\data" "%DIST_RUNTIME_BACKUP%\data" >nul
)
if exist "dist\backups" (
	echo Pastrez backup-urile existente din dist\backups...
	xcopy /E /I /Y "dist\backups" "%DIST_RUNTIME_BACKUP%\backups" >nul
)
if exist "dist\Exports" (
	echo Pastrez exporturile existente din dist\Exports...
	xcopy /E /I /Y "dist\Exports" "%DIST_RUNTIME_BACKUP%\Exports" >nul
)

if exist "dist" (
	rmdir /s /q "dist"
)

if exist "build\Autoliv_Shift_Manager_Onefile" (
	rmdir /s /q "build\Autoliv_Shift_Manager_Onefile"
)

"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm "Autoliv_Shift_Manager_Onefile.spec"

if errorlevel 1 (
	echo.
	echo ============================================
	echo  Build esuat.
	echo  Verifica daca PyInstaller este instalat in .venv si daca executabilul este deschis sau blocat.
	echo ============================================
	exit /b 1
)

mkdir "dist\assets" >nul 2>&1
mkdir "dist\data" >nul 2>&1
mkdir "dist\backups" >nul 2>&1
mkdir "dist\Exports" >nul 2>&1
mkdir "dist\logs" >nul 2>&1

if exist "%DIST_RUNTIME_BACKUP%\data" (
	xcopy /E /I /Y "%DIST_RUNTIME_BACKUP%\data" "dist\data" >nul
)
if exist "%DIST_RUNTIME_BACKUP%\backups" (
	xcopy /E /I /Y "%DIST_RUNTIME_BACKUP%\backups" "dist\backups" >nul
)
if exist "%DIST_RUNTIME_BACKUP%\Exports" (
	xcopy /E /I /Y "%DIST_RUNTIME_BACKUP%\Exports" "dist\Exports" >nul
)

copy /y "config.json" "dist\config.json" >nul
copy /y "assets\autoliv_logo.png" "dist\assets\autoliv_logo.png" >nul
copy /y "assets\autoliv_app.ico" "dist\assets\autoliv_app.ico" >nul
copy /y "assets\autoliv_app_icon.png" "dist\assets\autoliv_app_icon.png" >nul
if not exist "dist\data\schedule_draft.json" copy /y "release_defaults\data\schedule_draft.json" "dist\data\schedule_draft.json" >nul
if not exist "dist\data\schedule_live.json" copy /y "release_defaults\data\schedule_live.json" "dist\data\schedule_live.json" >nul
if not exist "dist\data\audit_log.json" copy /y "release_defaults\data\audit_log.json" "dist\data\audit_log.json" >nul
if not exist "dist\data\employees.json" copy /y "release_defaults\data\employees.json" "dist\data\employees.json" >nul
if not exist "dist\data\ui_state.json" copy /y "release_defaults\data\ui_state.json" "dist\data\ui_state.json" >nul

if exist "%DIST_RUNTIME_BACKUP%" (
	rmdir /s /q "%DIST_RUNTIME_BACKUP%" >nul 2>&1
)

if exist "dist\data\users.json" del /f /q "dist\data\users.json" >nul 2>&1
if exist "dist\data\bootstrap_admin.json" del /f /q "dist\data\bootstrap_admin.json" >nul 2>&1
if exist "dist\data\runtime_root.txt" del /f /q "dist\data\runtime_root.txt" >nul 2>&1
if exist "dist\data\planner.lock" del /f /q "dist\data\planner.lock" >nul 2>&1
if exist "dist\data\tv_server.lock" del /f /q "dist\data\tv_server.lock" >nul 2>&1
if exist "dist\data\audit_log.lock" del /f /q "dist\data\audit_log.lock" >nul 2>&1
if exist "dist\logs\system.log" del /f /q "dist\logs\system.log" >nul 2>&1

echo.
echo ============================================
echo  Build finalizat!
echo  Executabilul portabil se afla in:
echo  dist\Autoliv Shift Manager.exe
echo.
echo  Pentru update sigur pe statie foloseste:
echo  update_portable_exe.cmd "dist\Autoliv Shift Manager.exe" "C:\Folder\Autoliv Shift Manager.exe"
echo ============================================
