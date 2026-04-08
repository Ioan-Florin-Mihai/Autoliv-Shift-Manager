@echo off
cd /d "%~dp0"
echo Construiesc executabilul portabil...

if exist "dist\Autoliv Shift Manager.exe" (
	del /f /q "dist\Autoliv Shift Manager.exe"
)

if exist "build\Autoliv_Shift_Manager_Onefile" (
	rmdir /s /q "build\Autoliv_Shift_Manager_Onefile"
)

python -m PyInstaller --clean --noconfirm "Autoliv_Shift_Manager_Onefile.spec"

if errorlevel 1 (
	echo.
	echo ============================================
	echo  Build esuat.
	echo  Verifica daca executabilul este deschis sau blocat.
	echo ============================================
	pause
	exit /b 1
)

echo.
echo ============================================
echo  Build finalizat!
echo  Executabilul portabil se afla in:
echo  dist\Autoliv Shift Manager.exe
echo ============================================
pause
