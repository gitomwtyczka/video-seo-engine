# YouTube Description Pipeline — VSE
**Wersja:** 2.2-FINAL | **Data:** 2026-07-12 | **Status:** ZATWIERDZONE — IMPLEMENTACJA W TOKU

> ✅ Spec zatwierdzony przez właściciela projektu 2026-07-12
> 🔄 Decyzja architektoniczna: generowanie treści YT przeniesione do PressAI (crimson-void)

---

## Decyzja architektoniczna (ADR-001)

**Data:** 2026-07-12 | **Supervisor 05**

**Kontext:** VSE miał samodzielnie generować opis YT przez `core/generator.py`. Odkryto, że:
- PressAI (press.impresjapr.pl / crimson-void) to centralny silnik LLM ekosystemu
- `article_formats.yaml` zawiera system formatów treści + już istnieje `video_satellite`
- PressAI przyjmuje `.vtt` natywnie jako źródło danych
- Duplikacja logiki LLM w VSE = dług techniczny

**Decyzja:** Generowanie treści (body, mid-CTA, credits, hashtagi) → PressAI.
Sładanie struktury (timestamps, link, stopka, guard 5000 zn) → VSE `inject.py`.

**Architektura:**
```
VSE pipeline:
  1. Generuje SEO schema (generator.py) — bez pól YT
  2. POST press.impresjapr.pl/api/external/generate-yt-description
     { vtt_content, video_title, chapters, focus_keyphrases, ... }
  3. PressAI → { youtube_description_body, youtube_mid_cta,
                   youtube_credits, youtube_hashtags }
  4. inject.py składa moduły M1-M8 w finalny opis
  5. Fallback: stary youtube_description_hook z generatora
```

---

## Struktura modułowa opisu (9 modułów)

| # | Moduł | Kto | Rozmiar |
|---|--------|-----|--------|
| M1 | Hook + body semantyczny | **PressAI** | 350–900 zn (elastyczny) |
| M2 | Link do artykułu WP | inject.py | ~60 zn |
| M3 | Mid-CTA kontekstowe | **PressAI** | max 120 zn |
| M4B | Cytaty z deep linkami | inject.py | op., 2-3 cytaty |
| M5 | Timestamps / rozdziały | inject.py | auto, jeśli ≥3 |
| M6 | Autorstwo / ƽródła | **PressAI** | 1-2 linie |
| M7 | Stopka per-kanał | inject.py | max 600 zn |
| M8 | Hashtagi | **PressAI** | dokładnie 3 |
| GUARD | Limit 5000 zn | inject.py | cięcie z `...` |

**Body:** 350-450 zn news | 500-900 zn wywiad/analiza
**Stopka:** pełna (wersja prawy.pl wklejona przez użytkownika)
**Mid-CTA:** kontekstowe, np. *"Subskrybuj, aby nie przegapić kolejnych analiz polskiej polityki. 🔔"*
**Autorstwo:** szukane w transkrypcie, jeśli brak — podaje imię i nazwisko

---

## Stopka PressAI (prawy.pl) — treść produkcyjna

```
📺 PRAWY.PL — Niezależne media
🌐 https://prawy.pl
📘 Facebook: https://www.facebook.com/PortalPrawy/
🐦 Twitter/X: https://twitter.com/prawypl
▶️ YouTube: https://www.youtube.com/user/portalprawypl

❤️ WESPRZYJ NASZĄ MISJĘ:
👶 Fundacja S.O.S. Obrony Poczętego Życia
   Nr konta: 32 1140 1010 0000 4777 8600 1001
   KRS: 0000215438
```

---

## Roadmapa implementacji

### ✅ Zamknięte (Supervisor 05, 2026-07-12)
- [x] Analiza SEO najlepszych praktyk (ChatGPT + Gemini audit)
- [x] Spec v2.2 finalny — 9 modułów, elastyczna długość body
- [x] Decyzja architektoniczna ADR-001 (PressAI jako silnik LLM)
- [x] Dispatch crimson-dev: endpoint `/api/external/generate-yt-description`
- [x] Dispatch vse-dev: integracja pipeline + `build_yt_description()`
- [x] Backupy obu repo zaplanowane w dispatchu (Krok 0)

### 🟡 W toku (workery, model: Gemini Pro 3.1 High)
- [ ] `crimson-void`: nowy format `youtube_description` w `article_formats.yaml`
- [ ] `crimson-void`: endpoint POST `/api/external/generate-yt-description`
- [ ] `video-seo-engine`: `fetch_yt_description_from_pressai()` w `pipeline.py`
- [ ] `video-seo-engine`: `build_yt_description()` w `inject.py`
- [ ] Deploy VSE API (`vse-api` container)

### 🔵 Roadmapa P2 (następna sesja po wdrożeniu P1)
- [ ] UI stopki: Textarea w dashboard → `YouTubeChannel.footer_text`
- [ ] Fix emoji (UTF-8 corruption) w dashboard UI
- [ ] M4B: cytaty z deep linkami (fuzzy match VTT → timestamp)

### 🔴 Roadmapa P3 (przyszłościowe)
- [ ] Auto-sync: webhook WordPress → refresh opisu YT gdy artykuł zaktualizowany
  - ƽródło: analiza VSE SEO audit (plik: `D:\Biblioteki\VSE\Rozwój plany\opis na youtube...txt`)
  - Mechanizm: diff-checker URL treści + prze-generowanie opisu przy zmianie
- [ ] YouTube A/B Title Testing: generowanie wariantów tytułów + thumbnail copy
  - Uwaga: YT Studio obsługuje A/B eksperymentalnie — generujemy warianty, user wkleja ręcznie

---

## Pliki kluczowe

| Plik | Repo | Rola |
|------|------|------|
| `backend/article_formats.yaml` | crimson-void | Format `youtube_description` |
| `backend/routers/external.py` | crimson-void | Endpoint generowania |
| `api/services/pipeline.py` | video-seo-engine | Wywołanie PressAI |
| `api/routers/inject.py` | video-seo-engine | `build_yt_description()` |
| `core/generator.py` | video-seo-engine | Fallback (stary hook) |

---

## Dispatche (Supervisor 05, 2026-07-12)

- crimson: `sonic-void/.agents/tasks/dispatches/2026-07-12_crimson_yt_endpoint.md`
- vse: `sonic-void/.agents/tasks/dispatches/2026-07-12_vse_yt_integration.md`

*Ostatnia aktualizacja: 2026-07-12 [Supervisor 05]*
