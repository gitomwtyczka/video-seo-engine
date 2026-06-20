# DISPATCH — D11: Video Screenshots + ImageObject Schema

**Callsign:** vse-dev-26  
**Dispatch:** DISPATCH-VSE-DEV-26-20260621-VIDEO-SCREENSHOTS-D11  
**Projekt:** video-seo-engine  
**Priorytet:** 🔴 KRYTYCZNY (blokuje 80+ RankMath + Google Discover)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  

---

## CEL

Dodanie 1-2 screenshotów z wideo do generowanego artykułu z opisami alt i schema ImageObject. Obrazki są uploadowane do WP Media Library i wstawiane w treść.

## PROBLEM

Artykuły generowane przez VSE mają ZERO obrazków poza embedem wideo. To kosztuje:
- RankMath: -5-10 pkt (brak frazy kluczowej w alt atrybutów obrazków)
- Google Discover: artykuły bez obrazków ≥1200px mają 2-3x niższy CTR
- Google Images: zero ruchu z tego kanału

## WYMAGANIA wg TYPU PUBLIKACJI

| Typ publikacji | Wymagane screeny |
|---|---|
| `watching_page` | 1 screenshot (opcjonalny, ale zalecany) |
| `full_analysis` | **2 screeny obowiązkowo** |
| `discover` | **2 screeny obowiązkowo** |

## SPECYFIKACJA IMPLEMENTACJI

### FAZA A: Pobranie thumbnailów (najprostsza, pewna metoda)

**Plik: `core/fetcher.py`** — nowa funkcja

```python
def fetch_video_thumbnails(video_id: str, output_dir: str) -> list[dict]:
    """
    Pobiera thumbnails z YouTube dla danego wideo.
    Zwraca listę dictów: [{"path": "/tmp/xxx.jpg", "width": 1280, "height": 720, "source": "youtube_maxres"}]
    """
```

Kolejność prób (fallback chain):
1. `https://img.youtube.com/vi/{video_id}/maxresdefault.jpg` (1280x720) — preferowany
2. `https://img.youtube.com/vi/{video_id}/sddefault.jpg` (640x480) — fallback
3. `https://img.youtube.com/vi/{video_id}/hqdefault.jpg` (480x360) — last resort

Sprawdź HTTP status — nie każde wideo ma maxresdefault. Pobierz pierwszy dostępny.
Zapisz do `output_dir` jako `{video_id}_thumb_1.jpg`.

Dla **drugiego** screena (jeśli typ wymaga 2):
- Użyj innego momentu: `https://img.youtube.com/vi/{video_id}/1.jpg` (120x90 — minimalny)
- LUB: `https://img.youtube.com/vi/{video_id}/2.jpg`
- LUB: `https://img.youtube.com/vi/{video_id}/3.jpg`

> ⚠️ YouTube ma 4 auto-generated thumbnails: `0.jpg` (= `hqdefault`), `1.jpg`, `2.jpg`, `3.jpg`.
> Są małe (120x90), ale działają jako placeholder.
> Lepsze rozwiązanie (FAZA B, backlog): ffmpeg frame extraction z yt-dlp stream.

### FAZA B: LLM generuje opisy do screenshotów

**Plik: `core/generator.py`** — zmiana w prompcie

Dodaj nowy punkt w sekcji „CO WYGENEROWAĆ”:

```
15. (lub 16, po external_links) **image_descriptions** — lista 2 opisów do screenshotów z wideo.
    Każdy dict: {"alt_text": "...", "caption": "...", "context": "..."}
    ZASADY:
    a) alt_text: max 125 zn, SEO-friendly, MUSI zawierać główną frazę z focus_keyphrases[0]
    b) caption: 1 zdanie opisujące co widać na screenie (pod obrazkiem)
    c) context: w którym miejscu article_body wstawić obrazek ("po akapicie 1", "po H2")
    d) Opisy powinny być różne — pierwszy ogólny (główna scena), drugi szczegółowy (moment z rozmowy)
```

W response JSON template dodaj:
```json
"image_descriptions": [{"alt_text": "...", "caption": "...", "context": "..."}]
```

### FAZA C: Upload do WP Media Library + wstawienie w artykuł

**Plik: `core/injector.py`** — nowa funkcja + modyfikacja `inject_video()`

