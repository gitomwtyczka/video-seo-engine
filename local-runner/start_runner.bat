@echo off
REM VSE Local Transcript Runner — Task Scheduler launcher
REM Uruchamiaj przez Task Scheduler jako zalogowany użytkownik
REM NIE uruchamiaj ręcznie w pętli — runner.py sam loopuje

cd /D "%~dp0"

REM Sprawdź czy Python dostępny
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python nie znaleziony w PATH. Zainstaluj Python 3.10+.
    exit /b 1
)

REM Załaduj .env i uruchom runnera
echo [%DATE% %TIME%] VSE Runner starting via Task Scheduler...
python runner.py

REM Jeśli runner crashuje, czekaj 10s i uruchom ponownie
echo [%DATE% %TIME%] Runner exited (code %errorlevel%) — restarting in 10s...
timeout /t 10 /nobreak >nul
python runner.py
