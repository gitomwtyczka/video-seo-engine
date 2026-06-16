## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Przeczytaj blok systemowy:**
view_file → .agents/protocols/dispatch-system-block.md (jeśli istnieje)

---

# TASK: vse-runner-01 — Local Runner Recovery

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Workspace:** video-seo-engine  
**Priorytet:** 🔴 PILNE — blokuje VTT timestamps w rozdziałach

---

## Twój callsign: `[vse-runner-01 | video-seo-engine]`

## Twój deliverable:
Działający VSELocalRunner Windows service z zaktualizowaną wersją runner.py (VTT fix z main)

---

## Dostęp do maszyny

**Wszystkie komendy przez `run_command` (PowerShell, lokalny Windows):**
- Lokalne komendy Windows: `run_command` bezpośrednio
- VPS: `run_command: ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "komenda"`
- **FILE BRIDGE / Wetty: ZAKAZ — deprecated**

---

## Problem

`git pull` na repozytorium `video-seo-engine` jest zablokowany przez untracked plik `local-runner/service.py`. 
Ten plik zawiera lokalną konfigurację specyficzną dla tej maszyny — NIE można go nadpisać.

**Cel:** Zaktualizować TYLKO `runner.py` bez dotykania `service.py`.

---

## Komendy do wykonania (w tej kolejności)

```powershell
# 1. Przeć do katalogu projektu
cd C:\Users\tobroz\projects\video-seo-engine

# 2. Pobierz zmiany z remote bez merge
git fetch origin main

# 3. Checkout TYLKO runner.py z origin/main
git checkout origin/main -- local-runner/runner.py

# 4. Zweryfikuj VTT patch
Select-String -Path "local-runner\runner.py" -Pattern "__VTT__"

# 5. Zrestartuj serwis
net stop VSELocalRunner
net start VSELocalRunner

# 6. Sprawdź status
Get-Service VSELocalRunner | Select-Object Status, DisplayName
```

---

## Jeśli serwis nie startuje po restarcie

```powershell
Get-Content "C:\ProgramData\VSELocalRunner\runner.log" -Tail 50
```

Zaraportuj logi do Supervisora — nie próbuj naprawiać samodzielnie jeśli błąd jest nieznany.

---

## Raport po wykonaniu

Na końcu wyślij raport do:
1. `video-seo-engine/.agents/reports/2026-06-16_vse-runner-01_local-runner-recovery.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-runner-01_local-runner-recovery.md`

Treść: wynik każdej komendy + status serwisu + czy VTT patch widać w kodzie.

---

## Protokół callsign (OBOWIĄZKOWE)

Każda odpowiedź zaczyna się i kończy:
```
[vse-runner-01 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-runner-01 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

---

*Supervisor 03 | sonic-void | 2026-06-16 18:12*
