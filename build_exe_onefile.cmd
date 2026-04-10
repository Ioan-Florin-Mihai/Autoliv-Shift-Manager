@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "VERSION_TMP=%TEMP%\autoliv_build_version_%RANDOM%.txt"

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

if exist "dist\Autoliv Shift Manager.exe" (
	del /f /q "dist\Autoliv Shift Manager.exe"
)

if exist "dist\Autoliv Shift Manager v%APP_VERSION%.exe" (
	del /f /q "dist\Autoliv Shift Manager v%APP_VERSION%.exe"
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

echo.
echo ============================================
echo  Build finalizat!
echo  Executabilul portabil se afla in:
echo  dist\Autoliv Shift Manager.exe
echo.
echo  Pentru update sigur pe statie foloseste:
echo  update_portable_exe.cmd "dist\Autoliv Shift Manager.exe" "C:\Folder\Autoliv Shift Manager.exe"
echo ============================================
