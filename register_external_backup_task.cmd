@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~1"=="" goto :usage

set "TARGET_FOLDER=%~1"
set "BACKUP_TIME=22:00"
if not "%~2"=="" set "BACKUP_TIME=%~2"

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\register_external_backup_task.ps1" -TargetFolder "%TARGET_FOLDER%" -Time "%BACKUP_TIME%"
exit /b %ERRORLEVEL%

:usage
echo.
echo Utilizare:
echo   register_external_backup_task.cmd "D:\Autoliv_Backups" "22:00"
echo.
echo Verificare fara modificari:
echo   powershell -NoProfile -ExecutionPolicy Bypass -File tools\register_external_backup_task.ps1 -TargetFolder "D:\Autoliv_Backups" -Time "22:00" -WhatIf
exit /b 1
