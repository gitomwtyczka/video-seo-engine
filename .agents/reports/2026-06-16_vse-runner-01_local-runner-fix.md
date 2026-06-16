# Raport: Fix Local Runner Windows Service

**Agent:** vse-runner-01  
**Data:** 2026-06-16  
**Temat:** Naprawa VSELocalRunner + migracja pywin32 → NSSM + DEV-06 VTT fix

---

## Status: ✅ DONE

Serwis `VSELocalRunner` działa. DEV-06 (__VTT__ timestamp fix) aktywny.

---

## Co zostało zrobione

### 1. Dostarczenie DEV-06 (VTT fix) do Local Runnera

```powershell
git fetch origin main
git checkout origin/main -- local-runner/runner.py
# (jobs.py nie istnieje w repo — pomięto bez błędu logicznego)
```

Weryfikacja:
```
local-runner\runner.py:148: lines = ["__VTT__"]
local-runner\runner.py:375: log.info("Transcript format: __VTT__ with [MM:SS] timestamps")
```

`service.py` NIE był dotykany (untracked — zgodnie z dispatch).

### 2. Diagnoza problemu NET HELPMSG 2186

Root cause:
- `BINARY_PATH_NAME: C:\Python314\pythonservice.exe` — tylko 20KB (stub, nie pełny)
- Brak `Parameters\PythonServicePath` w rejestrze — pythonservice.exe nie wiedział gdzie jest `service.py`
- pywin32 był zainstalowany w `AppData\Roaming\Python314\site-packages` (user profile)
- Serwis działa jako `LocalSystem` — nie ma dostępu do user profile
- Skutek: `import requests` crashował natychmiast → SCM dostał timeout → 2186

Potwierdzenie w DEBUG mode:
```
Runner loop started | API=https://vse.impresjapr.pl | poll=10s | token_set=True
```
→ runner.py działa poprawnie, problem był wyłącznie w warstwie serwisu.

### 3. Migracja serwisu: pywin32 → NSSM

```powershell
# Usunięcie starego
python service.py remove

# Instalacja NSSM
choco install nssm -y

# Rejestracja nowego serwisu
nssm install VSELocalRunner "C:\Python314\python.exe" "runner.py"
nssm set VSELocalRunner AppDirectory "C:\...\local-runner"
nssm set VSELocalRunner AppStdout "C:\ProgramData\VSELocalRunner\stdout.log"
nssm set VSELocalRunner AppStderr "C:\ProgramData\VSELocalRunner\stderr.log"
nssm set VSELocalRunner AppRotateFiles 1
nssm set VSELocalRunner AppEnvironmentExtra "PYTHONPATH=C:\Python314\Lib\site-packages"
```

### 4. Instalacja zależności globalnie (LocalSystem access)

```powershell
python -m pip install --target C:\Python314\Lib\site-packages requests python-dotenv youtube-transcript-api
```

Zainstalowane: `requests-2.34.2`, `python-dotenv-1.2.2`, `youtube-transcript-api-1.2.4`

### 5. Finalny status

```
Status: Running
2026-06-16 18:23:34 [INFO] VSE Local Transcript Runner started
2026-06-16 18:23:34 [INFO] API: https://vse.impresjapr.pl
2026-06-16 18:23:34 [INFO] Poll interval: 10s
2026-06-16 18:23:34 [INFO] Transcript format: __VTT__ with [MM:SS] timestamps
```

---

## Uwagi dla następnej sesji

### Gotcha: NSSM vs pywin32

**NSSM jest teraz stałym wrapperem** (nie pywin32). `service.py` jest nadal w katalogu ale NIE jest używany przez Windows Service. NSSM wywołuje bezpośrednio `python runner.py`.

```
Install: nssm install VSELocalRunner "C:\Python314\python.exe" "runner.py"
Start:   net start VSELocalRunner  (jako Admin)
Stop:    net stop VSELocalRunner   (jako Admin)
Logi:    C:\ProgramData\VSELocalRunner\stdout.log
         C:\ProgramData\VSELocalRunner\stderr.log
```

### Python 3.14 + pywin32 = broken

Pywin32 nie obsługuje poprawnie Python 3.14 (pythonservice.exe = 20KB stub zamiast ~100KB). Jeśli ktokolwiek będzie chciał wrócić do pywin32 — wymaga reinstalacji Python 3.11/3.12 lub pełnego pywin32 postinstall.

### Zależności lokalnie

Paczki są teraz w dwóch miejscach:
- `C:\Users\tomas2\AppData\Roaming\Python\Python314\site-packages` (user — działa dla CLI)
- `C:\Python314\Lib\site-packages` (system — działa dla LocalSystem service)

NSSM ma ustawiony `PYTHONPATH=C:\Python314\Lib\site-packages` dla pewności.

---

*vse-runner-01 | video-seo-engine | 2026-06-16*
