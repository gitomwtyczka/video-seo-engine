# Video SEO Pipeline — Architecture & Knowledge Base

**Wersja:** v5.3 (stan: 2026-05-13)
**Źródło:** shadow-perihelion (sesje 2026-05-07 do 2026-05-12)
**Autor:** vse-architect-01
**Zaktualizowano:** DISPATCH-VSE-ARCHITECT-02 (2026-05-13) — roadmap Faz 1-7

---

## 🏗️ Architektura Pipeline v5.3

```
YouTube Channel / Portal
        │
        ▼
[core/fetcher.py]
  ├── youtube-transcript-api v1.2.4+ (instance API)
  │     ytt = YouTubeTranscriptApi()
  │     entries = ytt.fetch(video_id, languages=['pl'])
  ├── yt-dlp (fallback + metadata)
  │     yt-dlp --dump-json <url>
  └── Output: <video_id>.json + <video_id>.pl.vtt
        │
        ▼
[core/matcher.py]
  ├── WordPress REST API: GET /wp-json/wp/v2/posts?categories=<ID>
  ├── regex: youtube.com/(?:watch\?v=|embed/)([a-zA-Z0-9_-]{11})
  └── Output: prawy_tv_matches.json [{wp_id, youtube_id, slug, post_date}]
        │
        ▼
[core/generator.py]  ✅ ZMIGROWANY (DISPATCH-02, 2026-05-13)
  ├── parse_vtt_full() — parser VTT z markerami [MM:SS] co 30s
  ├── find_anchor_in_vtt() — fuzzy match anchor_text → timestamp
  ├── generate_seo_v4() — Gemini 2.5 Flash call z promptem v5.3
  ├── process_video() — full pipeline: VTT → Gemini → resolved chapters → JSON
  └── Output: seo_results/<video_id>.json
        │
        ▼
[core/injector.py]   ✅ ZMIGROWANY (DISPATCH-02, 2026-05-13)
  ├── get_post_date() — fetch uploadDate z WP REST API
  ├── get_youtube_view_count() — YouTube Data API v3 (YT_API_KEY)
  ├── set_youtube_thumbnail() — download + upload do WP media library
  ├── build_schema_jsonld() — VideoObject + Clip[] + FAQPage + Quotation
  ├── build_post_content() — WP blocks + seekTo JS
  ├── update_post() — REST API PATCH z dry-run support
  └── inject_video() — full pipeline: thumbnail + content injection
        │
        ▼
[core/sitemap.py]
  ├── Load matches.json + durations from seo_results/
  ├── Generate video-sitemap.xml (Google Video Sitemap 1.1)
  └── Stats: total, with_duration, estimated, no_duration
```

---

## 📋 Schema Types — Decyzje Architektoniczne

### ✅ AKTYWNE (v5.3)

#### VideoObject (OBOWIĄZKOWY)
Główny schema dla każdego posta z filmem.

```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "Tytuł artykułu",
  "description": "SEO-optimized description z kluczowymi frazami",
  "thumbnailUrl": "https://i.ytimg.com/vi/{yt_id}/maxresdefault.jpg",
  "uploadDate": "2026-01-15T10:00:00+01:00",
  "duration": "PT1H23M45S",
  "contentUrl": "https://www.youtube.com/watch?v={yt_id}",
  "embedUrl": "https://www.youtube.com/embed/{yt_id}",
  "interactionStatistic": {
    "@type": "InteractionCounter",
    "interactionType": "https://schema.org/WatchAction",
    "userInteractionCount": 12345
  }
}
```

