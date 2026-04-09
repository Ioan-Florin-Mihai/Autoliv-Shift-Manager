@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "SKIP_INSTALL=0"
set "NO_UPDATE=0"
set "VERSION_ONLY=0"
set "TARGET_EXE="
set "RELEASE_KEEP_COUNT=5"
set "LOCK_FILE=%~dp0.release_lock"
set "RUN_TIMESTAMP="
set "APP_VERSION="
set "BUILD_TIME="
set "RELEASE_DIR="
set "ERROR_MESSAGE="
set "STATUS_TEXT=FAIL"
set "EXIT_CODE=1"
set "LOCK_CREATED=0"
set "TARGET_LOG=build-only"
set "RUN_TS_TMP=%TEMP%\autoliv_release_runts_%RANDOM%.txt"
set "VERSION_TMP=%TEMP%\autoliv_release_version_%RANDOM%.txt"
set "BUILD_TIME_TMP=%TEMP%\autoliv_release_buildtime_%RANDOM%.txt"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--help" goto :usage
if /I "%~1"=="-h" goto :usage
if /I "%~1"=="--skip-install" (
	set "SKIP_INSTALL=1"
	shift
	goto :parse_args
)
if /I "%~1"=="--no-update" (
	set "NO_UPDATE=1"
	shift
	goto :parse_args
)
if /I "%~1"=="--version-only" (
	set "VERSION_ONLY=1"
	shift
	goto :parse_args
)
if not "%TARGET_EXE%"=="" (
	echo.
	echo [EROARE] A fost specificata mai mult de o cale target.
	exit /b 1
)
set "TARGET_EXE=%~f1"
shift
goto :parse_args

:args_done

set "RELEASE_ROOT=%~dp0release"
set "RELEASE_LOG=%RELEASE_ROOT%\release_log.txt"
set "DIST_EXE=dist\Autoliv Shift Manager.exe"
set "RELEASE_EXE_NAME=Autoliv_Shift_Manager.exe"

del /f /q "%RUN_TS_TMP%" >nul 2>&1
"%PYTHON_EXE%" -c "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))" > "%RUN_TS_TMP%"
if exist "%RUN_TS_TMP%" set /p RUN_TIMESTAMP=<"%RUN_TS_TMP%"
del /f /q "%RUN_TS_TMP%" >nul 2>&1
if "%RUN_TIMESTAMP%"=="" set "RUN_TIMESTAMP=%DATE% %TIME%"

if not "%TARGET_EXE%"=="" set "TARGET_LOG=%TARGET_EXE%"
if "%VERSION_ONLY%"=="1" set "TARGET_LOG=version-only"

if exist "%LOCK_FILE%" (
	echo.
	echo [EROARE] Exista deja un lock activ: %LOCK_FILE%
	echo [EROARE] Daca niciun release nu ruleaza, sterge fisierul si reincearca.
	set "ERROR_MESSAGE=Lock activ sau ramas dintr-o rulare anterioara"
	goto :cleanup_exit
)

> "%LOCK_FILE%" echo %RUN_TIMESTAMP%
if errorlevel 1 (
	echo.
	echo [EROARE] Nu pot crea lock file-ul de release.
	set "ERROR_MESSAGE=Crearea lock file-ului a esuat"
	goto :cleanup_exit
)
set "LOCK_CREATED=1"

echo.
echo ============================================
echo  AUTOLIV SHIFT MANAGER - LOCAL RELEASE
echo ============================================
echo  Python: %PYTHON_EXE%
if "%SKIP_INSTALL%"=="1" (
	echo  Dependente: skip install
) else (
	echo  Dependente: install / update
)
if "%VERSION_ONLY%"=="1" (
	echo  Mod: version-only
) else if "%NO_UPDATE%"=="1" (
	echo  Update target: dezactivat (--no-update)
) else if not "%TARGET_EXE%"=="" (
	echo  Target update: %TARGET_EXE%
) else (
	echo  Target update: build only
)
echo ============================================

