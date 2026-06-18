# VSE Local Runner — Installer Issues Log

Data: 2026-06-18 | Agent: Supervisor 05 | Sesja: edd9efd8

Cel: dokumentacja wszystkich problemów napotkanych podczas instalacji runnera
na potrzeby stworzenia instalatora który zadziała na każdym komputerze.

---

## BŁĄD 1 — Chocolatey NSSM shim zablokowany przez Device Guard

**Objaw:**
```
'C:\ProgramData\chocolatey\bin\nssm.exe' was blocked by your organization's Device Guard policy.
```

**Kiedy:** Wywołanie nssm.exe przez subprocess / Start-Process z poziomu agenta lub skryptu.

**Przyczyna:** `C:\ProgramData\chocolatey\bin\nssm.exe` to Chocolatey **shim** (wrapper), nie prawdziwy binary.
Niektóre polityki Device Guard blokują shim ale nie oryginalny plik.

**Fix:** Użyj bezpośredniej ścieżki do prawdziwego binary:
```
C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe
```

**Installer check:**
```bat
set NSSM_TOOLS=C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe
if exist "%NSSM_TOOLS%" (
    set NSSM=%NSSM_TOOLS%
) else (
    where nssm >nul 2>&1 && set NSSM=nssm || goto :nssm_error
)
```

---

## BŁĄD 2 — NSSM AppDirectory z trailing quote w rejestrze

**Objaw:**
```
Failed to start service VSELocalRunner.
CreateProcess() failed: Nazwa katalogu jest nieprawidłowa.
```

**Kiedy:** Po instalacji przez NSSM gdy ścieżka AppDirectory przekazywana jest w cudzysłowach.

**Przyczyna:** NSSM zapisał w rejestrze:
```
AppDirectory = C:\Users\tomas2\...\local-runner"
```
Trailing `"` na końcu ścieżki powoduje że CreateProcess() nie może znaleźć katalogu.

**Fix:**
```bat
reg add "HKLM\SYSTEM\CurrentControlSet\Services\VSELocalRunner\Parameters" /v AppDirectory /t REG_EXPAND_SZ /d "SCIEZKA_BEZ_CUDZYSLOWU" /f
```

**Installer check:** Po instalacji zawsze weryfikuj AppDirectory:
```bat
for /f "tokens=3" %%v in ('reg query "HKLM\...\Parameters" /v AppDirectory') do set CHECK=%%v
if "%CHECK:~-1%"=="""" echo WARNING: trailing quote detected
```

---

## BŁĄD 3 — UnicodeEncodeError w Windows Service (cp1250)

