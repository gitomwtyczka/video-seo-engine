# DISPATCH: fix-vtt-truncation-runner
**Target:** vse-dev  
**Repo:** video-seo-engine  
**Plik:** `local-runner/runner.py`  
**Priorytet:** CRITICAL — produkcja zwraca ucięte VTT  
**Data:** 2026-07-20

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. **Backup przed modyfikacją** — OBOWIĄZKOWO: `get_file_contents` → zapisz jako `local-runner/runner.py.bak-2026-07-20` przez `create_or_update_file`
2. **Długi plik (26KB)** — NIE podmieniaj całości. Targeted edits — tylko zmieniane funkcje.
3. **Po każdym `create_or_update_file`** → natychmiast `get_file_contents` → weryfikuj newlines
4. **Nie dotykaj** logiki pollingu, submit_result, process_job, main() — tylko funkcje pobierania VTT
5. **GitHub SHA** — przy aktualizacji istniejącego pliku zawsze pobierz aktualny SHA najpierw

---

## Kontekst — diagnoza root cause

Flow:
```
Twój PC: local-runner/runner.py
  → poll GET /v1/jobs/pending
  → fetch_transcript(video_url)        ← tu problem
    → yt-dlp --write-auto-sub          ← pobiera tylko pierwszy chunk
    → _parse_webvtt_to_segments()      ← parsuje ucięty plik
    → _format_segments_as_vtt()        ← wysyła ucięty __VTT__
  → POST /v1/jobs/{id}/result
    ↓
VPS: pipeline.py odbiera ucięty VTT → generuje artykuł na 40min zamiast 82min
```

**Problem:** `yt-dlp --write-auto-sub` dla długich filmów (>40min) pobiera
autogenerowane napisy z YouTube w trybie chunked — domyślnie zwraca
tylko część (ok. 40min). Brak flagi wymuszającej pełne pobieranie.

---

## Wymagane zmiany

### 1. Obie funkcje pobierania: `_try_ytdlp_with_cookies_file()` i `_try_ytdlp_with_browser()`

Do komendy `yt-dlp` dodaj flagi:
```python
"--extractor-args", "youtube:player_client=tv_embedded",
"--no-part",
"--retries", "10",
"--fragment-retries", "10",
```

Uzasadnienie:
- `player_client=tv_embedded` — TV client zwraca napisy jako jeden pełny
  plik zamiast chunked stream. Sprawdzona metoda omijania cenzury chunkowania.
- `--no-part` — nie zapisuj pliku jako `.part` (zapobiega sytuacji gdzie
  plik VTT istnieje ale jest niekompletny)
- `--retries` + `--fragment-retries` — długie filmy mogą wymagać więcej prób

Alternatywne wartości `player_client` do próby jeśli `tv_embedded` nie zadziała:
`web_creator`, `android_embedded` (w komentarzu w kodzie jako TODO)

### 2. Dodaj walidację pokrycia VTT po parsowaniu

Dodaj nową funkcję (PRZED `fetch_transcript_ytdlp`):

```python
def _get_segments_duration(segments: list) -> float:
    """Zwraca czas ostatniego segmentu w sekundach."""
    if not segments:
        return 0.0
    last = max(segments, key=lambda s: s.get("start", 0.0))
    return float(last.get("start", 0.0))
```

W `_try_ytdlp_with_cookies_file()` i `_try_ytdlp_with_browser()`,
po parsowaniu segmentów dodaj log z czasem pokrycia:

```python
seg_duration = _get_segments_duration(segments)
log.info(
    "VTT coverage: last segment at %.0fs (%dm %02ds) — %d segments",
    seg_duration, int(seg_duration // 60), int(seg_duration % 60), len(segments)
)
```

To pozwoli w logach zobaczyć ile minut faktycznie pokrywa pobrany VTT.

### 3. NIE zmieniaj
- Logiki pollingu (main, get_pending_jobs)
- submit_result
- process_job
- fetch_transcript_api (youtube-transcript-api fallback)
- Konfiguracji (zmienne env)

---

## Plan pracy

1. `get_file_contents` runner.py → pobierz SHA + przeczytaj
2. `create_or_update_file` → backup `.bak-2026-07-20` (ta sama treść)
3. Edytuj `_try_ytdlp_with_cookies_file()` — targeted replace tylko komendy cmd[]
4. Edytuj `_try_ytdlp_with_browser()` — targeted replace tylko komendy cmd[]
5. Dodaj funkcję `_get_segments_duration()` + logi
6. `get_file_contents` → weryfikuj newlines i składnię
7. Dual-write raport

---

## Pliki testowe (user weryfikuje po instalacji)

| video_id    | Oczekiwany czas |
|-------------|------------------|
| uIwj95733_E | ~82min (4920s)   |
| uFLxdXdIoZA | ~70min (4200s)   |

W logach runnera powinno pojawić się:
```
VTT coverage: last segment at 4850s (80m 50s) — 2341 segments
```
zamiast poprzedniego:
```
VTT coverage: last segment at 2400s (40m 00s) — ...
```

---

## Raportowanie

Dual-write:
1. `video-seo-engine/.agents/reports/YYYY-MM-DD_vse-dev_runner-vtt-fix.md`
2. `sonic-void/.agents/reports/inbox/YYYY-MM-DD_vse-dev_runner-vtt-fix.md`

Raport musi zawierać:
- SHA commita
- SHA backupu
- Dokładne flagi które zostały dodane do komendy yt-dlp
- Czy walidacja pokrycia działa (z przykładowym logiem)
- Czy są jakieś nierozwiązane edge case'y
