# DISPATCH — vse-dev-04 | Local Transcript Windows Service

**ID:** DISPATCH-VSE-DEV-04-20260615-LOCAL-SERVICE  
**Data:** 2026-06-15  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-04` (local-service)

> ⚠️ Ten dispatch dotyczy komponentu działającego LOKALNIE na PC Usera — nie na VPS.

---

## Kontekst — Dlaczego to zadanie istnieje

**CO:** `youtube-transcript-api` zwraca `No transcript available` gdy uruchamiana z Oracle Cloud VPS. Nie jest to błąd kodu — to IP ban YouTube na data center IPs. Kod działa poprawnie gdy uruchamiany lokalnie (z IP domowego/biurowego).

**PO CO:** VSE pipeline bez transkryptu nie działa — generator (Claude) nie ma danych wejściowych. Rozwiązaniem jest przeniesienie fetchowania transkryptów z VPS na lokalny PC Usera, który ma normalne IP.

**JAK (decyzja architektoniczna):** Windows Service na lokalnym PC polling API kolejki VSE → fetching lokalnie → zwrot transkryptu do API. Wzorzec: GitHub Actions self-hosted runner.

---

## Zakres implementacji

### 1. Backend API — nowe endpointy `/v1/jobs/`

Dodaj do `api/routers/` nowy router `jobs.py`:

```python
POST /v1/jobs/                     # Tworzy job (wywołuje pipeline /v1/generate)
GET  /v1/jobs/pending              # Zwraca listę jobów ze statusem 'pending' (dla local-runner)
POST /v1/jobs/{job_id}/result      # Local-runner przesyła transkrypt
GET  /v1/jobs/{job_id}             # Status job (polling z frontendu)
```

Model tabeli `transcript_jobs` (nowa tabela w DB):

```python
class TranscriptJob(Base):
    __tablename__ = "transcript_jobs"
    id: UUID PK auto
    video_url: str          # YouTube URL
    status: str             # 'pending' | 'fetched' | 'processing' | 'done' | 'failed'
    transcript: Text        # NULL do czasu zwrotu przez local-runner
    error: str              # NULL jeśli OK
    created_at: datetime
    updated_at: datetime
    user_id: UUID FK        # Kto zlecił
```

Auth dla local-runner: prosty Bearer token (`LOCAL_RUNNER_TOKEN` w `.env` VPS).
Local-runner wysyła `Authorization: Bearer <LOCAL_RUNNER_TOKEN>` przy każdym request.

### 2. Modyfikacja pipeline

W `api/services/pipeline.py` zmień logikę fetchera:

```python
async def fetch_transcript(video_url: str) -> str:
    # Jeśli LOCAL_RUNNER_MODE=true w env:
    #   → utwórz TranscriptJob w DB ze statusem 'pending'
    #   → poll job co 2s max 120s
    #   → gdy status='fetched' → pobierz transcript
    # Jeśli LOCAL_RUNNER_MODE=false (default):
    #   → stary kod youtube-transcript-api bezpośrednio
```

Zmienna env: `LOCAL_RUNNER_MODE=true` (dodaj do `.env` na VPS).

### 3. Local Runner — `local-runner/runner.py`

Nowy katalog `local-runner/` w repo:

```python
# local-runner/runner.py
import time
import requests
from youtube_transcript_api import YouTubeTranscriptApi

API_BASE = os.getenv("VSE_API_BASE", "https://vse.impresjapr.pl")
TOKEN = os.getenv("LOCAL_RUNNER_TOKEN")
POLL_INTERVAL = 10  # sekund

def main():
    while True:
        try:
            # Poll pending jobs
            r = requests.get(f"{API_BASE}/v1/jobs/pending",
                           headers={"Authorization": f"Bearer {TOKEN}"},
                           timeout=10)
            jobs = r.json()
            for job in jobs:
                process_job(job)
        except Exception as e:
            log.error(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)

