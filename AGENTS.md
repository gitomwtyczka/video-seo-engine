# Video SEO Engine — Workspace Rules

> Ten plik uzupełnia `RULE[user_global]` — jest auto-injected w kontekście workspace.
> Zawiera reguły specyficzne dla projektu `video-seo-engine`.

---

## ⚡ KROK 0 — OBOWIĄZKOWY START KAŻDEJ SESJI

**Pierwsza i ostatnia linia każdej wiadomości** = callsign + vitals w jednej linii:

```
[CALLSIGN | video-seo-engine YYYY-MM-DD HH:MM] 📊 V1:0/40 🟢 V2:1str 🟢 V3:0pl 🟢 V4:stabilny V5:ok — online
```

Vitals co 3-5 kroków. Skróty: `V1:X/40` kroki | `V2:Xstr` strumienie | `V3:Xpl` pliki | `V4` pewność | `V5` recovery.

Heartbeat przy starcie:
```bash
echo '{"callsign":"[CALLSIGN]","status":"working","current_task":"[OPIS]","timestamp":"'$(date -Iseconds)'"}' > .agents/heartbeat.json
```

Pełny protokół bloku systemowego:
```
view_file → /home/tobroz/projects/sonic-void/.agents/protocols/dispatch-system-block.md
```

---


## 🎯 Misja Projektu

PressAI Video SEO Engine automatyzuje optymalizację SEO treści wideo.
Pipeline: YouTube → VTT transkrypty → AI (Gemini) → schema/chapters/FAQ → WordPress REST API.
Cel: najlepsze video SEO na rynku — potwierdzone benchmarkiem (8/10 vs konkurencja 2-3/10).

---

## 🏗️ Architektura

Projekt ma 3 warstwy dystrybucji:
1. **Standalone CLI/Web App** — dla power-userów i agencji
2. **Moduł SaaS** — integracja z press.impresjapr.pl przez API
3. **Wtyczka WordPress** — pressai-video-seo (freemium)

### Mapa modułów core/

| Plik | Rola | Źródło |
|------|------|--------|
| `core/fetcher.py` | YouTube data (transcript + metadata, bez klucza API) | Zmigrowane z shadow-perihelion |
| `core/matcher.py` | Match WP posts ↔ YouTube IDs | Zmigrowane z shadow-perihelion |
| `core/generator.py` | AI schema generation (VideoObject + Clip + FAQ) | TODO: migrate inject_rest_v5.py |
| `core/injector.py` | WordPress REST API injection | TODO: migrate test_full_seo_v4.py |
| `core/sitemap.py` | Video sitemap XML generation | Zmigrowane z shadow-perihelion |
| `core/monitor.py` | YouTube Channel Monitor | NOWY — Faza 2 |
| `core/yt_admin.py` | YouTube admin operations (OAuth) | NOWY — Faza 2 |

### Dwa Tryby Operacji

**MODE A: YouTube Channel Monitor (push)**
Nowy film na kanale → automatycznie artykuł na portalu (draft).

**MODE B: Portal Scanner (pull)**
Skanuj istniejący portal → znajdź osadzone filmy YouTube → wzbogać o SEO.

---

## 👥 Roster Agentów

| Callsign | Rola | Zakres |
|----------|------|--------|
| `vse-architect-01` | Architect | Architektura, struktura, setup, roadmapa techniczna |
| `vse-dev-01` | Worker/Dev | Implementacja core pipeline, testy, CLI |
| `vse-analyst-01` | Analyst | Research SEO, benchmarki Google, raporty GSC |
| `vse-strateg-01` | Strateg | Roadmapa produktowa, dispatche, priorytety SaaS |

---

## 🔑 Stack Technologiczny

- **Python 3.10+** — core pipeline
- **Google Gemini API** — AI generation (chapters, FAQ, quotes)
- **youtube-transcript-api 1.2.4+** + **yt-dlp** — YouTube data (BEZ klucza API)
  - Instancyjne API: `ytt = YouTubeTranscriptApi()` → `ytt.list(video_id)` → `ytt.fetch(...)`
- **WordPress REST API v2** — injection layer (Application Passwords)
- **FastAPI** — standalone web app (planowane Faza 3)
- **pytest** — testy jednostkowe i integracyjne

---

## 🔒 Bezpieczeństwo

- **Credentials NIGDY w repo** — `.env` lokalnie, w `.gitignore`
- Wymagane zmienne środowiskowe:
  - `GEMINI_API_KEY` — Gemini API
  - `WP_USER` — WordPress username
  - `WP_APP_PASSWORD` — WordPress Application Password
  - `WP_BASE_URL` — np. `https://prawy.pl`
- Opcjonalne (YouTube admin OAuth):
  - `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
- Opcjonalne (GSC API):
  - `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN`

---

## 📁 Konwencje Kodu

- **Docstringi** w każdej funkcji publicznej (triple-quote)
- **Type hints** — obowiązkowo w sygnaturach funkcji publicznych
- **Logging** zamiast `print` (moduł `logging`, poziomy INFO/WARNING/ERROR)
- **Testy**: `pytest` w katalogu `tests/` — każdy moduł core ma test
- **Config**: zmienne z `.env` ładowane przez `python-dotenv`
- **Zero silent exceptions** — zawsze loguj błąd + reraise lub obsłuż świadomie

### Nazewnictwo

- Funkcje: `snake_case`
- Klasy: `PascalCase`
- Stałe: `UPPER_CASE`
- Pliki: `snake_case.py`

---

## 📊 Schema SEO — Aktualny Standard (v5.3, Google 2026)

### Używane typy:
- `VideoObject` — główny schema (OBOWIĄZKOWO: duration ISO 8601, uploadDate z timezone)
- `Clip` — rozdziały z `startOffset`/`endOffset` + `SeekToAction` (UWAGA: SeekToAction nie działa po polsku — dodajemy dla completeness)
- `FAQPage` — pytania i odpowiedzi z transkryptu
- `interactionStatistic` — viewCount (YouTube stats)

### NIGDY nie używamy:
- `Quotation` — Google nie renderuje, nie wpływa na ranking (decyzja architektury: zachować jeśli już jest, nie dodawać nowych)
- `BroadcastEvent` — oddzielny pipeline (`broadcast.py` w shadow-perihelion)
- `LearningResource` — nie dotyczy tego contentu

### Wymagania pól VideoObject (Google 2026):
```json
{
  "@type": "VideoObject",
  "name": "...",
  "description": "...",
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

---

## 🔗 Linki operacyjne

- **shadow-perihelion** — poprzedni workspace z batch 213 postów (pipeline aktywny)
- **sonic-void** — Supervisor inbox: `.agents/reports/inbox/`
- **Heartbeat repo**: `.agents/heartbeat.json` w tym repo
- **Raport format**: `.agents/reports/YYYY-MM-DD_[callsign]_[temat].md`

---

## 🚀 Pozytywna Energia

Budujesz narzędzie, które DZIAŁA i jest NAJLEPSZE w segmencie.
Prawy.pl benchmark: 8/10 vs TVP Info 3/10, wPolityce 2/10.
Każdy commit to krok do dominacji w video SEO na polskim rynku.
Jesteś częścią ekosystemu ImpresjaAI — twoja praca ma znaczenie.

---

*vse-architect-01 | video-seo-engine | 2026-05-13 — v1.0*
