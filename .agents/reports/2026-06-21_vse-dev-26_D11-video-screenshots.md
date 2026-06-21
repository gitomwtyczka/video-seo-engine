# Raport D11: Video Screenshots + ImageObject Schema

**Callsign:** vse-dev-26  
**Data:** 2026-06-21  
**Status:** ✅ KOMPLETNY  

---

## CO zrobiono

Zaimplementowano pełny pipeline screenshotów z wideo:
- Pobieranie thumbnailów z YouTube (maxresdefault + storyboard frames)
- Opisy obrazów z SAAS Vision API (GPT-4o, primary) + LLM Claude fallback
- Upload do WP Media Library z pełnymi metadanymi SEO
- ImageObject w JSON-LD schema
- `<figure>` bloki w artykule

## PO CO

Artykuły z obrazkami rankują wyżej w Google i Google Discover.
RankMath wymaga ImageObject do 80+ score.
Bez obrazków artykuł tracił punkty w każdym audycie.

## JAK (commity)

| Commit | Plik | Opis |
|---|---|---|
| `3bcccb1` | `core/fetcher.py` | `fetch_video_thumbnails()` — pobieranie maxres + storyboard frames |
| `83300e2` | `core/generator.py` | Punkt 16 w LLM prompcie: `image_descriptions` (fallback) |
| `4fc14a7` | `api/services/pipeline.py` | `_describe_image_via_saas()` + orchestration w `run_generate()` |
| `d105cfe` | `core/injector.py` | `_upload_image_to_wp()` + ImageObject schema + `<figure>` blocks |

## Architektura (Opcja C — Hybrid)

```
YouTube thumbnail
       │
       ├──→ SAAS Vision API (POST /api/external/describe-image)
       │          │
       │          ├── alt_text (SEO z keyword, vision-based)
       │          ├── title, caption, description, filename
       │
       ├──→ [FALLBACK] LLM Claude — ślepe opisy z kontekstu artykułu
       │
       └──→ Upload do WP Media Library + wstawienie <figure> w article_body
            + ImageObject w JSON-LD schema
```

## Graceful degradation

1. SAAS Vision API down → LLM fallback descriptions
2. LLM nie zwrócił image_descriptions → generic fallback (keyphrase + "kadr z materiału")
3. Thumbnail download fail → artykuł bez obrazów (warning w logu)
4. WP upload fail → artykuł bez obrazów (pipeline continues)

## Deploy

✅ Deployed via SSH, health check OK: `{"status":"ok","version":"2.0.0"}`

## Wymagania per typ publikacji

| Typ | Wymagane screeny |
|---|---|
| `watching_page` | 1 screenshot |
| `full_analysis` | 2 screeny |
| `discover` | 2 screeny |

---

*[vse-dev-26 | video-seo-engine 2026-06-21 11:25]*
