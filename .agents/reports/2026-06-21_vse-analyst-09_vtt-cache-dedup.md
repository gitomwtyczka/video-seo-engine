# A9: VTT Cache + Content Dedup — Analiza

**Callsign:** vse-analyst-09  
**Data:** 2026-06-21  
**Dispatch:** DISPATCH-VSE-ANALYST-09-20260621-VTT-CACHE-DEDUP  
**Pliki zbadane:** `core/fetcher.py`, `api/services/pipeline.py`, `core/generator.py`, `api/models/job.py`, `api/db.py`, `api/models/__init__.py`

---

## VTT Cache

### Obecny flow (diagnoza)

Obecny flow transkryptu ma **zero cache** — każde wywołanie `POST /v1/generate` pobiera VTT od nowa:

```
run_generate() → tempfile.TemporaryDirectory() → fetch_video() → fetch_transcript_api()
                                                                → [fallback] fetch_transcript_ytdlp()
                                                                → save VTT to tmp_dir
                → generate_schema() ← reads VTT from tmp_dir
                → [exit with block] → tmpdir DELETED by Python context manager
```

**Kluczowe problemy:**
1. `tempfile.TemporaryDirectory()` jest kasowany natychmiast po zakończeniu requestu — VTT ginie bezpowrotnie
2. `fetch_transcript_api()` robi pełny request do YouTube za każdym razem (listing + fetch + format)
3. W trybie `LOCAL_RUNNER_MODE=true` — tworzy nowy `TranscriptJob`, czeka na Local Runnera (2min timeout), a transkrypt z kolumny `transcript` nigdy nie jest reużywany
4. Tabela `transcript_jobs` **nie nadaje się jako cache** — jej PK to UUID, klucz to `video_url` (nie `video_id + lang`), brak indeksu wyszukiwania po video_id

**Konsekwencje:**
- Użytkownik generuje 3 artykuły z tego samego wideo (analiza + watching_page + discover) = **3x fetch z YouTube** (lub 3x czekanie na Local Runner ~50s każdy)
- YouTube może rate-limitować częste requesty z tego samego IP
- Local Runner obciążony redundantnym fetching

### Rozmiar typowego VTT

| Parametr | Wartość |
|----------|----------|
| 15-min wideo | ~15-25 KB (WebVTT) |
| 30-min wideo | ~30-50 KB |
| 60-min wideo | ~60-100 KB |
| 120-min wideo | ~120-200 KB |

Transkrypt to **czysty tekst** — nawet najdłuższe wideo to <200 KB. PostgreSQL `TEXT` obsłuży to bez problemu.

### Propozycja: tabela `vtt_cache`

```sql
CREATE TABLE vtt_cache (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id     VARCHAR(11)  NOT NULL,
    lang         VARCHAR(10)  NOT NULL,
    vtt_text     TEXT         NOT NULL,
    vtt_format   VARCHAR(20)  NOT NULL DEFAULT 'webvtt',
    source       VARCHAR(30)  NOT NULL DEFAULT 'transcript_api',
    char_count   INTEGER      NOT NULL,
    fetched_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uq_vtt_cache_video_lang UNIQUE (video_id, lang)
);

CREATE INDEX idx_vtt_cache_expires ON vtt_cache (expires_at);
CREATE INDEX idx_vtt_cache_video ON vtt_cache (video_id);
```

### Klucz cache

`video_id` + `lang` — composite unique constraint. Ten sam film może mieć transkrypt PL (manual) i EN (auto-generated).

### TTL

| Typ contentu | TTL | Uzasadnienie |
|---|---|---|
| Napisy manualne | **30 dni** | Rzadko się zmieniają |
| Auto-generated (YouTube ASR) | **7 dni** | YouTube czasem regeneruje auto-subs |
| Local Runner VTT | **30 dni** | Skopiowany raz, identyczny z YouTube |

Cleanup: CRON job co 24h: `DELETE FROM vtt_cache WHERE expires_at < NOW()`.

### Proponowany flow z cache

```
run_generate(video_url, lang=...)
  → video_id = extract(video_url)
  → CACHE CHECK: SELECT vtt_text FROM vtt_cache WHERE video_id = ? AND lang = ? AND expires_at > NOW()
  → HIT? YES → use cached vtt_text, skip fetch entirely
  → HIT? NO  → fetch from YouTube (existing flow) → INSERT/UPSERT INTO vtt_cache
  → continue to generate_schema()
```

