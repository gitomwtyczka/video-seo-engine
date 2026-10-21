# Raport Wdrożenia Y1: YouTube Publish Fix

- **Data:** 2026-10-21 20:00 UTC | **Callsign:** vse-diag-yt
- **Merge Commit SHA:** `d07e3ebb80cdd13d7bdc09db49deb96067f57cca` (PR #6)
- **Snapshot TAG:** `20261021-195852` (poprzedni commit: `471d0a8a6caf7eb2e3e17ff4b3ab30e41d23c4c4`)
- **Smoke testy:**
  - Python import: `IMPORT OK` (`api.core.youtube_publish`, `api.routers.inject`, `api.services.pipeline`)
  - Logi `vse-api` i `vse-web`: czyste, 0 tracebacków
  - HTTP checks: `/docs` (200 OK), `/dashboard` (200 OK), `/` (200 OK)
- **Status wdrożenia:** SUKCES (kontenery `vse-api` i `vse-web` przebudowane i aktywne)
- **Komenda rollbacku (PowerShell):**
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/vse_rollback.sh 20261021-195852 --code"
```