def process_job(job):
    """Pobiera transkrypt lokalnie i wysyła wynik do API."""
    video_id = extract_video_id(job["video_url"])
    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["pl", "en"])
        text = " ".join([t.text for t in transcript])
        requests.post(
            f"{API_BASE}/v1/jobs/{job['id']}/result",
            json={"transcript": text, "status": "fetched"},
            headers={"Authorization": f"Bearer {TOKEN}"}
        )
        log.info(f"Job {job['id']}: transkrypt OK ({len(text)} znaków)")
    except Exception as e:
        requests.post(
            f"{API_BASE}/v1/jobs/{job['id']}/result",
            json={"status": "failed", "error": str(e)},
            headers={"Authorization": f"Bearer {TOKEN}"}
        )
```

### 4. Windows Service wrapper — `local-runner/service.py`

Użyj **NSSM** (Non-Sucking Service Manager) — nie piszemy kodu WinService w C#:

```python
# local-runner/install.bat
@echo off
echo [VSE Local Runner] Instalacja Windows Service...
pip install youtube-transcript-api requests python-dotenv
nssm install VSELocalRunner python "%~dp0runner.py"
nssm set VSELocalRunner AppDirectory "%~dp0"
nssm set VSELocalRunner AppEnvironmentExtra VSE_API_BASE=https://vse.impresjapr.pl
nssm set VSELocalRunner Start SERVICE_AUTO_START
nssm set VSELocalRunner AppRestartDelay 5000
net start VSELocalRunner
echo [VSE Local Runner] Zainstalowany i uruchomiony.
```

Pliki w `local-runner/`:
```
local-runner/
├── runner.py         # Główna logika pollingu
├── .env.example      # LOCAL_RUNNER_TOKEN=your_token_here
├── install.bat       # Instalator Windows (wymaga NSSM na PATH)
├── uninstall.bat     # Deinstalator
└── requirements.txt  # youtube-transcript-api, requests, python-dotenv
```

---

## Kolejność implementacji

1. **Tabela + endpointy** — `api/models/job.py` + `api/routers/jobs.py` (bez logiki pipeline)
2. **Migracja DB** — tabela `transcript_jobs` przez lifespan auto-create
3. **Modyfikacja pipeline** — `LOCAL_RUNNER_MODE` switch w `pipeline.py`
4. **local-runner/runner.py** — implementacja
5. **local-runner/install.bat** — instalator
6. **Testy** — `pytest tests/test_jobs.py` (unit, mock requests)
7. **Commit + push main**
8. **Deploy na VPS** — `git pull + docker compose build vse-api + up -d --no-deps --force-recreate vse-api`
9. **Ustaw `LOCAL_RUNNER_MODE=true` w `.env` na VPS**
10. **Zainstaluj local-runner na PC Usera**

---

## Kryteria akceptacji

- [ ] `GET /v1/jobs/pending` zwraca listę jobów (Bearer auth)
- [ ] `POST /v1/jobs/{id}/result` aktualizuje job w DB
- [ ] `runner.py` poprawnie pobiera transkrypt dla ID `XfGpTCMdvCE`
- [ ] `install.bat` instaluje service bez błędów (wymaga NSSM)
- [ ] Pipeline end-to-end: POST /v1/generate → job created → runner fetches → pipeline continues
- [ ] Log w `%ProgramData%\VSELocalRunner\runner.log`

---

## Uwagi operacyjne

- **NSSM** do pobrania: https://nssm.cc/download (skopiować `nssm.exe` do `local-runner/` lub na PATH)
- `LOCAL_RUNNER_TOKEN` generuj jako `secrets.token_urlsafe(32)` — wpisz do `.env` na VPS i `.env` w `local-runner/`
- Service name: `VSELocalRunner` (widoczny w `services.msc`)
- Restart polityka: auto-restart po 5s
- Log poziom: INFO domyślnie, DEBUG przez env `LOG_LEVEL=DEBUG`

---

## Raportowanie

Po zakończeniu dual-write:
1. `video-seo-engine/.agents/reports/YYYY-MM-DD_vse-dev-04_local-service.md`
2. `sonic-void/.agents/reports/inbox/YYYY-MM-DD_vse-dev-04_local-service.md`

*Supervisor 01 | sonic-void | 2026-06-15*
