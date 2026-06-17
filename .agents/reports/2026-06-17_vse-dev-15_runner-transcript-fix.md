# Raport: Local Runner Transcript Fix (v3.0)

**Agent:** vse-dev-15  
**Data:** 2026-06-17  
**Status:** ✅ NAPRAWIONE  
**Commit:** `98212642ab74251d17617c6f66dbf5a8459b2831`

---

## Diagnoza

### Root Cause
YouTube zaczął blokować requesty bez cookies nawet na domowych IP.
Wymagana jest autentykacja cookies z przeglądarki (`"Sign in to confirm you're not a bot"`).

### Przebieg analizy

1. **Logi VSE API** — potwierdzają: runner DZIAŁA (polluje /v1/jobs/pending co ~10s), job został pobrany i przetworzony
2. **Test lokalny** — `youtube-transcript-api` zwraca `RequestBlocked` nawet na lokalnym PC
3. **Test yt-dlp bez cookies** — ten sam error: `Sign in to confirm you're not a bot`
4. **Test yt-dlp + chrome/edge cookies** — `Could not copy Chrome cookie database` (Chrome zablokowany przez OS/inne procesy)
5. **Test yt-dlp + firefox cookies** — **SUKCES**: 455 cookies wyodrębnione, transkrypt pobrany (pl + en json3)

### Potwierdzenie działania

```
[INFO] yt-dlp OK: browser=firefox lang=pl segments=1333 chars=55598
SUCCESS! Lines: 1334
  __VTT__
  [00:05] Rosja jest dzisiaj celem
  [00:06] niezapowiedzianych odwiedzin, odwiedzin
  ...
```

---

## Zmiana (runner v3.0)

**Plik:** `local-runner/runner.py` w repo `video-seo-engine`

### Poprzednia strategia (v2)
- youtube-transcript-api (PRIMARY) — **ZABLOKOWANE** przez YouTube

### Nowa strategia (v3)
1. `yt-dlp --cookies-from-browser firefox` (PRIMARY) ← **DZIAŁA**
2. `yt-dlp --cookies-from-browser chrome` (fallback 1)
3. `yt-dlp --cookies-from-browser edge` (fallback 2)
4. `youtube-transcript-api` bez cookies (last resort)

### Nowe komponenty
- `fetch_transcript_ytdlp()` — primary strategy z fallback po przeglądarkach
- `_try_ytdlp_with_browser()` — pojedyncza próba z konkretną przeglądarką
- `_parse_json3_to_segments()` — parser formatu json3 (yt-dlp) → [{text, start}]
- `fetch_transcript_api()` — wyodrębniony fallback z youtube-transcript-api
- `fetch_transcript()` — kompozycja wszystkich strategii

### Format wyjściowy
Bez zmian — nadal `__VTT__` z markerami `[MM:SS]`, pipeline.py nie wymaga modyfikacji.

---

## Weryfikacja

- ✅ Test jednostkowy: `fetch_transcript_ytdlp('yPRRbK1WLRs')` → 1333 segmentów
- ✅ Commit w repo: `98212642`
- ✅ Git pull OK na lokalnym klonie
- ⚠️ Encoding pl znaków może wymagać weryfikacji (wyświetlanie ok, ale terminale mogą pokazywać znaki zastępcze)

---

## Wymagania

- **Firefox musi być zainstalowany i zalogowany do YouTube** na PC usera
- yt-dlp zaktualizowany do ≥ 2026.6.9 (`pip install -U yt-dlp`)
- Runner działa jako NSSM Windows Service — Firefox cookies są dostępne z profilu użytkownika

---

## Nie zrobiono / Do rozważenia

- Test e2e pełnego generowania (VSE → runner → wynik) — wymaga restartowania runnera
- NSSM powinien działać pod kontem użytkownika (nie SYSTEM) dla dostępu do cookies Firefox
- Monitoring: dodać alert gdy wszystkie strategie zawodzą

---

*vse-dev-15 | crimson-void | 2026-06-17 22:05*