# RAPORT AUDYTU — YouTube Knowledge Audit
## shadow-perihelion + sonic-void → video-seo-engine

**Agent:** sup-analyst-01  
**Data:** 2026-06-15 20:30 CEST  
**Zlecenie:** DISPATCH-SUP-ANALYST-20260615-YT-KNOWLEDGE-AUDIT  
**Priorytet:** WYSOKI — bloker produkcyjny (`metadata_fetch_failed`)

---

## Sekcja 1: Mapa — co było zaimplementowane

| Funkcja | Repo/Plik | Jak działało | Status migracji do VSE |
|---|---|---|---|
| Fetch metadanych YT (title, desc, duration, views, tags) | `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | `yt-dlp --dump-json` | ❌ **NIE ZMIGROWANE** — VSE `core/fetcher.py` nie istnieje w repo |
| Fetch transkryptów VTT (primary) | `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | `youtube-transcript-api` v1.2.4+ (bez klucza API) | ❌ **NIE ZMIGROWANE** |
| Fetch transkryptów VTT (fallback) | `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | `yt-dlp --write-sub` | ❌ **NIE ZMIGROWANE** |
| Listing kanału/playlisty | `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | `yt-dlp --flat-playlist` | ❌ **NIE ZMIGROWANE** |
| Batch processing video | `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | CLI `--batch urls.txt` | ❌ **NIE ZMIGROWANE** |
| Match WP posts ↔ YT videos | `shadow-perihelion/scripts/video-seo/match_prawy_tv.py` | WP REST API + regex YT embed | ⚠️ Częściowo — VSE pipeline.py ma placeholder, brak impl. |
| Generowanie video sitemap | `shadow-perihelion/scripts/video-seo/generate_video_sitemap.py` | XML builder, 213 URL | ❌ BRAK w VSE (osobny skrypt) |
| SEO schema injection do WP | `shadow-perihelion/scripts/video-seo/inject_rest_v5.py` (lokalnie) | WP REST API, VideoObject+Clip+FAQ | ✅ **ZMIGROWANE** — `core/injector.py` (zaimportowany w pipeline.py) |
| YouTube opis/chapters update | `video-seo-engine` CLI `update-yt` | OAuth `videos.update` | ✅ **ZMIGROWANE** — `inject_video()` → `yt_api_key` param |
| viewCount z YouTube Data API v3 | `shadow-perihelion/scripts/video-seo/inject_rest_v5.py` | `YT_API_KEY` env, `videos.list` | ⚠️ OPCJONALNY — `yt_api_key=None` w pipeline.py (graceful degradation) |
| VSE pipeline orchestration | `video-seo-engine/api/services/pipeline.py` | `core.fetcher` + `core.generator` + `core.injector` | ⚠️ ZARYS GOTOWY — ale importuje `core.fetcher` którego BRAK w repo |

---

## Sekcja 2: collector.py — analiza

### CO to jest?

`sonic-void/src/collector.py` (10 667 bajtów) to **Heartbeat Collector ekosystemu Antigravity**.

**NIE ma związku z YouTube ani SEO.** To wewnętrzne narzędzie monitorowania agentów.

### Co robi?

1. Skanuje workspace'y (`sonic-void`, `crimson-void`, `emerald-gravity`, `axial-supernova`, `electric-pinwheel`, `ethereal-eclipse`)
2. Czyta `.agents/heartbeat.json` z każdego workspace'a
3. Porównuje timestamp z progiem `HEARTBEAT_MAX_AGE = 300` sekund
4. Aktualizuje `status.json` w sonic-void z aktualnym statusem agentów (`working` / `idle`)
5. Loguje zdarzenia (`agent_online`, `agent_offline`, `alert_sent`) w FIFO queue (max 50 eventów)
6. Wysyła Discord webhook gdy agent przechodzi na `idle` (opcjonalne)

### Jak uruchamiany?

```bash
python collector.py          # jednorazowe skanowanie
python collector.py --loop   # loop co 10 sekund
```

Lokalizacja: lokalny PC Windows, hardcoded ścieżka do `playground/`.  
**Zero zewnętrznych bibliotek** — tylko stdlib Python.

### Czy to jest missing piece dla YouTube?

**NIE.** `collector.py` to narzędzie operacyjne ekosystemu, nie część pipeline'u video SEO.

---

## Sekcja 3: Rozwiązanie IP ban — historia

### Diagnoza

**Problem:** Oracle Cloud IP jest blokowany przez YouTube gdy używamy `yt-dlp`. Wynik: `metadata_fetch_failed`.

### Jak shadow-perihelion rozwiązało ten problem?

**Odpowiedź: NIE rozwiązało przez obejście IP bana — unikało go przez LOKALNE uruchamianie.**

#### 1. `youtube-transcript-api` (primary, bez IP ban)

```python
# youtube_fetch.py
ytt = YouTubeTranscriptApi()
transcript_list = ytt.list(video_id)
entries = ytt.fetch(video_id, languages=[lang])
```

Biblioteka komunikuje się z YouTube inaczej niż `yt-dlp`. Na cloud VPS status nieweryfikowany.

#### 2. `yt-dlp` (metadata + fallback) — BLOKOWANY NA VPS

```python
result = subprocess.run(["yt-dlp", "--dump-json", "--no-playlist", url], ...)
```

README mówi wprost: `"No YouTube Data API v3 key required"` — świadomy design bez API key, ale yt-dlp jest blokowany przez Oracle Cloud IP.

#### 3. YT OAuth `videos.update` — DZIAŁA NA VPS

HTTP do `googleapis.com`, NIE do `youtube.com`. Nie blokowany — to oficjalny interfejs Google.

Z handoffu `vse-strateg-01` (2026-06-13):
```
YT_API_KEY: AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo
YT OAuth: CLIENT_ID/SECRET w .env, REFRESH_TOKEN odnowiony 2026-06-13
```

#### 4. Kluczowa obserwacja — LOKALNY RUNNER

Z handoffu `vse-strateg-01` (2026-06-13):
> `"Path: C:\Users\tomas2\.gemini\antigravity\playground\video-seo-engine\"`  
> `"run_command: dostępny i działa (nie używamy FILE BRIDGE ani Wetty)"`

