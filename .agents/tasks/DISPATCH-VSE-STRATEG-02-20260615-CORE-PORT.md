# DISPATCH — vse-strateg-02
## Port `api/core/fetcher.py` z shadow-perihelion + uruchomienie pipeline

**Od:** Supervisor 01 (na podstawie audytu sup-analyst-01)  
**Do:** `vse-strateg-02`  
**Data:** 2026-06-15  
**Priorytet:** 🔴 BLOKER PRODUKCYJNY  
**Repo:** `gitomwtyczka/video-seo-engine`, branch: `main`

---

## ⚠️ KONTEKST — czego NIE robić

Przeczytaj ten blok zanim cokolwiek zaczniesz.

**Poprzedni strateg (vse-strateg-01) zamknął sesję z błędnym wnioskiem:**  
> `"YouTube Data API v3 NIE istniała w żadnym repo"`

**To jest NIEPRAWDA.** Audyt sup-analyst-01 (2026-06-15) udowodnił:
- API v3 była używana w `inject_rest_v5.py` v5.3 (CHANGELOG: `YT_API_KEY` env var → `viewCount`)
- `YT_API_KEY` jest w credentials registry: `AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo` (GCP: `glass-turbine-388620`)
- OAuth (CLIENT_ID/SECRET/REFRESH_TOKEN) jest aktywny w `~/.impresja/secrets/youtube/prawypl5-oauth.env`
- `youtube-transcript-api` była używana lokalnie i DZIAŁAŁA

**Nie buduj od zera. Portuj istniejący kod.**

---

## TWOJE ZADANIE — PORT, nie build

### Krok 0 — Przeczytaj все istniejące skrypty źródłowe

Przed napisaniem JEDNEJ linii kodu: przeczytaj dokładnie:

```
GitHub MCP:
  repo: gitomwtyczka/shadow-perihelion, branch: main
  path: scripts/youtube-worker/youtube_fetch.py   [⇐ GŁÓWNE źrÓDŁO]
  path: scripts/youtube-worker/requirements.txt
  path: scripts/youtube-worker/README.md
  path: scripts/video-seo/CHANGELOG.md
```

`youtube_fetch.py` to 16 KB działającego kodu. To jest **źródło prawdy** — port z niego, nie wymysłaj.

### Krok 1 — Zrozum co importuje pipeline.py

Przeczytaj:
```
repo: gitomwtyczka/video-seo-engine, branch: main
path: api/services/pipeline.py
```

`pipeline.py` importuje:
```python
from core.fetcher import process_video as fetch_video
from core.generator import process_video as generate_schema
from core.injector import inject_video
```

**BRAK `api/core/` w repo.** Musisz stworzyć ten katalog.

### Krok 2 — Port `api/core/fetcher.py`

**CO skopiować 1:1** z `youtube_fetch.py`:
- `extract_video_id(url_or_id)` — regex parser URL
- `iso_duration(seconds)` — konwerter sekund → ISO 8601
- `format_published_date(raw)` — YYYYMMDD → ISO
- `fetch_transcript_api(video_id, lang)` — cała funkcja z `youtube-transcript-api`
- `fetch_transcript_ytdlp(video_id, lang, output_dir)` — jako ostateczny fallback (może padać na VPS)
- `log(msg, quiet)` — helper

**CO zmienić (jeden punkt !):**
- `fetch_metadata_ytdlp()` → `fetch_metadata_api_v3()` używając `YOUTUBE_API_KEY` env var

```python
def fetch_metadata_api_v3(video_id: str, api_key: str) -> dict:
    """Fetch metadata via YouTube Data API v3. Nie blokuje na Oracle Cloud."""
    import urllib.request, json
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?id={video_id}&key={api_key}"
        f"&part=snippet,contentDetails,statistics"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        if not data.get("items"):
            return {}
        item = data["items"][0]
        snippet = item["snippet"]
        duration_iso = item["contentDetails"]["duration"]  # już ISO 8601
        # zamień PT#H#M#S na sekundy (użyj parsera z youtube_fetch.py lub napisz)
        thumbnails = snippet.get("thumbnails", {})
        thumb = (thumbnails.get("maxres") or thumbnails.get("standard") 
                 or thumbnails.get("high", {})).get("url", "")
        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt", ""),
            "duration_seconds": parse_iso8601_duration(duration_iso),
            "duration_iso": duration_iso,
            "view_count": int(item["statistics"].get("viewCount", 0)),
            "like_count": int(item["statistics"].get("likeCount", 0)),
            "comment_count": int(item["statistics"].get("commentCount", 0)),
            "thumbnail_url": thumb,
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "tags": snippet.get("tags", []),
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        }
    except Exception as e:
        log(f"  API v3 error: {e}")
        return {}
```

