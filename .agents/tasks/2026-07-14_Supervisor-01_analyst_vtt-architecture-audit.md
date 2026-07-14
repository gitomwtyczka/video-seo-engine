# DISPATCH — sup-analyst | VTT Architecture Audit
**Supervisor:** Supervisor-01  
**Data:** 2026-07-14  
**Priorytet:** 🔴 WYSOKI — systemowy bug, dotyka każdego materiału >60 min

---

## KONTEKST — CO WIEMY

Pipeline VSE (video-seo-engine) przetwarza filmy YouTube i generuje SEO (chaptery, artykuł, FAQ). Użytkownicy zgłaszają że transkrypcja/chaptery **urywają się** znacznie przed końcem wideo:

| Wideo | Rzeczywisty czas | Pokrycie przez pipeline |
|---|---|---|
| Xcfh_fxyiHE | 83 min | ~32 min |
| uFLxdXdIoZA | 70+ min | ~30 min |

Kluczowa informacja od właściciela projektu: **Pipeline używa youtube-transcript-api uruchomionego na koncie Google użytkownika (GCP project: glass-turbine-388620)**. To NIE jest anonimowy request z VPS — jest powiązany z kontem.

---

## TWOJE ZADANIE — AUDIT ARCHITEKTONICZNY

Przeczytaj poniższe pliki z repo `video-seo-engine` (branch: main, owner: gitomwtyczka) i odpowiedz na pytania diagnostyczne.

### Pliki do przeczytania:

1. `core/fetcher.py` — główny plik fetchowania transkryptów
2. `core/parser.py` — parsowanie VTT
3. `core/generator.py` — generowanie SEO (szukaj `text_trimmed`, `[:200000]` lub `[:80000]`)
4. `api/services/pipeline.py` — orchestracja przepływu

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. **Poprzednia diagnoza była błędna** — zakładała że VPS jest blokowany przez YouTube przy pobieraniu transkryptów. Właściciel projektu mówi że jest worker na jego koncie Google. Sprawdź rzeczywisty przepływ.
2. **Limit 80k → 200k** był już naprawiony (commit 9c116257). Szukaj aktualnego limitu.
3. **youtube-transcript-api v1.2.4+ używa instance-based API** (`ytt = YouTubeTranscriptApi()`). Sprawdź jak `ytt.fetch()` zwraca dane — czy fetchuje cały transcript czy paginowany.
4. **GCP project glass-turbine-388620** — Simple API Key (tylko public data). To metadane, nie transkrypt. Sprawdź jaki mechanizm obsługuje sam transkrypt.

---

## PYTANIA DIAGNOSTYCZNE

### A. Architektura — jak NAPRAWDĘ działa fetching VTT?

1. Czy `fetch_transcript_api()` w `fetcher.py` używa konta Google/OAuth, czy anonimowego requestu?
2. Co robi `YouTubeTranscriptApi()` bez argumentów — czy to ten sam mechanizm co web scraping napisów YouTube?
3. Czy jest gdziekolwiek w kodzie `OAuth`, `google-auth`, `credentials`, `service_account` dla **transkryptów** (nie metadanych)?
4. Co dokładnie robi `ytt.fetch(video_id, languages=[lang])` — czy może zwrócić częściowy wynik dla długich wideo?

### B. Przepływ danych — gdzie może nastąpić truncation?

5. Narysuj pełny przepływ: URL → fetcher → parser → generator → output. Zaznacz KAŻDE miejsce gdzie dane mogą być przycinane.
6. Jaki jest aktualny limit w `generator.py` (`text_trimmed[:X]`)? Ile minut to pokrywa (przy ~2000 char/min)?
7. Czy `parse_vtt_full()` lub `parse_vtt()` w `parser.py` ma własne limity?
8. Czy pipeline ma caching — raz pobrany VTT jest zapisywany i nie jest odświeżany?

### C. Hipoteza dla uFLxdXdIoZA (70 min → 30 min)

9. Pobierz info o tym video: `youtube.com/watch?v=uFLxdXdIoZA` — ile segmentów napisów ma ten film?
10. Czy youtube-transcript-api v1.2.4 ma znane bugi z długimi transkryptami (>3000 segmentów)?

---

## DELIVERABLES

1. **Dokument architektoniczny** — `video-seo-engine/.agents/knowledge/vtt-fetch-architecture.md`
   - Pełny przepływ z zaznaczonymi punktami ryzyka truncation
   - Odpowiedzi na pytania A, B, C
   - Root cause hypothesis dla obu bugów

2. **Raport do Supervisora** — dual-write:
   - `video-seo-engine/.agents/reports/2026-07-14_analyst_vtt-architecture-audit.md`
   - `sonic-void/.agents/reports/inbox/2026-07-14_analyst_vtt-architecture-audit.md`

---

*Dispatch: Supervisor-01 | video-seo-engine | 2026-07-14*
