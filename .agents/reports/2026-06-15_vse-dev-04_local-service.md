# Raport: Local Transcript Windows Runner

**Agent:** `vse-dev-04`  
**Data:** 2026-06-15  
**Dispatch:** DISPATCH-VSE-DEV-04-20260615-LOCAL-SERVICE  
**Status:** ✅ ZAKOŃCZONY

---

## SHA Commitów

| # | SHA | Opis |
|---|-----|------|
| 1 | `7eb5288` | `api/models/job.py` — TranscriptJob SQLAlchemy model |
| 2 | `b6cf90d` | `api/routers/jobs.py` — `/v1/jobs/` endpoints + security |
| 3 | `fcffdba` | `api/main.py` — register jobs router, TranscriptJob in DB init |
| 4 | `fd08803` | `api/services/pipeline.py` — LOCAL_RUNNER_MODE switch, async job polling |
| 5 | `4f9acf1` | `local-runner/runner.py` — Windows Service polling logic |
| 6 | `9dbd32e` | `local-runner/install.bat` — NSSM installer |
| 7 | `aebb255` | `local-runner/uninstall.bat` |
| 8 | `8bb00ca` | `local-runner/requirements.txt` |
| 9 | `56c41d9` | `local-runner/.env.example` |
| 10 | `867af8a` | `local-runner/.gitignore` |
| 11 | `478f2b0` | `tests/test_jobs_security.py` — security tests |
| 12 | `5bd9143` | `local-runner/README.md` — documentation |

---

## Wyniki Testów

### Endpointy API (weryfikacja na VPS, port 8085)

| Endpoint | Test | Wynik |
|----------|------|-------|
| `GET /v1/jobs/pending` | Nieprawidłowy token | 401 (✅) |
| `GET /v1/jobs/pending` | Prawidłowy token | 200 `[]` (✅) |
| `DB init` | transcript_jobs tabela | Stworzona (✅) |
| `LOCAL_RUNNER_MODE` | Flag w logach | ENABLED (✅) |

### Logi VPS potwierdzające:
```
2026-06-15 22:20:21 [INFO] Database tables verified/created (incl. transcript_jobs).
2026-06-15 22:20:21 [INFO] Local Transcript Runner mode: ENABLED
2026-06-15 22:21:26 [WARNING] Runner auth: invalid token attempt
2026-06-15 22:21:37 [INFO] [jobs] /pending: 0 jobs returned for runner
```

---

## Konfiguracja VPS (.env)

Dodane do `/home/ubuntu/video-seo-engine/.env`:
```
LOCAL_RUNNER_TOKEN=XSaag87rZdA8h4mj01-UvFx-QIEwBvdsbTXR-K2W5_0
LOCAL_RUNNER_MODE=true
```

Kontener przebudowany i zrestartowany (`force-recreate`).

---

## Status Local Runner (PC Usera)

`local-runner/.env` skonfigurowany lokalnie z tokenem (git pull do `playground/video-seo-engine/local-runner/`).

**Do aktywacji przez Usera:**
1. Pobierz NSSM ze https://nssm.cc/download i skopiuj `nssm.exe` do `local-runner/`
2. Uruchom `install.bat` jako Administrator
3. Zweryfikuj w `services.msc`: service `VSELocalRunner` status `Running`

---

## Security Compliance (SUPPLEMENT-VSE-DEV-04-20260615-SECURITY)

| Ryzyko | Status | Implementacja |
|--------|--------|---------------|
| 🔴 RYZYKO 1 — Fake Transcript Injection | ✅ Zaimplementowane | `sanitize_transcript()` w `jobs.py` |
| 🟡 RYZYKO 2 — Brak Job Ownership Validation | ✅ Zaimplementowane | Idempotent check w `complete_job()` |
| 🟡 RYZYKO 3 — Rate Limiting | ✅ Zaimplementowane | `_check_rate_limit()`, 30 req/min |
| 🟡 RYZYKO 4 — Token Storage | ✅ Spełnione | `secrets.token_urlsafe(32)`, `.gitignore` |
| 🟢 RYZYKO 5 — Transport Security | ✅ OK | HTTPS/Cloudflare |

---

## Architektura Zaimplementowana

```
PC Usera                    VPS (Oracle Cloud)
[runner.py]                 [API FastAPI]
    │                           │
    ├── GET /v1/jobs/pending ────►  TranscriptJob DB
    │   (Bearer token)           status='pending'
    │
    ├── youtube-transcript-api     (lokalne IP OK)
    │   (lokalnie, bez bana IP)
    │
    └── POST /v1/jobs/{id}/result   job.status='fetched'
        (Bearer token, HTTPS)      job.transcript=...
                                       │
                                   pipeline.py
                                   LOCAL_RUNNER_MODE=true
                                   _wait_for_transcript()
                                       │
                                   Claude/Gemini
                                   SEO generation
```

---

*vse-dev-04 | video-seo-engine | 2026-06-15*