echo.
echo [STEP] Bumping version...
del /f /q "%VERSION_TMP%" >nul 2>&1
"%PYTHON_EXE%" bump_version.py --patch > "%VERSION_TMP%"
if exist "%VERSION_TMP%" set /p APP_VERSION=<"%VERSION_TMP%"
del /f /q "%VERSION_TMP%" >nul 2>&1
if errorlevel 1 (
	echo.
	set "ERROR_MESSAGE=Incrementarea versiunii a esuat"
	goto :cleanup_exit
)
if "%APP_VERSION%"=="" (
	echo.
	set "ERROR_MESSAGE=Noua versiune nu a putut fi determinata"
	goto :cleanup_exit
)

echo [OK] Versiune noua: %APP_VERSION%

if "%VERSION_ONLY%"=="1" (
	echo.
	echo [OK] Version bump finalizat. Nicio alta actiune nu a fost executata.
	set "STATUS_TEXT=SUCCESS"
	set "EXIT_CODE=0"
	goto :cleanup_exit
)

if "%SKIP_INSTALL%"=="0" (
	echo.
	echo [STEP] Installing dependencies...
	"%PYTHON_EXE%" -m pip install -r requirements.txt -r requirements-dev.txt
	if errorlevel 1 (
		echo.
		set "ERROR_MESSAGE=Instalarea dependentelor a esuat"
		goto :cleanup_exit
	)
)

echo.
echo [STEP] Building EXE...
call build_exe_onefile.cmd
if errorlevel 1 (
	echo.
	set "ERROR_MESSAGE=Build-ul executabilului a esuat"
	goto :cleanup_exit
)

if not exist "%DIST_EXE%" (
	echo.
	set "ERROR_MESSAGE=Executabilul generat lipseste: %DIST_EXE%"
	goto :cleanup_exit
)

echo.
echo [STEP] Creating release folder...
set "RELEASE_DIR=%RELEASE_ROOT%\%APP_VERSION%"
if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%"
if not exist "%RELEASE_ROOT%" (
	set "ERROR_MESSAGE=Folderul release root nu a putut fi creat"
	goto :cleanup_exit
)
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
if not exist "%RELEASE_DIR%" (
	set "ERROR_MESSAGE=Folderul release pentru versiune nu a putut fi creat"
	goto :cleanup_exit
)

copy /Y "%DIST_EXE%" "%RELEASE_DIR%\%RELEASE_EXE_NAME%" >nul
if errorlevel 1 (
	echo.
	set "ERROR_MESSAGE=Copierea executabilului in release folder a esuat"
	goto :cleanup_exit
	)
if not exist "%RELEASE_DIR%\%RELEASE_EXE_NAME%" (
	set "ERROR_MESSAGE=Executabilul nu exista in release folder dupa copiere"
	goto :cleanup_exit
)

del /f /q "%BUILD_TIME_TMP%" >nul 2>&1
"%PYTHON_EXE%" -c "from datetime import datetime; print(datetime.now().isoformat(timespec='seconds'))" > "%BUILD_TIME_TMP%"
if exist "%BUILD_TIME_TMP%" set /p BUILD_TIME=<"%BUILD_TIME_TMP%"
del /f /q "%BUILD_TIME_TMP%" >nul 2>&1
if "%BUILD_TIME%"=="" set "BUILD_TIME=%DATE% %TIME%"

> "%RELEASE_DIR%\version.txt" echo %APP_VERSION%
> "%RELEASE_DIR%\build_time.txt" echo %BUILD_TIME%
(
	echo Release %APP_VERSION%
	echo Build time: %BUILD_TIME%
	echo.
	echo - Release local generat automat.
	echo - Completeaza aici observatii sau instructiuni interne.
) > "%RELEASE_DIR%\notes.txt"
if not exist "%RELEASE_DIR%\version.txt" (
	set "ERROR_MESSAGE=version.txt nu a fost generat"
	goto :cleanup_exit
)
if not exist "%RELEASE_DIR%\build_time.txt" (
	set "ERROR_MESSAGE=build_time.txt nu a fost generat"
	goto :cleanup_exit
)
if not exist "%RELEASE_DIR%\notes.txt" (
	set "ERROR_MESSAGE=notes.txt nu a fost generat"
	goto :cleanup_exit
)

