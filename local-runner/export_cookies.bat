@echo off
REM VSE Cookie Exporter — uruchamiany przez Task Scheduler jako tomas2
REM Eksportuje cookies YouTube z przeglądarki do pliku dla NSSM serwisu
REM Uruchamia się przy każdym logowaniu + codziennie o 06:00

setlocal
set COOKIE_FILE=C:\ProgramData\VSELocalRunner\yt_cookies.txt
set COOKIE_FILE_TMP=C:\ProgramData\VSELocalRunner\yt_cookies.tmp
set LOG=C:\ProgramData\VSELocalRunner\cookie_export.log

echo [%DATE% %TIME%] Starting cookie export... >> "%LOG%"

REM Próbuj Chrome -> Firefox -> Edge w kolejności
set EXPORTED=0

REM Chrome
yt-dlp --cookies-from-browser chrome --cookies "%COOKIE_FILE_TMP%" --skip-download --quiet "https://www.youtube.com/" >nul 2>&1
if exist "%COOKIE_FILE_TMP%" (
    echo [%DATE% %TIME%] Chrome cookies exported OK >> "%LOG%"
    move /Y "%COOKIE_FILE_TMP%" "%COOKIE_FILE%" >nul
    set EXPORTED=1
    goto done
)

REM Firefox
yt-dlp --cookies-from-browser firefox --cookies "%COOKIE_FILE_TMP%" --skip-download --quiet "https://www.youtube.com/" >nul 2>&1
if exist "%COOKIE_FILE_TMP%" (
    echo [%DATE% %TIME%] Firefox cookies exported OK >> "%LOG%"
    move /Y "%COOKIE_FILE_TMP%" "%COOKIE_FILE%" >nul
    set EXPORTED=1
    goto done
)

REM Edge
yt-dlp --cookies-from-browser edge --cookies "%COOKIE_FILE_TMP%" --skip-download --quiet "https://www.youtube.com/" >nul 2>&1
if exist "%COOKIE_FILE_TMP%" (
    echo [%DATE% %TIME%] Edge cookies exported OK >> "%LOG%"
    move /Y "%COOKIE_FILE_TMP%" "%COOKIE_FILE%" >nul
    set EXPORTED=1
    goto done
)

:done
if %EXPORTED%==0 (
    echo [%DATE% %TIME%] ERROR: All browsers failed to export cookies >> "%LOG%"
    exit /b 1
)

echo [%DATE% %TIME%] Cookie file ready: %COOKIE_FILE% >> "%LOG%"
exit /b 0
