# Video SEO Pipeline — Architecture & Knowledge Base

**Wersja:** v5.3 (stan: 2026-05-13)
**Źródło:** shadow-perihelion (sesje 2026-05-07 do 2026-05-12)
**Autor:** vse-architect-01

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
[core/generator.py]  ← TODO: migrate from shadow-perihelion
  ├── Gemini API: parse VTT → chapters, FAQ, description
  ├── Build JSON-LD: VideoObject + Clip[] + FAQPage
  └── Output: seo_results/<video_id>.json
        │
        ▼
[core/injector.py]   ← TODO: migrate from shadow-perihelion
  ├── WordPress REST API: GET + PATCH /wp-json/wp/v2/posts/<id>
  ├── Inject/replace <script type="application/ld+json"> block
  └── Atomic update (rollback on failure)
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
Aktualizowany przy każdym re-processingу.

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

## 📊 Status Operacyjny (2026-05-13)

| Metryka | Wartość |
|---------|---------|
| Pipeline version | v5.3 |
| Posty live (prawy.pl) | 6 |
| Kolejka (archiwum) | 213+ |
| Batch status | w toku w shadow-perihelion |
| Schema score (Google) | 8/10 |
| Konkurencja TVP Info | 3/10 |
| Konkurencja wPolityce | 2/10 |

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

---

*vse-architect-01 | video-seo-engine | 2026-05-13*
