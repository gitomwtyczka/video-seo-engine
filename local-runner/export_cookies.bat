@echo off
REM VSE Cookie Exporter v2 — uruchamiany przez Task Scheduler jako zalogowany user
REM Eksportuje cookies YouTube z przegladarki do pliku dla NSSM serwisu
REM Uruchamia sie przy logowaniu + codziennie o 06:00

setlocal
set COOKIE_FILE=C:\ProgramData\VSELocalRunner\yt_cookies.txt
set COOKIE_FILE_TMP=C:\ProgramData\VSELocalRunner\yt_cookies.tmp
set LOG=C:\ProgramData\VSELocalRunner\cookie_export.log

REM URL konkretnego wideo — nie strony glownej (unika wisania na playlistach)
set YT_URL=https://www.youtube.com/watch?v=yPRRbK1WLRs

echo [%DATE% %TIME%] Starting cookie export... >> "%LOG%" 2>&1

REM Upewnij sie ze katalog istnieje
if not exist "C:\ProgramData\VSELocalRunner" mkdir "C:\ProgramData\VSELocalRunner"

REM Probuj Chrome -> Firefox -> Edge w kolejnosci
set EXPORTED=0

REM Chrome
yt-dlp --cookies-from-browser chrome --cookies "%COOKIE_FILE_TMP%" --skip-download --no-playlist --quiet "%YT_URL%" >nul 2>&1
if exist "%COOKIE_FILE_TMP%" (
    echo [%DATE% %TIME%] Chrome cookies exported OK >> "%LOG%"
    move /Y "%COOKIE_FILE_TMP%" "%COOKIE_FILE%" >nul
    set EXPORTED=1
    goto done
)
echo [%DATE% %TIME%] Chrome failed, trying Firefox... >> "%LOG%"

REM Firefox
yt-dlp --cookies-from-browser firefox --cookies "%COOKIE_FILE_TMP%" --skip-download --no-playlist --quiet "%YT_URL%" >nul 2>&1
if exist "%COOKIE_FILE_TMP%" (
    echo [%DATE% %TIME%] Firefox cookies exported OK >> "%LOG%"
    move /Y "%COOKIE_FILE_TMP%" "%COOKIE_FILE%" >nul
    set EXPORTED=1
    goto done
)
echo [%DATE% %TIME%] Firefox failed, trying Edge... >> "%LOG%"

REM Edge
yt-dlp --cookies-from-browser edge --cookies "%COOKIE_FILE_TMP%" --skip-download --no-playlist --quiet "%YT_URL%" >nul 2>&1
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

for %%A in ("%COOKIE_FILE%") do echo [%DATE% %TIME%] Cookie file ready: %%~zA bytes >> "%LOG%"
exit /b 0
