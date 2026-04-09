@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "SOURCE_EXE=%~f1"
set "TARGET_EXE=%~f2"

if not exist "%SOURCE_EXE%" (
	echo.
	echo [EROARE] Executabilul sursa nu exista:
	echo %SOURCE_EXE%
	exit /b 1
)

for %%I in ("%TARGET_EXE%") do (
	set "TARGET_DIR=%%~dpI"
	set "TARGET_NAME=%%~nI"
)
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
if not exist "%TARGET_DIR%" (
	echo.
	echo [EROARE] Folderul tinta nu a putut fi creat:
	echo %TARGET_DIR%
	exit /b 1
)

set "SANITIZED_NAME=%TARGET_NAME: =_%"
set "BACKUP_EXE=%TARGET_DIR%%SANITIZED_NAME%_backup.exe"
set "STAGED_EXE=%TARGET_EXE%.new"

echo.
echo [STEP] Oprire proces existent daca este pornit...
taskkill /IM "Autoliv Shift Manager.exe" /F >nul 2>&1

if exist "%STAGED_EXE%" del /f /q "%STAGED_EXE%" >nul 2>&1

if exist "%TARGET_EXE%" (
	echo [STEP] Creez backup...
	copy /Y "%TARGET_EXE%" "%BACKUP_EXE%" >nul
	if errorlevel 1 (
		echo.
		echo [EROARE] Nu pot crea backup pentru executabilul existent.
		exit /b 1
	)
	if not exist "%BACKUP_EXE%" (
		echo.
		echo [EROARE] Backup-ul nu a fost creat corect.
		exit /b 1
	)
)

echo [STEP] Copiez noua versiune in staging...
copy /Y "%SOURCE_EXE%" "%STAGED_EXE%" >nul
if errorlevel 1 (
	echo.
	echo [EROARE] Copierea noului executabil in staging a esuat.
	exit /b 1
)

echo [STEP] Inlocuiesc executabilul tinta...
move /Y "%STAGED_EXE%" "%TARGET_EXE%" >nul
if errorlevel 1 goto :restore
if not exist "%TARGET_EXE%" goto :restore

echo.
echo [OK] Update finalizat cu succes:
echo %TARGET_EXE%
exit /b 0

:restore
echo.
echo [EROARE] Update-ul a esuat. Incerc restaurarea backup-ului...
if exist "%STAGED_EXE%" del /f /q "%STAGED_EXE%" >nul 2>&1
if exist "%BACKUP_EXE%" (
	copy /Y "%BACKUP_EXE%" "%TARGET_EXE%" >nul
	if errorlevel 1 (
		echo [EROARE] Restaurarea backup-ului a esuat.
		exit /b 1
	)
	echo [OK] Backup restaurat:
	echo %TARGET_EXE%
	exit /b 1
)

echo [EROARE] Nu exista backup pentru restaurare.
exit /b 1

:usage
echo.
echo Utilizare:
echo   update_portable_exe.cmd "dist\Autoliv Shift Manager.exe" "C:\Folder\Autoliv Shift Manager.exe"
exit /b 1