(
	echo {
	echo   "version": "%APP_VERSION%",
	echo   "path": "release/%APP_VERSION%/%RELEASE_EXE_NAME%"
	echo }
) > "%RELEASE_ROOT%\latest_version.json"
if not exist "%RELEASE_ROOT%\latest_version.json" (
	set "ERROR_MESSAGE=latest_version.json nu a fost generat"
	goto :cleanup_exit
)

echo.
echo [STEP] Cleaning old releases...
"%PYTHON_EXE%" -c "from pathlib import Path; import re, shutil, sys; root=Path(sys.argv[1]); keep=int(sys.argv[2]); dirs=[p for p in root.iterdir() if p.is_dir() and re.match(r'^\d+\.\d+\.\d+$', p.name)]; dirs=sorted(dirs, key=lambda p: tuple(int(x) for x in p.name.split('.'))); [shutil.rmtree(p) for p in dirs[:-keep]] if len(dirs) > keep else None" "%RELEASE_ROOT%" "%RELEASE_KEEP_COUNT%"
if errorlevel 1 (
	set "ERROR_MESSAGE=Curatarea release-urilor vechi a esuat"
	goto :cleanup_exit
)

if "%NO_UPDATE%"=="1" (
	echo.
	echo [STEP] Updating target...
	echo [OK] Sarit peste update din cauza flag-ului --no-update.
) else if not "%TARGET_EXE%"=="" (
	echo.
	echo [STEP] Updating target...
	call update_portable_exe.cmd "%RELEASE_DIR%\%RELEASE_EXE_NAME%" "%TARGET_EXE%"
	if errorlevel 1 (
		echo.
		set "ERROR_MESSAGE=Update-ul executabilului existent a esuat"
		goto :cleanup_exit
	)
) else (
	echo.
	echo [STEP] Updating target...
	echo [OK] Fara target de update - release local finalizat fara deploy.
)

set "STATUS_TEXT=SUCCESS"
set "EXIT_CODE=0"

goto :cleanup_exit

:cleanup_exit
if "%APP_VERSION%"=="" set "APP_VERSION=UNKNOWN"
if not exist "%RELEASE_ROOT%" mkdir "%RELEASE_ROOT%" >nul 2>&1
>> "%RELEASE_LOG%" echo [%RUN_TIMESTAMP%] VERSION %APP_VERSION% - %STATUS_TEXT% - Target: %TARGET_LOG%
if not "%ERROR_MESSAGE%"=="" >> "%RELEASE_LOG%" echo     Reason: %ERROR_MESSAGE%

if "%LOCK_CREATED%"=="1" (
	if exist "%LOCK_FILE%" del /f /q "%LOCK_FILE%" >nul 2>&1
)

del /f /q "%RUN_TS_TMP%" >nul 2>&1
del /f /q "%VERSION_TMP%" >nul 2>&1
del /f /q "%BUILD_TIME_TMP%" >nul 2>&1

if "%EXIT_CODE%"=="0" (
	echo.
	echo ============================================
	echo  Release local finalizat cu succes.
	echo  Versiune: %APP_VERSION%
	echo  Executabil nou: %DIST_EXE%
	if not "%RELEASE_DIR%"=="" echo  Folder release: %RELEASE_DIR%
	echo  Manifest update: %RELEASE_ROOT%\latest_version.json
	echo ============================================
) else (
	echo.
	echo ============================================
	echo  Release local esuat.
	if not "%ERROR_MESSAGE%"=="" echo  Motiv: %ERROR_MESSAGE%
	echo ============================================
)

exit /b %EXIT_CODE%

:usage
echo.
echo Utilizare:
echo   release_local.cmd
echo   release_local.cmd "C:\Folder\Autoliv Shift Manager.exe"
echo   release_local.cmd --skip-install
echo   release_local.cmd --skip-install "C:\Folder\Autoliv Shift Manager.exe"
echo   release_local.cmd --no-update
echo   release_local.cmd --version-only
echo.
echo Exemple:
echo   release_local.cmd "C:\Autoliv\Autoliv Shift Manager.exe"
echo   release_local.cmd --skip-install "D:\USB\Autoliv Shift Manager.exe"
echo   release_local.cmd --no-update
echo   release_local.cmd --version-only
exit /b 0