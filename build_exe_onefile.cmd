@echo off
cd /d "%~dp0"
echo Construiesc executabilul portabil...
python -m PyInstaller --noconfirm "Autoliv_Shift_Manager_Onefile.spec"
echo.
echo ============================================
echo  Build finalizat!
echo  Executabilul portabil se afla in:
echo  dist\Autoliv Shift Manager.exe
echo ============================================
pause
