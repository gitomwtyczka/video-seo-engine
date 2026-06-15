@echo off
REM ==========================================================================
REM VSE Local Transcript Runner - Instalator Windows Service
REM Wymaga: NSSM (Non-Sucking Service Manager) na PATH lub w tym katalogu
REM Uruchom jako Administrator!
REM ==========================================================================

setlocal EnableDelayedExpansion

set SERVICE_NAME=VSELocalRunner
set SCRIPT_DIR=%~dp0
set RUNNER_SCRIPT=%SCRIPT_DIR%runner.py
set LOG_DIR=C:\ProgramData\VSELocalRunner

echo.
echo [VSE Local Runner] Instalator Windows Service
echo ================================================
echo.

REM Sprawdz czy uruchomiony jako Administrator
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ten skrypt wymaga uruchomienia jako Administrator!
    echo Kliknij prawym przyciskiem na install.bat i wybierz "Uruchom jako administrator"
    pause
    exit /b 1
)

REM Sprawdz czy Python jest dostepny
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python nie jest zainstalowany lub nie jest na PATH!
    pause
    exit /b 1
)

REM Sprawdz czy plik .env istnieje
if not exist "%SCRIPT_DIR%.env" (
    echo [ERROR] Brak pliku .env w katalogu: %SCRIPT_DIR%
    echo Skopiuj .env.example do .env i uzupelnij LOCAL_RUNNER_TOKEN
    pause
    exit /b 1
)

REM Sprawdz czy NSSM jest dostepny
where nssm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%SCRIPT_DIR%nssm.exe" (
        set NSSM=%SCRIPT_DIR%nssm.exe
    ) else (
        echo [ERROR] NSSM nie znaleziony!
        echo Pobierz ze: https://nssm.cc/download
        echo Skopiuj nssm.exe do tego katalogu lub dodaj do PATH
        pause
        exit /b 1
    )
) else (
    set NSSM=nssm
)

REM Zainstaluj wymagane pakiety Python
echo [1/5] Instalacja zaleznosci Python...
pip install -r "%SCRIPT_DIR%requirements.txt" -q
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] pip install zakonczony z bledem - kontynuuje...
)

REM Stworz katalog logow
echo [2/5] Tworzenie katalogu logow: %LOG_DIR%
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Zatrzymaj istniejacy service (ignoruj blad jesli nie istnieje)
echo [3/5] Sprawdzam czy service juz istnieje...
%NSSM% status %SERVICE_NAME% >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [*] Service %SERVICE_NAME% istnieje - zatrzymuje i reinstaluje...
    %NSSM% stop %SERVICE_NAME% confirm >nul 2>&1
    %NSSM% remove %SERVICE_NAME% confirm >nul 2>&1
)

REM Znajdz pelna sciezke do pythona
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

REM Zainstaluj service przez NSSM
echo [4/5] Instalacja Windows Service przez NSSM...
%NSSM% install %SERVICE_NAME% "%PYTHON_PATH%" "%RUNNER_SCRIPT%"
%NSSM% set %SERVICE_NAME% AppDirectory "%SCRIPT_DIR%"
%NSSM% set %SERVICE_NAME% AppStdout "%LOG_DIR%\runner.log"
%NSSM% set %SERVICE_NAME% AppStderr "%LOG_DIR%\runner.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760
%NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START
%NSSM% set %SERVICE_NAME% AppRestartDelay 5000
%NSSM% set %SERVICE_NAME% Description "VSE Local Transcript Runner - fetches YouTube transcripts for PressAI Video SEO Engine"

REM Uruchom service
echo [5/5] Uruchamianie service...
%NSSM% start %SERVICE_NAME%

timeout /t 3 /nobreak >nul

%NSSM% status %SERVICE_NAME%

echo.
echo ================================================
echo [VSE Local Runner] Instalacja zakonczona!
echo.
echo Service: %SERVICE_NAME%
echo Log:     %LOG_DIR%\runner.log
echo Zarzadzanie: services.msc lub:
echo   net start %SERVICE_NAME%
echo   net stop  %SERVICE_NAME%
echo   nssm status %SERVICE_NAME%
echo ================================================
echo.
pause
