# Raport: core/fetcher.py — Port + API v3 Fix

**Agent:** vse-strateg-01  
**Data:** 2026-06-15  
**Dispatch:** DISPATCH-VSE-STRATEG-02-20260615-CORE-PORT.md  
**Status:** ✅ WYKONANE (z blockerem: transcript IP ban)

---

## Co zostało zrobione

### Commits
| Commit | Opis |
|--------|------|
| `3b062f3` | `core/fetcher.py` — API v3 zastępuje yt-dlp metadata (główny fix) |
| `4149f98` | `api/core/fetcher.py` — port (redundant, `/app/core/` ma pierwszeństwo) |
| `e482d64` | `api/core/__init__.py` — nowy pakiet |

### Root cause fix

Problem: `core/fetcher.py` w root repozytorium był starą wersją używającą `fetch_metadata_ytdlp()` — która fails na Oracle Cloud VPS (YouTube IP ban).

Fix: Zaktualizowałem `core/fetcher.py` z nową logiką:
```python
api_key = os.environ.get("YOUTUBE_API_KEY", "")
if api_key:
    meta = fetch_metadata_api_v3(video_id, api_key)  # googleapis.com — nie blokowane
else:
    meta = fetch_metadata_ytdlp(video_id)  # fallback lokalny
```

### Dodano do VPS .env
```
YOUTUBE_API_KEY=AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo
```
GCP project: `glass-turbine-388620` (Simple API Key, public data)

### Wynik testu
```
[fetcher] API v3 OK: XfGpTCMdvCE 
  title='Syndyk zniszczył moją firmę. Celowo. Oto dowody'
  duration=PT17M14S
  views=377
```
**Metadata fetch: DZIAŁA ✅**

---

## Pozostały bloker

**youtube-transcript-api RÓWNIEŻ zablokowana przez IP ban Oracle Cloud.**

Error: `Could not retrieve a transcript — YouTube is blocking requests from your IP`

To oddzielny problem — poza zakresem tego dispatcha. Opcje:
1. Proxy dla transcript-api (koszt infra)
2. OAuth cookies (ryzykowne)
3. Personal API / prywatna sieć

🚦 BLOKUJE: `/v1/process` zwraca `RuntimeError: No transcript available` — bez transkryptu generator nie może działać.

---

## Architektura po poprawce

```
VPS request flow:
  /v1/process
    → pipeline.py → core.fetcher.process_video()
      → fetch_metadata_api_v3()  # googleapis.com ✅ (nie blokowane)
      → fetch_transcript_api()   # youtube-transcript-api ❌ (IP ban)
      → fetch_transcript_ytdlp() # yt-dlp ❌ (IP ban)
      → metadata OK, transcript FAILED
```

---

*vse-strateg-01 | video-seo-engine | 2026-06-15 21:54*