**Objaw:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
Runner exits immediately, runner.log = 0 bytes
```

**Kiedy:** runner.py zawiera znaki Unicode (→, ←, emoji) w log.info() lub docstrings.
Windows Service domyślnie używa cp1250 (lub lokalnej strony kodowej) — nie UTF-8.

**Przyczyna:** `sys.stdout` w kontekście serwisu to plik otwarty przez NSSM w lokalnej
stronie kodowej Windows. Polskie znaki diakrytyczne i strzałki Unicode nie są obsługiwane.

**Fix w kodzie:**
```python
# Na początku runner.py, przed inicjalizacją loggera:
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
```

**Fix prewencyjny:** W log.info() używaj ASCII zamiast Unicode arrows:
- `→` → `->`
- `←` → `<-`

**Fix prewencyjny 2:** W docstringach unikaj ścieżek Windows z backslashem:
```python
# ZLE:
"Plik w C:\ProgramData\..."  # \P = SyntaxWarning
# DOBRZE:
"Plik w C:\\ProgramData\\..."  # podwójny backslash
```

---

## BŁĄD 4 — SyntaxWarning: invalid escape sequence \P w docstringu

**Objaw:**
```
SyntaxWarning: "\P" is an invalid escape sequence
Service exits immediately (Python 3.14 traktuje to jako błąd)
```

**Kiedy:** Docstring zawiera ścieżkę Windows: `C:\ProgramData\...`

**Przyczyna:** `\P` nie jest valid escape sequence w Python. W Python 3.12+ to DeprecationWarning,
w 3.14+ może być SyntaxError. Powoduje crash przy starcie serwisu.

**Fix:** `C:\\ProgramData\\...` lub raw string `r"C:\ProgramData\..."`

---

## BŁĄD 5 — Permission denied: runner.log (LocalSystem brak dostępu do katalogu)

**Objaw:**
```
PermissionError: [Errno 13] Permission denied: 'C:\ProgramData\VSELocalRunner\runner.log'
Service exits immediately, log file = 0 bytes
```

**Kiedy:** Katalog `C:\ProgramData\VSELocalRunner` stworzony przez użytkownika,
nie przez SYSTEM. NSSM uruchamia serwis jako LocalSystem.

**Fix:**
```bat
icacls "C:\ProgramData\VSELocalRunner" /grant "SYSTEM:(OI)(CI)F" /T
```

**Installer:** Twórz katalog logu jako krok instalatora (jako admin) i od razu ustaw uprawnienia:
```bat
mkdir "%LOG_DIR%" 2>nul
icacls "%LOG_DIR%" /grant "SYSTEM:(OI)(CI)F" /T
icacls "%LOG_DIR%" /grant "Użytkownicy:(OI)(CI)M" /T
```

---

## BŁĄD 6 — LocalSystem nie może odczytać cookies przeglądarki (DPAPI)

**Objaw:**
```
ERROR: could not find chrome cookies database in
"C:\WINDOWS\system32\config\systemprofile\AppData\Local\Google\Chrome\User Data"
```

**Kiedy:** yt-dlp z `--cookies-from-browser chrome/firefox/edge` uruchomiony w kontekście LocalSystem.

**Przyczyna:** Cookies przeglądarek są szyfrowane kluczem DPAPI powiązanym z kontem użytkownika.
LocalSystem ma inny profil (`systemprofile`) i nie może odszyfrować cookies tomas2.

**Fix (architektoniczny):** Dual-strategy:
1. Eksport cookies do pliku przez Task Scheduler (uruchomiony jako zalogowany user):
   ```
   yt-dlp --cookies-from-browser firefox --cookies C:\ProgramData\VSELocalRunner\yt_cookies.txt --skip-download --no-playlist "URL"
   ```
2. Serwis (LocalSystem) używa `--cookies yt_cookies.txt` zamiast `--cookies-from-browser`

**Installer:** Zarejestruj Task Scheduler dla cookie export:
```bat
schtasks /Create /TN "VSECookieExport" /TR "%COOKIE_EXPORT%" /SC ONLOGON /RU "%CURRENT_USER%" /RL HIGHEST /F
schtasks /Create /TN "VSECookieExportDaily" /TR "%COOKIE_EXPORT%" /SC DAILY /ST 06:00 /RU "%CURRENT_USER%" /RL HIGHEST /F
```

---

## BŁĄD 7 — yt-dlp nie może zapisać cookies po sesji (PermissionError)

**Objaw:**
```
PermissionError: [Errno 13] Permission denied: 'C:\ProgramData\VSELocalRunner\yt_cookies.txt'
yt-dlp exit=1 mimo że VTT pobrany (467KB)
```

**Kiedy:** yt-dlp uruchomiony jako tomas2 próbuje nadpisać plik cookies który
był stworzony przez SYSTEM (ma ACL: Użytkownicy=(RX) — tylko odczyt).

**Fix:**
```bat
icacls "C:\ProgramData\VSELocalRunner\yt_cookies.txt" /grant "Użytkownicy:(M)"
```

**Installer:** Po stworzeniu pliku cookies zawsze ustaw uprawnienia:
```bat
icacls "%LOG_DIR%\yt_cookies.txt" /grant "Użytkownicy:(M)" 2>nul
```

---

## BŁĄD 8 — deno niewidoczny dla LocalSystem (user-level install)

**Objaw:**
```
WARNING: [youtube] Falling back to generic n function search
cookies_file: No VTT for lang=pl exit=1
```

**Kiedy:** yt-dlp uruchomiony przez serwis (LocalSystem) próbuje rozwiązać
YouTube JS challenge (n-parameter) przez deno. Deno zainstalowane przez WinGet
w profilu użytkownika → niewidoczne dla SYSTEM.

**Lokalizacja deno (user-level):**
```
C:\Users\{USER}\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_*\deno.exe
```

**Fix:** Dodaj deno do systemowego PATH (Machine scope):
```powershell
$denoDir = Split-Path (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\DenoLand.Deno*\deno.exe" -Recurse | Select-Object -First 1 -ExpandProperty FullName)
$machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
if ($machinePath -notlike "*$denoDir*") {
    [System.Environment]::SetEnvironmentVariable('Path', "$machinePath;$denoDir", 'Machine')
}
```
Potem restart serwisu (pobierze nowy PATH).

**Alternatywa:** Zainstaluj deno system-wide: `winget install DenoLand.Deno --scope machine`

**Installer check:**
```bat
where deno >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: deno not found in system PATH
    echo yt-dlp will fall back to generic n function — some videos may fail
    echo Install deno system-wide: winget install DenoLand.Deno --scope machine
)
```

---

## BŁĄD 9 — export_cookies.bat wisi na playlistach YouTube

**Objaw:** `export_cookies.bat` uruchomiony z `https://www.youtube.com/` jako URL
nigdy nie kończy — yt-dlp próbuje przetworzyć wszystkie playlisty ze strony głównej.

