@echo off
REM VSE Local Transcript Runner - Deinstalator Windows Service
REM Uruchom jako Administrator!

set SERVICE_NAME=VSELocalRunner

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Wymaga uprawnien Administrator!
    pause
    exit /b 1
)

where nssm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%~dp0nssm.exe" (
        set NSSM=%~dp0nssm.exe
    ) else (
        echo [ERROR] NSSM nie znaleziony. Odinstaluj recznie przez services.msc
        pause
        exit /b 1
    )
) else (
    set NSSM=nssm
)

echo [*] Zatrzymywanie i usuwanie service %SERVICE_NAME%...
%NSSM% stop %SERVICE_NAME% confirm
%NSSM% remove %SERVICE_NAME% confirm

echo.
echo [VSE Local Runner] Odinstalowany.
pause