```python
def _upload_image_to_wp(
    image_path: str,
    alt_text: str,
    caption: str,
    wp_base_url: str,
    wp_user: str,
    wp_app_password: str,
) -> dict:
    """
    Upload obrazka do WP Media Library przez REST API.
    POST /wp/v2/media z multipart/form-data.
    Ustawia alt_text i caption.
    Zwraca: {"id": 12345, "url": "https://portal.pl/wp-content/uploads/...jpg", "width": 1280, "height": 720}
    """
```

W `inject_video()` po zbudowaniu content HTML:
1. Sprawdź czy `seo_data` zawiera `image_descriptions` i `image_paths`
2. Uploaduj każdy obrazek do WP Media
3. Wstaw `<figure><img src="..." alt="..." width="..." height="..."/><figcaption>...</figcaption></figure>` w article_body wg `context` z image_descriptions
4. Dodaj ImageObject do JSON-LD schema

### FAZA D: Pipeline orchestration

**Plik: `api/services/pipeline.py`** — nowy krok między fetch a generate

W `run_generate()` po Step 1 (fetch metadata):
```python
# Step 1b: Fetch video thumbnails for screenshot enrichment
from core.fetcher import fetch_video_thumbnails
num_screenshots = 2 if publication_type in ("full_analysis", "discover") else 1
thumbnails = await asyncio.to_thread(
    fetch_video_thumbnails, video_id, tmp_dir
)
# Pass thumbnail paths to result for injector
```

W `run_generate()` result dict dodaj:
```python
result["image_paths"] = [t["path"] for t in thumbnails[:num_screenshots]]
result["image_meta"] = thumbnails[:num_screenshots]
```

W `run_inject()` i `_create_wp_post()` przekaż image_paths do injector.

### FAZA E: Schema ImageObject

W injector, przy budowaniu JSON-LD schema, dodaj zagnieżdżony `image` w `VideoObject`:

```json
{
  "@type": "VideoObject",
  "image": [
    {
      "@type": "ImageObject",
      "url": "https://portal.pl/wp-content/uploads/video-screenshot-1.jpg",
      "width": 1280,
      "height": 720,
      "caption": "Opis sceny..."
    }
  ]
}
```

## KLUCZOWE ZASADY

1. **Graceful degradation** — jeśli thumbnail nie do pobrania, pipeline działa dalej bez obrazków
2. **Nie blokuj pipeline** — błąd uploadu do WP = warning w logu, artykuł publikowany bez obrazków
3. **Backward compatible** — brak `image_descriptions` w starych wynikach = brak obrazków (OK)
4. **WP Media upload wymaga auth** — użyj tego samego `wp_user` + `wp_app_password` co injector

## WERYFIKACJA

1. `POST /v1/generate` z video — response zawiera `image_descriptions` (2 itemy) i `image_paths`
2. `POST /v1/inject` — obrazki uploadowane do WP Media Library
3. Artykuł w WP zawiera `<figure>` z `<img>` i `<figcaption>`
4. alt text zawiera frazę kluczową
5. JSON-LD schema zawiera `image` z `ImageObject`
6. Test z `publication_type=watching_page` — 1 screenshot
7. Test z `publication_type=full_analysis` — 2 screenshoty

## DEPLOY

Po commitach do `main`:
```powershell
$script = @'
cd /home/ubuntu/video-seo-engine
git pull origin main
docker compose -f docker-compose.vse.yml build vse-api
docker compose -f docker-compose.vse.yml up -d vse-api
sleep 3
curl -s http://localhost:8085/health
'@
$script | Set-Content -Path "$env:TEMP\deploy_d11.sh" -Encoding UTF8 -NoNewline
scp -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no "$env:TEMP\deploy_d11.sh" ubuntu@147.224.162.100:/tmp/deploy_d11.sh
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 'bash /tmp/deploy_d11.sh'
```

## SEKWENCJA

> ⚠️ D11 zależy od D10 (external_links w prompcie). Czekaj aż D10 będzie DONE w inbox, albo rebase na commit D10.

## DUAL-WRITE RAPORT

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/`
2. Raport do `sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-26_D11-video-screenshots.md`
3. Heartbeat status: `done`

---

*[Supervisor 01 | sonic-void 21.06.2026 00:44] — dispatch D11*