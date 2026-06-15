# SUPPLEMENT — DISPATCH-VSE-STRATEG-02-20260615-CORE-PORT
## Pogłębiony audyt: co jest i czego nie ma w shadow-perihelion

**Od:** sup-analyst-01 (Opcja A — pogłębiony audyt)  
**Do:** vse-strateg-02  
**Data:** 2026-06-15 20:55 CEST  
**Priorytet:** 🔴 — czytaj PRZED pracą nad `generator.py`

Czytaj ten plik ZARAZ PO dispatchu głównym. Uzupełnia brakującą wiedzę.

---

## ARCHITEKTURA PIPELINE v5 — tak działało lokalnie

Z README.md i USAGE.md shadow-perihelion:

```
1. match_prawy_tv.py    → WP REST API → Lista postów z embedded YT URL → CSV
2. youtube_fetch.py     → yt-dlp + youtube-transcript-api → VTT + metadata JSON
3. generate_seo_v5.py   → Gemini AI + VTT → SEO JSON (schema, FAQ, rozdzialy, cytaty)
4. inject_rest_v5.py    → WP REST API → PATCH post z HTML + JSON-LD schema
```

Krytyczny detail: `generate_seo_v5.py` i `inject_rest_v5.py` **NIGDY nie były w repozytorium GitHub**.

Były czysto lokalne:
- `SUBS_DIR = D:\\Biblioteki\\prawy.pl\\subs\\`
- `OUT_DIR  = D:\\Biblioteki\\prawy.pl\\seo_results_v5\\`

Stan w VSE repo: `core/injector.py` Został zmigrowany (potwierdzony przez pipeline.py).  
Stan w VSE repo: `core/generator.py` i `core/fetcher.py` — **NIE ISTNIEJĄ**.

---

## CO GENEROWAŁ generate_seo_v5.py — wymagana struktura wyjściowa

Na podstawie CHANGELOG.md, README.md, handoffów i VSE pipeline.py:

### Format JSON wyjściowego (to musi zwrócić `core/generator.py`):

```python
{
    # Tytuły
    "post_title": str,          # Tytuł do WP (PL, zoptymalizowany SEO)
    "yt_title": str,            # Tytuł do aktualizacji na YouTube
    "seo_title": str,           # RankMath SEO title
    "focus_keyphrase": str,     # RankMath focus keyphrase
    
    # Treść WP
    "lead": str,                # Lead article (HTML)
    "article_body": str,        # Body tekstu (HTML, z cytami/quoations)
    
    # VideoObject schema
    "schema": {                 # lub "schema_json_ld"
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": str,
        "description": str,
        "thumbnailUrl": str,
        "uploadDate": str,          # ISO 8601
        "duration": str,            # ISO 8601 (PT#H#M#S)
        "embedUrl": str,            # https://www.youtube.com/embed/{id}
        "contentUrl": str,          # https://www.youtube.com/watch?v={id}
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/WatchAction",
            "userInteractionCount": int   # viewCount z YT API
        },
        "hasPart": [                # Klipy-rozdzialy
            {
                "@type": "Clip",
                "name": str,
                "startOffset": int,     # sekundy
                "endOffset": int,
                "url": str              # ...?t={start}
            }
        ]
    },
    
    # FAQ schema
    "faq": [                    # lub nested w schema
        {"question": str, "answer": str}
    ],
    
    # Rozdzialy YouTube
    "chapters": [               # Format do opisu YT
        {"start": str, "title": str}  # start: "MM:SS" lub "H:MM:SS"
    ],
    
    # YT opis
    "yt_description": str,      # Pełny opis do YT z rozdzialami
    
    # Metadane pomocnicze
    "youtube_id": str,
    "wp_post_id": int
}
```

Skalowanie FAQ/rozdziałów (z README):

| Długość | FAQ | Rozdziały | Cytaty |
|---------|-----|-----------|--------|
| ≤15 min | 2-3 | 5-7 | 2-3 |
| 16-30 min | 3-5 | 6-10 | 3-5 |
| 31-45 min | 4-6 | 8-12 | 4-6 |
| >45 min | 5-8 | 10-15 | 5-7 |

### Techniki generowania (z README + handoffów):

1. **Anchor-matched timestamps** — fuzzy match VTT → 100% precyzja chapter links
2. **seekTo() in-page** — rozdziały sterują playerem na stronie (JS), nie otwierają YT
3. **Polished quotes** — AI wygładza surowy transkrypt do czytelnych cytatów
4. **YouTube thumbnail** — auto upload jako featured image WP (z dedup)
5. **uploadDate** — pobierana z WP REST API post `date` field
6. **interactionStatistic.userInteractionCount** — z `YT_API_KEY` (Google `videos.list`)

