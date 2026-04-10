@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  tv_mode.cmd  —  Porneste Autoliv Shift Manager in modul TV (fullscreen)
REM
REM  Copiaza acest fisier pe orice TV/PC din fabrica.
REM  Dublu-clic sau adauga la Startup pentru pornire automata.
REM ─────────────────────────────────────────────────────────────────────────────

REM Directorul executabilului (acelasi folder cu acest .cmd)
set "APP_DIR=%~dp0"

REM Incearca executabilul PyInstaller intai
if exist "%APP_DIR%Autoliv_Shift_Manager.exe" (
    start "" "%APP_DIR%Autoliv_Shift_Manager.exe" --tv
    goto :eof
)

REM Fallback: ruleaza direct cu Python (mod development)
if exist "%APP_DIR%main.py" (
    start "" pythonw "%APP_DIR%main.py" --tv
    goto :eof
)

echo EROARE: Nu s-a gasit nici Autoliv_Shift_Manager.exe, nici main.py.
pause