**Krytyczne wymagania Google 2026:**
- `duration`: MUSI być ISO 8601 (PT#H#M#S) — nie sekundy
- `uploadDate`: MUSI mieć timezone — nie samo YYYY-MM-DD
- `thumbnailUrl`: maxresdefault.jpg (1280x720) — nie hqdefault
- `embedUrl`: MUSI być obecny (obok `contentUrl`)

#### Clip (rozdziały)
Generowane przez Gemini z transkryptu VTT. Każdy rozdział to osobny `Clip`.

```json
{
  "@type": "Clip",
  "name": "Nazwa rozdziału",
  "startOffset": 120,
  "endOffset": 360,
  "url": "https://www.youtube.com/watch?v={yt_id}&t=120"
}
```

**UWAGA:** `SeekToAction` dodajemy dla completeness, ale Google **nie renderuje** dla treści PL.
Zachowujemy w schemacie — nie psuje, nie pomaga.

#### FAQPage
Generowany przez Gemini z transkryptu — 3-5 pytań i odpowiedzi.
Zwiększa CTR i eligibility do rich snippets.

#### interactionStatistic (viewCount)
Pobierany przez fetcher.py z yt-dlp (`view_count`).
Aktualizowany przy każdym re-processingu.

---

### ❌ DECYZJA: NIE UŻYWAMY

#### Quotation
- Google **nie renderuje** Quotation w rich snippets
- Nie wpływa na ranking
- **Decyzja architektoniczna:** nie dodawać nowych; jeśli istnieje w poście — zachować

#### BroadcastEvent
- Oddzielny pipeline: `broadcast.py` w shadow-perihelion
- Dotyczy LIVE streamów, nie archiwum
- Wymaga Google Indexing API (osobne credentials)

#### LearningResource, NewsArticle
- Nie dotyczy tego contentu
- RankMath auto-generuje NewsArticle — NIE ingerujemy

---

## 🗺️ Roadmap Faz 1-7

### Faza 1 — Core Pipeline (PRAWY.PL) ✅ KOMPLETNA
- [x] VideoObject schema v5.3 — duration, timezone, viewCount
- [x] Chapters (Clip) z fuzzy matching VTT
- [x] FAQPage z transkryptu
- [x] Batch processing 213+ postów (shadow-perihelion aktywny)
- [x] `core/generator.py` — zmigrowany z test_full_seo_v4.py (DISPATCH-02)
- [x] `core/injector.py` — zmigrowany z inject_rest_v5.py (DISPATCH-02)
- [x] `cli/main.py` — generate + inject + batch support (DISPATCH-02)

### Faza 2 — Channel Monitor (planowane)
- `core/monitor.py` — YouTube Channel Monitor
- Automatyczne wykrywanie nowych filmów (polling co 1h)
- Auto-tworzenie draft postów w WP z embeddednym video
- Triggerowanie pipeline v5.3 na nowych filmach

### Faza 3 — Multi-Portal (planowane)
- Portal Scanner dla Kurier365, BiznesCiti
- Unified `config/portals.yaml` — każdy portal: WP_URL, YT_CHANNEL_ID, CATEGORY_ID
- Adapter pattern: jeden pipeline, wiele portali

### Faza 4 — Video Sitemap Auto-Regen (planowane)
- `core/sitemap.py` już istnieje — do dopracowania
- Auto-regeneracja: `save_post` WordPress hook (via WP plugin)
- Cross-category discovery (nie tylko Prawy TV)

### Faza 5 — PressAI SaaS Module (planowane)
- REST API wrapper nad pipeline
- Endpoint: `POST /api/v1/process-video` → async job
- Wynik do crimson-void jako moduł PressAI

### Faza 6 — WordPress Plugin (planowane)
- Dystrybucja jako self-contained WP plugin
- GUI w WP admin: kolejka filmów, status injekcji, video sitemap stats

### Faza 7 — YouTube Description Sync (planowane, BLOKER)
- YouTube Data API v3 OAuth2 (Manager scope)
- GCP project: `antigravity-mcp-keys` (już istnieje)
- Opis YT aktualizowany po wygenerowaniu SEO (chapters jako timestamps)
- **BLOKER:** wymaga OAuth2 setup — osobny dispatch

---

## 📊 Status Operacyjny (2026-05-13)

| Metryka | Wartość |
|---------|---------|
| Pipeline version | v5.3 |
| Posty live (prawy.pl) | 6 |
| Kolejka (archiwum) | 156 pozostałych |
| Batch status | shadow-perihelion aktywny |
| Schema score (Google) | 8/10 |
| Konkurencja TVP Info | 3/10 |
| Konkurencja wPolityce | 2/10 |
| core/generator.py | ✅ zmigrowany |
| core/injector.py | ✅ zmigrowany |
| cli/main.py | ✅ rozszerzony |

---

## 🔗 Linki do Raportów (shadow-perihelion)

- `.agents/reports/` — raporty z sesji implementacyjnych
- `scripts/video-seo/` — oryginalne skrypty (generator, injector)
- `scripts/youtube-worker/` — youtube_fetch.py (zmigrowany do fetcher.py)

---

## ⚠️ Znane Gotchas

### youtube-transcript-api v1.2.4+
Nowe API instancyjne — NIE używać starego:
```python
# STARE (v0.x) — nie działa:
YouTubeTranscriptApi.get_transcript(video_id)

# NOWE (v1.2.4+) — poprawne:
ytt = YouTubeTranscriptApi()
entries = ytt.fetch(video_id, languages=['pl'])
```

### WordPress REST API — paginacja
Strony za ostatnią zwracają HTTP 400, nie pustą listę.
Sprawdzaj `status_code == 400` jako sygnał końca, nie `== 200`.

### Video Sitemap — RankMath limit
RankMath auto-generuje sitemap wideo, ale wykrywa ~38 z 213 postów.
Dlatego generujemy supplementary `video-sitemap-prawytv.xml` przez `core/sitemap.py`.

### SeekToAction — Polski content
Google nie renderuje SeekToAction dla treści polskojęzycznych.
Trzymamy w schemacie dla completeness i przyszłościowej kompatybilności.

### Gemini — rate limit w batch
Używaj `sleep_between=5` (domyślne w CLI) między wywołaniami.
Przy większych batchach (>20 filmów) rozważ `--sleep 10`.

### WP_APP_PASSWORD format
WordPress Application Passwords mają format z spacjami: `xxxx xxxx xxxx xxxx xxxx xxxx`.
HTTPBasicAuth automatycznie je obsługuje — nie usuwaj spacji.

---

*vse-architect-01 | video-seo-engine | 2026-05-13 — zaktualizowano DISPATCH-02*