Cache check w `pipeline.py::run_generate()`, **przed** `tempfile.TemporaryDirectory()`.

### Szacowany wpływ na performance

| Scenariusz | Bez cache | Z cache | Oszczędność |
|---|---|---|---|
| 1 artykuł, nowe wideo | ~3-5s | ~3-5s (miss) | 0 |
| 2. artykuł z tego samego wideo | ~3-5s | **~50ms** | **~98%** |
| Local Runner mode, 2. artykuł | **~50-120s** | **~50ms** | **>99%** |

---

## Content Deduplication

### Obecny stan (diagnoza)

**Brak jakiejkolwiek dywersyfikacji:**
1. `generate_seo_v4()` buduje identyczny prompt dla tego samego wideo — niezależnie od liczby wywołań
2. Brak memory — pipeline nie wie że film był już przetwarzany
3. Brak temperature control w `_call_llm()`
4. `publication_type` zmienia format ale nie perspektywę — 2x `full_analysis` = prawie identyczny artykuł

### Propozycje dywersyfikacji

#### 1. Parametr `angle` w prompcie (REKOMENDOWANE — niski koszt, wysoki impact)

```python
ANGLES = {
    "neutral": "Pisz obiektywnie, przedstaw fakty i argumenty obu stron.",
    "analytical": "Skup się na analizie przyczyn i skutków.",
    "opinion": "Pisz jako komentarz redakcyjny.",
    "breaking": "Pisz jak wiadomość z ostatniej chwili.",
    "background": "Pisz jako artykuł backgroundowy. Kontekst historyczny.",
    "interview_summary": "Skup się na najważniejszych wypowiedziach rozmówcy.",
}
```

#### 2. `previously_used_quotes` — anti-repeat (REKOMENDOWANE)

Pipeline przekazuje do promptu listę cytatów i wątków z poprzednich generowań:
```
## UWAGA — TEN MATERIAŁ BYŁ JUŻ PRZETWARZANY
NIE UŻYWAJ tych cytatów: [...]
Skup się na INNYCH aspektach niż: [...]
```

Wymaga: tabela `generation_history`.

#### 3. Temperature tuning (OPCJONALNE — niski impact)

Explicit temperature: 0.9 dla analizy, 1.1 dla discover. Nie rekomendowane jako główny mechanizm.

### Schema: `generation_history`

```sql
CREATE TABLE generation_history (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id         VARCHAR(11)   NOT NULL,
    profile_id       VARCHAR(50)   NULL,
    publication_type VARCHAR(30)   NOT NULL,
    angle            VARCHAR(30)   NULL,
    post_title       VARCHAR(200)  NOT NULL,
    focus_keyphrases JSONB         NOT NULL,
    used_quotes      JSONB         NULL,
    used_chapters    JSONB         NULL,
    article_hash     VARCHAR(64)   NULL,
    llm_provider     VARCHAR(20)   NOT NULL,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    schema_data      JSONB         NULL
);

CREATE INDEX idx_genhistory_video ON generation_history (video_id);
CREATE INDEX idx_genhistory_video_portal ON generation_history (video_id, profile_id);
```

### Rekomendacja: auto-detect w pipeline (Opcja A)

Pipeline sam sprawdza `generation_history` przed LLM. Zero zmian w API — dywersyfikacja transparentna.

---

## Estymacja pracochłonności

### VTT Cache: 1 dispatch, ~3-4h
- Model `VttCache` + migracja: 30min
- Cache logic w pipeline.py: 1.5h
- Integracja z Local Runner flow: 45min
- Cleanup task: 15min
- Testy pytest: 45min

### Content Dedup: 1-2 dispatche, ~4-6h
- Model `GenerationHistory` + migracja: 30min
- `angle` parameter + prompt section: 1h
- Anti-repeat logic: 1.5h
- Auto-detect w run_generate(): 1h
- article_hash similarity check: 30min
- Testy pytest: 1h

### Łącznie: 2-3 dispatche, ~8-10h

Rekomendowany order:
1. **A9-IMPL-1:** VTT Cache (samodzielny, zero dependencies)
2. **A9-IMPL-2:** Content Dedup (angle + generation_history + anti-repeat)
3. **Opcjonalnie A9-IMPL-3:** Dashboard UI — historia generowań per wideo

---

*[vse-analyst-09 | video-seo-engine 21.06.2026 17:25] — raport kompletny*