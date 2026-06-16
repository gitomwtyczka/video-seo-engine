# DISPATCH — vse-dev-06 | VTT Timestamps Fix (D1)

**ID:** DISPATCH-VSE-DEV-06-20260616-VTT-TIMESTAMPS  
**Data:** 2026-06-16  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-06`  
**Priorytet:** P1 — core quality fix  
**Scope:** `local-runner/` + `api/routers/jobs.py`  
**NIE DOTYKAJ:** `web/`, `api/routers/admin.py` (pracuje tam D4/dev-07)

---

## Definicja ukończenia — Twoja sesja jest kompletna gdy

> Zanim zaczniesz — zapamiętaj co oznacza DONE.

- [ ] Heartbeat `"status": "done"` z commit SHA w `last_completed[]`
- [ ] Rozdziały na `vse.impresjapr.pl` mają czasy (np. 02:15, 07:43)
- [ ] Raport w `video-seo-engine/.agents/reports/2026-06-16_vse-dev-06_vtt-timestamps.md`
- [ ] Raport w `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-06_vtt-timestamps.md`
- [ ] `project_status.json` zaktualizowany + lock zwolniony

---

## Kontekst — analiza Supervisora

### Root cause:
Skrypt produkcyjny `inject_rest_v5.py` (v5.3) używa **yt-dlp** lokalnie → pobiera `.vtt` z dokładnymi timestampami → LLM ma markery czasowe → `chapters[].time` jest precyzyjny.

Aplikacja VSE używa `youtube-transcript-api` przez Local Runner → zwraca **plain text BEZ timestampów** → generator nie ma skąd wziąć czasów → rozdziały pokazują `?` bez tytułów / `time=0`.

### Architektura Local Runner (aktualny stan po DEV-04):
```
Windows PC (VSELocalRunner Task Scheduler)
  → polling GET /v1/jobs/pending
  → pobiera transkrypt youtube-transcript-api
  → POST /v1/jobs/{id}/result {"transcript": "plain text"}
  → VPS pipeline.py dostaje plain text → LLM generuje bez czasów
```

### Cel:
```
Windows PC (VSELocalRunner)
  → polling GET /v1/jobs/pending
  → pobiera transkrypt Z TIMESTAMPAMI (format VTT lub lista segmentów)
  → POST /v1/jobs/{id}/result {"transcript": "VTT lub JSON list"}
  → VPS pipeline.py parsuje VTT → LLM dostaje tekst z markerami [MM:SS]
```

---

## Twoje zadanie

### Krok 1 — Przeczytaj aktualny kod

Przez GitHub MCP (branch: main):
1. `local-runner/runner.py` — jak pobiera transkrypt i co zwraca
2. `api/routers/jobs.py` — jak procesuje wynik od runnera
3. `api/services/pipeline.py` — jak używa transkryptu do generowania
4. `core/generator.py` — co dostaje na wejściu, co robi z VTT

### Krok 2 — Implementacja w Local Runner

`youtube-transcript-api` ma metody zwracające segmenty z timestampami:

```python
from youtube_transcript_api import YouTubeTranscriptApi

# Pobierz z timestampami
segments = YouTubeTranscriptApi.get_transcript(video_id, languages=['pl', 'en'])
# segments = [{"text": "...", "start": 12.5, "duration": 3.2}, ...]

# Sformatuj jako VTT-like text z markerami
def format_with_timestamps(segments):
    lines = []
    for seg in segments:
        m = int(seg['start'] // 60)
        s = int(seg['start'] % 60)
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)
```

Wyślij do API jako `transcript` z markerem `__VTT__` na początku żeby pipeline wiedział że to format z timestampami:
```json
{"transcript": "__VTT__\n[00:00] tekst...\n[02:15] kolejny segment..."}
```

### Krok 3 — Implementacja w pipeline.py / generator

W `api/services/pipeline.py` gdzie zapisuje `vtt_path` — sprawdź czy transkrypt zaczyna się od `__VTT__` i zachowaj format. Generator dostanie tekst z markerami.

Sprawdź `core/generator.py` — czy ma logikę parsowania `[MM:SS]` markerów. Jeśli nie — dodaj:
```python
def _parse_chapter_times(transcript_text):
    """Wyciąga [(seconds, text)] z tekstu z markerami [MM:SS]"""
    import re
    pattern = r'\[(\d{2}):(\d{2})\] (.+)'
    ...
```

### Krok 4 — Deploy

**Uwaga: Sprawdź deployment_locks w project_status.json PRZED deploy!**

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100
cd /home/ubuntu/video-seo-engine
git pull origin main

# Tylko te kontenery — NIE dotykaj vse-web (pracuje dev-07)
docker compose up -d --no-deps --force-recreate vse-api
```

Local Runner na Windows PC użytkownika:
- Zaktualizuje się automatycznie przy następnym git pull lub re-install
- Lub: użytkownik może uruchomić `git pull` i zrestartować Task Scheduler service

### Krok 5 — Test weryfikacyjny

1. Wklejenie URL YouTube na `vse.impresjapr.pl/dashboard`
2. Generuj SEO
3. Rozdziały powinny pokazywać: `02:15 — Tytuł Rozdziału` (z rzeczywistymi czasami)
4. Schema JSON-LD: `hasPart[].startOffset` ≠ 0

---

## Deployment Lock Protocol

Przed każdą komendą `docker compose`:
1. Pobierz `sonic-void/project_status.json` (GitHub MCP)
2. Sprawdź `deployment_locks.video-seo-engine`
3. Jeśli lock = inny agent — STOP, czekaj i napisz raport
4. Jeśli lock = wolny lub Twój callsign — możesz deployować
5. Po udanym deploy: zaktualizuj lock na `null`

---

## Architektura (przypomnienie)

```
Browser → nginx → FastAPI :8085
  POST /v1/generate → pipeline.py → Local Runner (transcript) → LLM → schema
  GET  /v1/jobs/pending → Local Runner polling
  POST /v1/jobs/{id}/result → runner callback
```

---

*Supervisor 01 | sonic-void | 2026-06-16 15:56*