**Cały pipeline działał lokalnie na Windows/WSL, nie na VPS.** Brak IP ban bo IP domowe nie jest flagowane.

---

## Sekcja 4: Co należy przemigrować

### Krytyczny brakujący element — `api/core/fetcher.py`

`pipeline.py` importuje:
```python
from core.fetcher import process_video as fetch_video
from core.generator import process_video as generate_schema
from core.injector import inject_video
```

**Weryfikacja repo VSE:** katalog `api/core/` **NIE ISTNIEJE**. Importy `core.fetcher` i `core.generator` padają na `ImportError` przy starcie kontenera.

### Lista plików do migracji

| Źródło | Cel w VSE | Akcja | Priorytet |
|---|---|---|---|
| `shadow-perihelion/scripts/youtube-worker/youtube_fetch.py` | `api/core/fetcher.py` | Zaadaptować — zastąpić `yt-dlp` metadata przez **YouTube Data API v3** | 🔴 KRYTYCZNE |
| `shadow-perihelion/scripts/youtube-worker/requirements.txt` | `requirements.txt` | Dodać `youtube-transcript-api>=0.6.0` | 🔴 KRYTYCZNE |
| — (brak w repo) | `api/core/generator.py` | Prawdopodobnie istnieje lokalnie jako `test_full_seo_v4.py` — zweryfikować | 🔴 KRYTYCZNE |
| — | `api/core/__init__.py` | Nowy pusty plik | 🔴 KRYTYCZNE |
| `shadow-perihelion/scripts/video-seo/match_prawy_tv.py` | `api/core/matcher.py` | Uproszczona wersja — matching YT embed w WP content | 🟡 WAŻNE |

---

## Sekcja 5: YOUTUBE_API_KEY — status i plan

### Stan w credentials registry

```yaml
# sonic-void/.agents/credentials/registry.yaml
youtube_oauth:
  prawypl5-owner:
    type: oauth_refresh_token
    service: YouTube Data API v3
    account: prawypl5@gmail.com
    gcp_project: glass-turbine-388620
    scope: youtube.force-ssl
    location: "~/.impresja/secrets/youtube/prawypl5-oauth.env"
    env_vars: [YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_CHANNEL_ID]
    status: active
```