Dodaj `parse_iso8601_duration(duration_str) -> int` (sekund) — standard `re` lub `isodate`.

**`process_video()` — główna funkcja wymagana przez pipeline.py:**

```python
def process_video(video_id: str, output_dir: str, lang: str = "pl") -> dict:
    """Fetch metadata + transcript for one video. Returns metadata dict."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    
    # 1. Metadata
    if api_key:
        meta = fetch_metadata_api_v3(video_id, api_key)
    else:
        # fallback: yt-dlp (tylko lokalne, na VPS może padać)
        meta = fetch_metadata_ytdlp(video_id)
    
    if not meta:
        return {"video_id": video_id, "error": "metadata_fetch_failed"}
    
    # 2. Transcript: primary = youtube-transcript-api, fallback = yt-dlp
    vtt_text, lang_used = fetch_transcript_api(video_id, lang)
    if not vtt_text:
        vtt_text, lang_used = fetch_transcript_ytdlp(video_id, lang, output_dir)
    
    # 3. Save VTT
    if vtt_text:
        vtt_path = os.path.join(output_dir, f"{video_id}.{lang}.vtt")
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(vtt_text)
        meta["vtt_path"] = vtt_path
        meta["vtt_language"] = lang_used or lang
    else:
        meta["vtt_path"] = None
        meta["vtt_language"] = None
    
    meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"
    return meta
```

### Krok 3 — Stwórz `api/core/__init__.py`

Pusty plik lub minimalny:
```python
# api/core/__init__.py
```

### Krok 4 — Zaktualizuj `requirements.txt`

Dodaj jeśli brakuje:
```
youtube-transcript-api>=0.6.0
```

Sprawdz aktualne requirements.txt w repo przed zmianą.

### Krok 5 — Deploy i test

Po push do GitHub:
```bash
# przez FILE BRIDGE (target: oracle-crimson)
recipe: deploy-backend   # lub docker compose build vse-api && up -d
```

Następnie test:
```bash
curl -X POST https://vse.impresjapr.pl/v1/process \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtube.com/watch?v=XfGpTCMdvCE", "wp_post_id": 121157}'
```

Oczekiwany wynik: `{"status": "ok", "schema_generated": true}` zamiast `metadata_fetch_failed`.

---

## CO POMINĄĆ

- `cli/` część `youtube_fetch.py` (argparse, `main()`) — niepotrzebna w FastAPI
- Listing kanału/playlisty — nie używane w VSE SaaS
- `generate_video_sitemap.py` — osobny one-off tool, nie część VSE
- Hardcoded ścieżki Windows (`D:\Biblioteki\`) — wszystko przez env vars

---

## CREDENTIALS na VPS

```
YOUTUBE_API_KEY=AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo
```

To jest Simple API Key (nie OAuth) — używany do odczytu metadanych publicznych filmów.  
GCP project: `glass-turbine-388620` (nie GalerieGoogle — inny projekt!)  
Dodaj do `/home/ubuntu/video-seo-engine/.env` przez FILE BRIDGE.

---

## PYTANIE OTWARTE — generator.py

Na VPS nie ma `api/core/generator.py`. Przed deployem sprawdz czy jest w repo:  
`repo: gitomwtyczka/video-seo-engine, path: api/core/`

Jeśli nie ma: STOP, zaraportuj do Supervisora. Nie implementuj bez wiedzy co miał robić generator — to inna sesja.

---

## RAPORTOWANIE

Po zakończeniu:
1. `video-seo-engine/.agents/reports/2026-06-15_vse-strateg-02_core-port.md`
2. `sonic-void/.agents/reports/inbox/2026-06-15_vse-strateg-02_core-port.md`

---

*Supervisor 01 | sonic-void | 2026-06-15 20:42 — na podstawie audytu sup-analyst-01*