**Fix:** Użyj konkretnego video URL z flagą `--no-playlist`:
```bat
yt-dlp --cookies-from-browser firefox --cookies "%COOKIE_FILE%" --skip-download --no-playlist --quiet "https://www.youtube.com/watch?v=KONKRETNE_ID"
```

---

## PODSUMOWANIE — Checklist dla bulletproof installer

```
[PREREQ] Python 3.10+ zainstalowany system-wide
[PREREQ] yt-dlp zainstalowany (pip install yt-dlp)
[PREREQ] NSSM — użyj tools/nssm.exe, nie chocolatey shim
[PREREQ] deno — sprawdź czy w systemowym PATH (nie user PATH)

[INSTALL]
1. mkdir C:\ProgramData\VSELocalRunner
2. icacls LOG_DIR /grant SYSTEM:(OI)(CI)F /T
3. icacls LOG_DIR /grant Użytkownicy:(OI)(CI)M /T
4. NSSM install (tools binary, nie shim)
5. Weryfikacja AppDirectory bez trailing quote
6. NSSM start → sprawdź event log (nie tylko runner.log)
7. schtasks VSECookieExport (ONLOGON + DAILY 06:00)
8. Pierwsze pobranie cookies (call export_cookies.bat)
9. icacls yt_cookies.txt /grant Użytkownicy:(M)
10. Restart serwisu (żeby pobrał nowy PATH z deno)

[WERYFIKACJA]
- Get-Service VSELocalRunner → Running
- Get-Content runner.log | Select -Last 5 → 'No pending jobs'
- Test: wklej URL YouTube → powinno pobrać transkrypt
```

---

## TODO — Znane ograniczenia (do rozwiązania)

- [ ] Cookies wygasają co ~2 tygodnie — potrzebny reminder dla usera lub auto-detect
- [ ] deno path hardcoded na tomas2 — installer musi wykrywać dynamicznie
- [ ] runner.py exit=1 gdy yt-dlp crashuje przy save_cookies ale VTT już na dysku — VTT jest tracony
- [ ] Brak obsługi filmów bez napisów — user dostaje generyczny błąd IP-block zamiast "no captions"
- [ ] Brak mechanizmu wykrywania czy film w ogóle ma napisy przed próbą pobrania

---
*Supervisor 05 | video-seo-engine | 2026-06-18*
