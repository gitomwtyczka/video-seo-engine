@echo off
REM ==========================================================================
REM VSE Local Transcript Runner - Instalator Windows Service v3.3
REM Wymaga: NSSM na PATH (zainstalowany przez Chocolatey) lub nssm.exe tutaj
REM
REM Uruchom prawym przyciskiem -> "Uruchom jako administrator"
REM
REM Co instaluje:
REM  1. Windows Service VSELocalRunner (NSSM, LocalSystem, AUTO_START)
REM  2. Task Scheduler VSECookieExport (jako biezacy user, ONLOGON + codziennie 06:00)
REM     eksportuje cookies YouTube z przegladarki do pliku dla serwisu
REM     Plik: C:\ProgramData\VSELocalRunner\yt_cookies.txt
REM ==========================================================================

setlocal EnableDelayedExpansion

set SERVICE_NAME=VSELocalRunner
set SCRIPT_DIR=%~dp0
set RUNNER_SCRIPT=%SCRIPT_DIR%runner.py
set LOG_DIR=C:\ProgramData\VSELocalRunner
set COOKIE_EXPORT=%SCRIPT_DIR%export_cookies.bat

echo.
echo [VSE Local Runner] Instalator Windows Service v3.3
echo ====================================================
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

REM Sprawdz czy NSSM jest dostepny — uzyj bezposrednio tools binary (nie Chocolatey shim)
set NSSM_TOOLS=C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe
if exist "%NSSM_TOOLS%" (
    set NSSM=%NSSM_TOOLS%
    echo [*] NSSM znaleziony: %NSSM_TOOLS%
) else (
    where nssm >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set NSSM=nssm
        echo [*] NSSM z PATH
    ) else if exist "%SCRIPT_DIR%nssm.exe" (
        set NSSM=%SCRIPT_DIR%nssm.exe
        echo [*] NSSM lokalny: %SCRIPT_DIR%nssm.exe
    ) else (
        echo [ERROR] NSSM nie znaleziony!
        echo Pobierz ze: https://nssm.cc/download i skopiuj nssm.exe do tego katalogu
        pause
        exit /b 1
    )
)

REM Zainstaluj wymagane pakiety Python
echo [1/6] Instalacja zaleznosci Python...
pip install -r "%SCRIPT_DIR%requirements.txt" -q
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] pip install zakonczony z bledem - kontynuuje...
)

REM Stworz katalog logow
echo [2/6] Tworzenie katalogu logow: %LOG_DIR%
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Zatrzymaj istniejacy service
echo [3/6] Sprawdzam czy service juz istnieje...
%NSSM% status %SERVICE_NAME% >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [*] Service %SERVICE_NAME% istnieje - zatrzymuje i reinstaluje...
    %NSSM% stop %SERVICE_NAME% confirm >nul 2>&1
    %NSSM% remove %SERVICE_NAME% confirm >nul 2>&1
)

REM Znajdz pelna sciezke do pythona (bierz pierwsza znaleziona)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_PATH set PYTHON_PATH=%%i
)
echo [*] Python: %PYTHON_PATH%

REM Zainstaluj service przez NSSM
echo [4/6] Instalacja Windows Service przez NSSM...
%NSSM% install %SERVICE_NAME% "%PYTHON_PATH%" "%RUNNER_SCRIPT%"
%NSSM% set %SERVICE_NAME% AppDirectory "%SCRIPT_DIR%"
%NSSM% set %SERVICE_NAME% AppStdout "%LOG_DIR%\runner.log"
%NSSM% set %SERVICE_NAME% AppStderr "%LOG_DIR%\runner.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760
%NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START
%NSSM% set %SERVICE_NAME% AppRestartDelay 5000
%NSSM% set %SERVICE_NAME% Description "VSE Local Transcript Runner v3.3 - YouTube transcripts for Video SEO Engine"

REM Uruchom service
echo [5/6] Uruchamianie service...
%NSSM% start %SERVICE_NAME%
timeout /t 3 /nobreak >nul
%NSSM% status %SERVICE_NAME%

REM Zarejestruj Task Scheduler dla odnawiania cookies YouTube
echo [6/6] Rejestracja Task Scheduler dla cookie export...
schtasks /Delete /TN "VSECookieExport" /F >nul 2>&1
schtasks /Delete /TN "VSECookieExportDaily" /F >nul 2>&1

for /f "tokens=*" %%u in ('whoami') do set CURRENT_USER=%%u
echo [*] Cookie export user: %CURRENT_USER%
schtasks /Create /TN "VSECookieExport" /TR "%COOKIE_EXPORT%" /SC ONLOGON /RU "%CURRENT_USER%" /RL HIGHEST /F
schtasks /Create /TN "VSECookieExportDaily" /TR "%COOKIE_EXPORT%" /SC DAILY /ST 06:00 /RU "%CURRENT_USER%" /RL HIGHEST /F

echo [*] Pierwsze pobranie cookies...
call "%COOKIE_EXPORT%"

echo.
echo ====================================================
echo [VSE Local Runner] Instalacja zakonczona! v3.3
echo.
echo Service:     %SERVICE_NAME% (LocalSystem, AUTO_START)
echo Log:         %LOG_DIR%\runner.log
echo Cookies:     %LOG_DIR%\yt_cookies.txt
echo              (odnawiane przy logowaniu + codziennie o 06:00)
echo.
echo Zarzadzanie:
echo   net start %SERVICE_NAME%
echo   net stop  %SERVICE_NAME%
echo   nssm status %SERVICE_NAME%
echo.
echo Reczne odswiezenie cookies:
echo   %COOKIE_EXPORT%
echo ====================================================
echo.
pause
