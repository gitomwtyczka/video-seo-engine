# DISPATCH: vtt-coverage-log-audit
**Target:** vse-analyst
**Repo:** video-seo-engine
**Data:** 2026-07-20

## Kontekst

Fix wdrożony w `local-runner/runner.py` (SHA `33fe7329`) o 19:35.
Serwis VSELocalRunner zrestartowany. Film testowy: `jae9brYJgcE` (~39 min).

## Zadanie — TYLKO fakty z logów

### 1. Runner log

```powershell
Get-Content 'C:\ProgramData\VSELocalRunner\runner.log' -Tail 80
```

Szukaj: `Processing job`, `VTT coverage: last segment at`, `yt-dlp+cookies_file OK`, `segments=`, błędy.

### 2. VPS docker logs

```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Potem (podmień NAZWA_KONTENERA):
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "docker logs --tail 60 --timestamps NAZWA_KONTENERA 2>&1"
```

Szukaj: `LOCAL_RUNNER_MODE`, `Job`, timeout errors.

### 3. Jeśli job nie pojawił się — napisz to wprost

## Format raportu

```
## Runner log — fakty
[linie z logu]

## VPS docker — fakty
[linie z logu]

## Wnioski
- Coverage: Xs (Xmin) — SUKCES / NIEPEŁNE / BRAK
- Metoda: cookies_file / browser / transcript-api
- Segmentów: N
- Błędy: tak/nie
```

## Dual-write

1. repo: `video-seo-engine` branch: `main` path: `.agents/reports/2026-07-20_vse-analyst_vtt-coverage-test.md`
2. repo: `sonic-void` branch: `master` path: `.agents/reports/inbox/2026-07-20_vse-analyst_vtt-coverage-test.md`
message: `report: vse-analyst vtt coverage log audit [vse-analyst]`