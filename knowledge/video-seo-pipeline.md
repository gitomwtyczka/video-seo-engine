# PressAI Video SEO Engine — Pipeline Knowledge

> Ostatnia aktualizacja: 2026-05-14 | vse-architect-01

---

## Status Faz

| Faza | Status | Opis |
|------|--------|------|
| Faza 1 — Core Pipeline | **KOMPLETNA** ✅ | generate + inject + CLI zwalidowane produkcyjnie |
| Faza 2 — Channel Monitor | **W TOKU** 🟡 | core/monitor.py + vse watch zaimplementowane, oczekuje na CHANNEL_ID |
| Faza 3 — Standalone App | Planowana 🔵 | FastAPI web UI |

---

## Faza 1 — Core Pipeline ✅

### Zwalidowane na produkcji

- **Wideo:** `U9HLRRXs5EU` (Prawy.pl WP#119445)
- **Data walidacji:** 2026-05-13
- **Wynik:** VideoObject + 9 Clipow + FAQPage — REST API 200

### Moduły

| Modul | Status | Commit |
|-------|--------|--------|
| `core/generator.py` | Done ✅ | `3f9c243` |
| `core/injector.py` | Done ✅ | `cde3bb2` |
| `core/fetcher.py` | Done ✅ | migracja z shadow-perihelion |
| `core/matcher.py` | Done ✅ | migracja z shadow-perihelion |
| `core/sitemap.py` | Done ✅ | migracja z shadow-perihelion |
| `cli/main.py` | Done ✅ | `f6f0a5c` |

### Schema v5.3 (Google 2026) — Zaimplementowane

- `VideoObject` — uploadDate (timezone), duration (ISO 8601), thumbnailUrl, embedUrl
- `Clip` — startOffset/endOffset + SeekToAction (dla completeness)
- `FAQPage` — z transkryptu VTT via Gemini
- `interactionStatistic` — WatchAction (wymaga YT_API_KEY)

---

## Faza 2 — YouTube Channel Monitor 🟡

### Cel (MODE A — push)

Automatyczne wykrywanie nowych filmow na kanale YouTube i tworzenie szkicow w WordPress.

### Flow

```
Nowy film na kanale YT
  -> get_latest_videos() [YouTube Data API v3]
  -> check_registry() [zapobiega double-injection]
  -> create_draft() [WP REST POST — szkic z embedem]
  -> trigger_generate() [core/generator.py — wymaga VTT]
  -> update_registry() [status: injected]
```

### Moduły Faza 2

| Modul | Status | Commit |
|-------|--------|--------|
| `core/monitor.py` | Done ✅ | `58a9ff6` |
| `cli/main.py` — `vse watch` | Done ✅ | `f6f0a5c` |
| `registry/U9HLRRXs5EU.json` | Done ✅ | `3435596` |
| `.env.example` — CHANNEL_ID | Done ✅ | `ea147eb` |

### Wymagane do uruchomienia

1. **CHANNEL_ID** — ID kanalu YouTube Prawy TV (format: `UCxxxx`)
   - Znajdz w: https://www.youtube.com/@PrawyTV/about → "Udostepnij kanal" → ID
2. **YT_API_KEY** — YouTube Data API v3 (Google Cloud Console)

### Uruchomienie dry-run

```bash
python -m cli.main watch --channel UC... --dry-run --once
```

### Pre-flight registry check

Kazde wywolanie generate/inject OBOWIAZKOWO sprawdza `registry/{video_id}.json`:
- Status `injected` lub `pending` → SKIP (nie przetwarza ponownie)
- Brak wpisu → przetwarza normalnie

### Format registry

```json
{
  "video_id": "U9HLRRXs5EU",
  "status": "injected",
  "wp_post_id": 119445,
  "injected_at": "2026-05-13T23:50:46+02:00",
  "agent": "vse-architect-01"
}
```

---

## Faza 3 — Standalone App 🔵 (planowana)

FastAPI web UI — dla power-userow i agencji.
Integracja z PressAI SaaS przez API.

---

## Techniczny Stack

- Python 3.10+
- Google Gemini API (gemini-2.5-flash)
- youtube-transcript-api 1.2.4+ + yt-dlp
- WordPress REST API v2 (Application Passwords)
- FastAPI (planowane, Faza 3)

---

## Znane Problemy / Gotcha

| Problem | Rozwiazanie |
|---------|-------------|
| CP1250 UnicodeEncodeError na Windows | Uzywaj `->` zamiast `->` w print() |
| `load_dotenv()` nie laduje .env w bridge | Przekaz env var inline w $env: w PowerShell |
| SEO JSON nie zapisany mimo "Saved" w logu | Exception w print() po zapisie — plik jest zapisany |
| YouTube API quota | Data API v3: 10000 units/dzien; search.list = 100 units |