`YT_API_KEY = AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo` (z handoffu 2026-06-13, GCP: glass-turbine-388620)

### Które endpointy API v3 były używane?

| Endpoint | Użycie | Gdzie |
|---|---|---|
| `videos.list` (Simple API Key) | viewCount → interactionStatistic w VideoObject | `inject_rest_v5.py` v5.3 (CHANGELOG) |
| `videos.update` (OAuth) | Update opisów YT z rozdziałami | VSE CLI `update-yt` |
| `playlistItems.list` (OAuth) | Listing filmów prywatnych/scheduled | Badane w DISPATCH-VSE-ANALYST-01-20260519-YT-OAUTH |

### Implementacja fetch przez API v3 (VPS-compatible)

```python
import httpx

def fetch_metadata_api_v3(video_id: str, api_key: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"id": video_id, "key": api_key, "part": "snippet,contentDetails,statistics"}
    resp = httpx.get(url, params=params, timeout=15)
    item = resp.json()["items"][0]
    snippet = item["snippet"]
    return {
        "video_id": video_id,
        "title": snippet["title"],
        "description": snippet["description"],
        "published_at": snippet["publishedAt"],
        "duration_seconds": parse_iso_duration(item["contentDetails"]["duration"]),
        "view_count": int(item["statistics"].get("viewCount", 0)),
        "like_count": int(item["statistics"].get("likeCount", 0)),
        "tags": snippet.get("tags", []),
        "thumbnail_url": snippet["thumbnails"].get("maxres", snippet["thumbnails"]["high"])["url"],
    }
```

**googleapis.com nie jest blokowany przez Oracle Cloud** — to oficjalny API endpoint.

---

## Sekcja 6: Rekomendacje implementacyjne dla `vse-dev`

### Krok 1 — Stwórz `api/core/` z fetcher.py

```python
# api/core/fetcher.py — co skopiować 1:1 z youtube_fetch.py
def fetch_transcript_api(video_id, lang="pl") -> tuple  # linie 75-120
def iso_duration(seconds) -> str
def extract_video_id(url_or_id) -> str
def format_published_date(raw) -> str

# Co zastąpić:
# fetch_metadata_ytdlp() → fetch_metadata_api_v3() (używa YT_API_KEY)

# Co dodać:
# process_video(video_id, output_dir, lang) → kompatybilne z pipeline.py
```

### Krok 2 — Zweryfikować `api/core/generator.py`

Jeśli nie ma w repo — zapytać Usera o `test_full_seo_v4.py` z lokalnego playgrounda.

### Krok 3 — Dodać `YT_API_KEY` do VPS .env

```bash
# /home/ubuntu/video-seo-engine/.env
YT_API_KEY=AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo
```

### Krok 4 — Fallback jeśli youtube-transcript-api też blokowana

Jeśli transkrypty też padają na VPS: runner przez `stellar-relay target=local-pc` lub cookies.txt pipeline.

### Co pominąć

- CLI część youtube_fetch.py (argparse, channel/playlist listing)
- `generate_video_sitemap.py` (osobny one-off tool, nie SaaS)
- `match_prawy_tv.py` hardcoded `D:\Biblioteki` paths (zastąpić env vars)

---

## Podsumowanie — 3 zdania

1. **`collector.py` = NIE YouTube** — to heartbeat monitor ekosystemu, zero związku z blokerem.
2. **Bloker = brakujący `api/core/fetcher.py`** — pipeline.py importuje plik który nie istnieje w repo; fix: zaimplementować przez YouTube Data API v3 zamiast `yt-dlp` (klucz: `AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo`, projekt: `glass-turbine-388620`).
3. **Shadow-perihelion działało LOKALNIE** — nigdy nie testowane na cloud VPS; IP ban był nieznany bo nie było VPS deployment tych skryptów.

---

*sup-analyst-01 | sonic-void | 2026-06-15 20:35 CEST — raport kompletny*