---

## CO ROBI inject_rest_v5.py — zidentyfikowana logika

`core/injector.py` JUŻ ISTNIEJE w VSE i jest importowany przez `pipeline.py`. Nie pisz go od nowa.

Ale dla kontekstu — co było w lokalnej wersji (z CHANGELOG + handoffów):

```
# inject_rest_v5.py robił:
1. GET /wp/v2/posts/{id}  → pobierz uploadDate, istniejącą treść
2. PUT /wp/v2/media       → upload thumbnails YT jako featured image (z dedup check)
3. PATCH /wp/v2/posts/{id} → aktualizuj: title, content (HTML+JSON-LD), excerpt
4. RankMath meta (przez custom endpoint lub postmeta direct):
   - rank_math_focus_keyword
   - rank_math_title  
   - rank_math_description
5. videos.update (OAuth)  → aktualizuj opis YT z rozdzialami + hashtagi
```

Jeśli `core/injector.py` w VSE repo ma ograniczoną funkcjonalność — patrz na to jako source of truth tego CO miało działać.

---

## CO ROBI match_prawy_tv.py — jest w repo

`scripts/video-seo/match_prawy_tv.py` JEST w GitHub shadow-perihelion. Przeczytaj go.

Działa:
```python
# 1. WP REST API: GET /wp/v2/posts?categories=2472&per_page=100
# 2. W każdym poście: regex search youtube.com/watch?v= lub youtu.be/
# 3. Jeśli ma VTT w SUBS_DIR: dodaj do listy do przetworzenia
# 4. Wynik: lista par (wp_post_id, youtube_id, vtt_path)
```

Dla VSE: `core/matcher.py` powinien robić to samo ale bez lokalnych ścieżek — przez `requests` do WP REST API.

---

## KRYTYCZNE ODKRYCIE: generate_seo_v5.py jest LOKALNY

**generate_seo_v5.py nie był nigdy commitowany do GitHub.**

Useř posiada go lokalnie na swoim komputerze Windows (`D:\Biblioteki\prawy.pl\`).

### Co to znaczy dla Ciebie:

**OPCJA A (rekomendowana) — zapytaj Usera:** 
> "Potrzebuję dostępu do `generate_seo_v5.py` — możesz skopiować jego treść lub commitnąć do shadow-perihelion?"

**OPCJA B — zbuduj na podstawie specyfikacji:**  
Jeśli User nie może/nie chce — zbuduj `core/generator.py` na podstawie:
- Struktury wyjściowej z sekcji wyżej
- Skalowania FAQ/rozdziałów z README
- Prompt w języku polskim do Gemini API
- Techniki anchor-matched timestamps

**OPCJA B wymaga VSE CLI test lokalnego** — nie deployuj na VPS bez testowania.

---

## STAN WIEDZY — podsumowanie per plik

| Plik Źródłowy | Gdzie | W VSE jako | Status |
|---|---|---|---|
| `youtube_fetch.py` | GitHub shadow-perihelion ✅ | `api/core/fetcher.py` | Do napisania |
| `generate_seo_v5.py` | LOKALNIE u Usera ❌ nie w repo | `api/core/generator.py` | Zapytać Usera |
| `inject_rest_v5.py` | LOKALNIE u Usera ❌ nie w repo | `api/core/injector.py` | JUŻ ZMIGROWANY |
| `match_prawy_tv.py` | GitHub shadow-perihelion ✅ | `api/core/matcher.py` | Placeholder w pipeline |
| `fix_featured_images.py` | GitHub shadow-perihelion ✅ | NIE DOTYCZY | Oracle VPS batch tool |
| `fix_parallel_worker.py` | GitHub shadow-perihelion ✅ | NIE DOTYCZY | Oracle VPS batch tool |
| `prawy-admin-scraper/` | GitHub shadow-perihelion ✅ | NIE DOTYCZY | CMS scraper — osobny projekt |

---

## PLAN DZIAŁANIA — równolegle z fetcher

```
Krok 1: Port youtube_fetch.py → api/core/fetcher.py  [jak w dispatchu głównym]
Krok 2: Zapytaj Usera o generate_seo_v5.py  [STOP i czekaj]
Krok 3: Odeślij generate_seo_v5.py do Supervisora — port jako core/generator.py
Krok 4: Test end-to-end lokalnie (nie na VPS) przed deployem
```

Jeśli User długo nie odpowiada — commituj fetcher, raportuj, zamknij sesję.

---

*sup-analyst-01 | sonic-void | 2026-06-15 20:58 CEST — audyt pogłębiony*
