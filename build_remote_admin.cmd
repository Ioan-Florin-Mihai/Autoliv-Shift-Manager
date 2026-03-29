@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm "Remote_Admin_Onedir.spec"
echo.
echo Build remote admin finalizat.
echo Folder executabil: dist\Autoliv Remote Control\
pause
