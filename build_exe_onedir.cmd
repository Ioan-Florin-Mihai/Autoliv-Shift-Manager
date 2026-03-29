@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm "Autoliv_Shift_Manager_Onedir.spec"
echo.
echo Build onedir finalizat.
echo Folder executabil: dist\Autoliv Shift Manager\
pause
