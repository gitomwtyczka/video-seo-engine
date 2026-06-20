# DISPATCH — D11: Video Screenshots + ImageObject Schema (UPDATED per A7)

**Callsign:** vse-dev-26  
**Dispatch:** DISPATCH-VSE-DEV-26-20260621-VIDEO-SCREENSHOTS-D11  
**Projekt:** video-seo-engine  
**Priorytet:** 🔴 KRYTYCZNY (blokuje 80+ RankMath + Google Discover)  
**Data:** 2026-06-21 (updated per A7 analyst report)  
**Wystawiony przez:** Supervisor 01  
**Zależności:** D10 (commit `feb2ed4`), D11-pre (SAAS endpoint w crimson-void)  

---

## CEL

Dodanie 1-2 screenshotów z wideo do generowanego artykułu z:
- Opisami z SAAS Vision API (GPT-4o, widzi obraz) — primary
- LLM Claude fallback jeśli SAAS niedostępny
- Upload do WP Media Library
- Schema ImageObject w JSON-LD

## ARCHITEKTURA (Opcja C — Hybrid, per A7)

```
YouTube thumbnail
       │
       ├──→ SAAS Vision API (POST /api/external/describe-image)
       │          │
       │          ├── alt_text (SEO z keyword, vision-based)
       │          ├── title
       │          ├── caption
       │          ├── description
       │          └── filename
       │
       ├──→ [FALLBACK] LLM Claude — ślepe opisy z kontekstu artykułu
       │
       └──→ Upload do WP Media Library + wstawienie w article_body
```

## WYMAGANIA wg TYPU PUBLIKACJI

| Typ publikacji | Wymagane screeny |
|---|---|
| `watching_page` | 1 screenshot (opcjonalny, ale zalecany) |
| `full_analysis` | **2 screeny obowiązkowo** |
| `discover` | **2 screeny obowiązkowo** |

## SPECYFIKACJA IMPLEMENTACJI

### FAZA A: Pobranie thumbnailów z YouTube

**Plik: `core/fetcher.py`** — nowa funkcja

```python
def fetch_video_thumbnails(video_id: str, output_dir: str, count: int = 2) -> list[dict]:
    """
    Pobiera thumbnails z YouTube.
    Fallback chain: maxresdefault.jpg → sddefault.jpg → hqdefault.jpg
    Dla drugiego screena: /1.jpg, /2.jpg, /3.jpg
    Zwraca: [{"path": "...", "width": 1280, "height": 720, "source": "youtube_maxres"}]
    """
```

### FAZA B: Opisy obrazów przez SAAS Vision API (PRIMARY)

**Plik: `api/services/pipeline.py`** — nowa funkcja

```python
async def _describe_image_via_saas(
    image_url: str,
    article_title: str,
    focus_keywords: list[str],
    site_brand: str = "",
) -> dict | None:
    """
    Wywołuje SAAS POST /api/external/describe-image.
    Auth: Bearer EXTERNAL_API_TOKEN (z .env, ten sam co SAAS enrichment).
    Zwraca dict z alt_text, title, caption, description, filename.
    None jeśli SAAS niedostępny → fallback do LLM.
    """
    saas_url = os.environ.get("SAAS_API_URL", "").strip().rstrip("/")
    token = os.environ.get("EXTERNAL_API_TOKEN", "").strip()
    if not saas_url or not token:
        return None
    
    endpoint = f"{saas_url}/api/external/describe-image"
    payload = {
        "image_url": image_url,
        "context": {
            "article_title": article_title,
            "focus_keywords": focus_keywords,
            "site_brand": site_brand,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("descriptions")
    except Exception as exc:
        logger.warning("SAAS image describe failed: %s — using LLM fallback", exc)
    return None
```

### FAZA B-fallback: LLM opisy (gdy SAAS niedostępny)

**Plik: `core/generator.py`** — dodatkowy punkt w prompcie

Dodaj punkt 16 w CO WYGENEROWAĆ:
```
16. **image_descriptions** — lista 2 opisów do screenshotów z wideo.
    Każdy dict: {"alt_text": "...", "caption": "...", "context": "..."}
    ZASADY:
    a) alt_text: max 125 zn, MUSI zawierać główną frazę z focus_keyphrases[0]
    b) caption: 1 zdanie opisujące scenę
    c) context: gdzie wstawić w article_body ("po akapicie 1", "po H2")
```

> ⚠️ Te opisy są FALLBACK — używane TYLKO gdy SAAS Vision API niedostępny.
> Gdy SAAS działa, pipeline używa opisów z SAAS (vision-based, lepsze).

### FAZA C: Upload do WP Media Library

**Plik: `core/injector.py`** — nowa funkcja

```python
def _upload_image_to_wp(
    image_path: str,
    descriptions: dict,  # {alt_text, title, caption, description, filename}
    wp_base_url: str,
    wp_user: str,
    wp_app_password: str,
) -> dict | None:
    """
    POST /wp/v2/media z multipart/form-data.
    Ustawia alt_text, title, caption, description z SAAS/LLM.
    Zwraca: {"id": 12345, "url": "https://...jpg", "width": 1280, "height": 720}
    """
```

W `inject_video()` po zbudowaniu content HTML:
1. Jeśli `seo_data` zawiera `image_paths` + opisy → upload + wstaw `<figure>` w article_body
2. Dodaj ImageObject do JSON-LD schema

### FAZA D: Pipeline orchestration

**Plik: `api/services/pipeline.py`** — nowe kroki w `run_generate()`

Po Step 1 (fetch metadata):
```python
# Step 1b: Fetch video thumbnails
num_screenshots = 2 if publication_type in ("full_analysis", "discover") else 1
thumbnails = await asyncio.to_thread(fetch_video_thumbnails, video_id, tmp_dir, num_screenshots)

# Step 1c: Get image descriptions from SAAS Vision API (primary)
image_descriptions = []
for thumb in thumbnails:
    yt_thumb_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    desc = await _describe_image_via_saas(yt_thumb_url, post_title, keyphrases, site_brand or "")
    if desc:
        image_descriptions.append(desc)
    # Fallback: LLM descriptions from generator output (Faza B-fallback)
```

### FAZA E: Schema ImageObject

W injector JSON-LD, dodaj `image` w `VideoObject`:
```json
"image": [{"@type": "ImageObject", "url": "...", "width": 1280, "height": 720, "caption": "..."}]
```

## KLUCZOWE ZASADY

1. **SAAS primary, LLM fallback** — SAAS widzi obraz (GPT-4o Vision), LLM nie
2. **Graceful degradation** — błąd na dowolnym etapie = artykuł bez obrazków (warning w logu)
3. **Rebase na D10** (commit `feb2ed4`) — generator.py ma już external_links
4. **Czekaj na D11-pre** — SAAS endpoint musi istnieć zanim SAAS-primary zadziała

## WERYFIKACJA

1. `POST /v1/generate` → response zawiera `image_descriptions` + `image_paths`
2. SAAS describe-image wywołane (check logs)
3. `POST /v1/inject` → obrazki w WP Media Library z poprawnymi opisami
4. Artykuł w WP ma `<figure>` + `<img>` z alt z keyword
5. JSON-LD schema ma `image` z `ImageObject`
6. Test SAAS down → LLM fallback działa

## DEPLOY

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

## DUAL-WRITE RAPORT

1. `video-seo-engine/.agents/reports/`
2. `sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-26_D11-video-screenshots.md`
3. Heartbeat: `done`

---

*[Supervisor 01 | sonic-void 21.06.2026 00:58] — dispatch D11 updated per A7*