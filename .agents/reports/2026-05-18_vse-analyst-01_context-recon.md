# Raport: Rekonstrukcja Kontekstu — video-seo-engine (13–18 maja 2026)

> **Agent:** vse-analyst-01 | video-seo-engine | 2026-05-18T20:35 CEST
> **Dispatch:** DISPATCH-VSE-ANALYST-01-20260518
> **Źródła:** git log, core/generator.py, core/injector.py, batch_inject.py, batch_seo_generate.py, heartbeat.json, brain dirs (79798d9e, dd56b234, 4c0ac986), .agents/reports/*

---

## Sekcja 1: TIMELINE — co kiedy

### Faza 0 — prehistoria (do 12.05.2026, shadow-perihelion)
- W shadow-perihelion działał legacy pipeline: `test_full_seo_v4.py` (generator) + `inject_rest_v5.py` (injector) + `batch_inject.py` + `batch_seo_generate.py`
- **Stan na 12.05 wieczór (brain audit, konwersacja 4c0ac986):**
  - ~200/210 JSONów SEO wygenerowanych przez Gemini
  - **44 posty zainjektowane** do WordPress (prawy.pl)
  - ~163 postów do injekcji w kolejce
  - Batch-worker-02 zajęty, operacje przez stellar-relay/PowerShell

### Faza 1 — bootstrap video-seo-engine (2026-05-13)
| Czas | Commit | Działanie |
|------|--------|-----------|
| 12:31 | `init` | Repo created, AGENTS.md, README, heartbeat |
| 12:34 | `70d3dbc` | Migracja `fetcher.py` z shadow-perihelion |
| 12:34 | `3d1e4a8` | Migracja `matcher.py` z shadow-perihelion |
| 12:36 | `5b89d78` | Migracja `sitemap.py` z shadow-perihelion |
| 12:37 | `f31a913` | Knowledge base — architecture doc |
| 12:38 | `bee365b` | Bootstrap complete ✅ |
| 19:55 | `3f9c243` | **`core/generator.py`** — migracja z test_full_seo_v4.py |
| 19:57 | `cde3bb2` | **`core/injector.py`** — migracja z inject_rest_v5.py |
| 19:58 | `5e67aa5` | `.env.example` rozszerzony |
| 19:58 | `f75e2a0` | `cli/main.py` — subkomendy `generate` + `inject` |
| 23:53 | `f6fef0f` | fix: CP1250 UnicodeEncodeError (Windows ASCII fallback) |
| 23:52 | `5cfee39` | **WALIDACJA E2E: U9HLRRXs5EU → WP#119445 → REST 200** ✅ |

### Faza 2 — Channel Monitor (2026-05-14)
| Czas | Commit | Działanie |
|------|--------|-----------|
| 00:22 | `58a9ff6` | `core/monitor.py` — YouTube Channel Monitor |
| 00:22 | `f6f0a5c` | `cli/main.py` — `vse watch` subcommand |
| 00:22 | `3435596` | Registry: U9HLRRXs5EU.json (retroaktywny) |
| 00:22 | `ea147eb` | `.env.example` — CHANNEL_ID + MONITOR_INTERVAL |
| 00:23 | `62ac145` | Knowledge/video-seo-pipeline.md — Fazy 1-7 |
| 00:27 | `8ea08ea` | Heartbeat: DISPATCH-03 done, Faza 2 complete ✅ |

### Faza 2b — Finetuning SEO + YouTube admin (2026-05-16)
| Czas | Commit | Działanie |
|------|--------|-----------|
| 19:07 | `4705b56` | `core/yt_admin.py` — YouTube OAuth, description writer, footer (+485 linii!) |
| 19:09 | `1dfb6fa` | `core/monitor.py` — smart scheduling (5-37min delay + premiere detection) (+224 linie) |
| 19:11 | `fa5ca69` | `cli/main.py` — `vse update-yt` + publish-delay args to `vse watch` (+130 linii) |
| 20:15 | `2789562` | **`core/injector.py` — thumbnail ALT=focus_keyphrase + RankMath meta** (+50 linii) |

**Ostatni commit w repo: 2026-05-16T20:15 CEST — 2 dni temu. Brak aktywności 17-18 maja.**

---

## Sekcja 2: STAN TECHNICZNY — co jest gotowe

### Moduły core/ — stan na HEAD (commit 2789562)

| Moduł | Status | Wersja | Zwalidowane |
|-------|--------|--------|-------------|
| `core/fetcher.py` | ✅ Done | Zmigrowane z shadow-perihelion | Pośrednio (przez stary pipeline) |
| `core/matcher.py` | ✅ Done | Zmigrowane z shadow-perihelion | Pośrednio |
| `core/generator.py` | ✅ Done | Zmigrowane + ulepszone | **TAK — U9HLRRXs5EU (13.05)** |
| `core/injector.py` | ✅ Done v2 | + RankMath + ALT thumbnail | **TAK — U9HLRRXs5EU (13.05)** |
| `core/sitemap.py` | ✅ Done | Zmigrowane z shadow-perihelion | Pośrednio |
| `core/monitor.py` | ✅ Done v2 | Smart scheduling + premiere detection | Zaimpl., NIE przetestowany live |
| `core/yt_admin.py` | ✅ Done | OAuth + description writer + footer | Zaimpl., NIE przetestowany live |

### Narzędzia legacy (root dir) — zachowane, AKTYWNE

| Plik | Status | Uwaga |
|------|--------|-------|
| `batch_seo_generate.py` | Aktywny | Używa starych importów z generator.py shadow-perihelion |
| `batch_inject.py` | Aktywny | **Importuje z `inject_rest_v5.py` i hardcoded path Windows** `D:\Biblioteki\prawy.pl` |
| `inject_rest_v5.py` | Legacy | Oryginał z shadow-perihelion — NIE używać bezpośrednio |

> ⚠️ **batch_inject.py jest ZŁAMANY na WSL2** — ma `from inject_rest_v5 import ... WP_URL` + ścieżkę Windows `D:\Biblioteki\prawy.pl\seo_results_v5`. Na Linux nie zadziała bez refactoru.

### CLI — gotowe komendy

```bash
vse fetch --video <YT_ID>          # pobierz transkrypt
vse match                          # dopasuj WP posts
vse generate --batch matches.json  # Gemini generation
vse inject --batch seo_results/    # WordPress injection
vse watch --channel UC...          # Channel Monitor
vse update-yt --video <YT_ID>      # Aktualizuj opis YT
```

### Testy automatyczne

- **pytest: BRAK** — nie ma żadnych plików w `tests/`. Znany gap. Dispatch-02 zakładał pytest jako "Następny Krok", nigdy nie wykonany.

---

## Sekcja 3: STANDARD ARTYKUŁU — co wypracowano

### Geneza — shadow-perihelion / inject_rest_v5.py

Standard artykułu WIDEO na prawy.pl to zestaw bloków Gutenberga + JSON-LD, który Supervisor określa jako "artykułowy standard redakcyjny". Wypracowany empirycznie w shadow-perihelion przez batch-worker-02 podczas injekcji 44 postów.

### Struktura blokowa artykułu (build_post_content w injector.py)

```
1. Lead block         → <!-- wp:paragraph --><p>{lead}</p><!--more-->
2. YouTube embed      → <!-- wp:embed --> z parametrami Gutenberg
3. Rozdziały nagrania → <!-- wp:list --><ul class="prawy-chapters-list">
                        <li><a class="prawy-chapter" data-time="{sec}">MM:SS — Tytuł</a></li>
4. Article body       → <!-- wp:html --> z AI-generated HTML (3-5 <p>, 1-2 <h2>)
5. Kluczowe cytaty    → <!-- wp:quote --> z blockquote + cite ze znacznikiem czasu
6. FAQ                → <!-- wp:html --> z <details>/<summary> (kolapsowalne)
7. JSON-LD schemas    → VideoObject + Clip[] + FAQPage (+ Quotation zachowany legacy)
8. Player JS          → seekTo via postMessage + eventListenery .prawy-chapter
```

### Co wstrzykuje injector.py do WP REST API

| Pole WP | Wartość | Standard |
|---------|---------|----------|
| `content` | Pełna struktura bloków (8 sekcji) | ✅ |
| `excerpt` | Lead bez HTML (`_strip_html(lead)`) | ✅ |
| `meta.rank_math_focus_keyword` | focus_keyphrase z Gemini | ✅ Dodane 16.05 |
| `meta.rank_math_description` | Lead[:157]... | ✅ Dodane 16.05 |
| `meta.rank_math_title` | seo_title z Gemini | ✅ Dodane 16.05 |
| `featured_media` | Thumbnail YouTube (maxresdefault) | ✅ |
| Thumbnail ALT text | `{focus_keyphrase} \| Prawy TV` | ✅ Dodane 16.05 |

### Ostatnie prace w tym obszarze (commit 2789562, 16.05)

Kluczowy commit `fix: thumbnail ALT=focus_keyphrase + RankMath meta` zamknął **trzy luki SEO**:

1. **ALT text thumbnailów** — wcześniej pusty, teraz `focus_keyphrase | Prawy TV`
2. **RankMath integration** — wcześniej plugin był ignorowany przez REST API, teraz `rank_math_focus_keyword`, `rank_math_description`, `rank_math_title` są wstrzykiwane jako WP post meta
3. **Graceful fallback** — jeśli nie ma focus_keyphrase, używa `seo_title[:80]`

### Czego brakuje w stosunku do pełnego standardu redakcyjnego

- **Brak automatycznego ustawiania kategorii/tagów** — injector nie ustawia `categories` ani `tags` przez REST API (są generowane przez Gemini, ale nie wstrzykiwane)
- **Brak aktualizacji tytułu posta** — `seo_title` z Gemini idzie do RankMath, ale nie nadpisuje `post_title` WP (to może być celowe — nie chcemy zmieniać oryginalnego tytułu)
- **Klucze Kurier365** — batch_inject.py jest hardcoded na prawy.pl; multi-portal wymaga refactoru

---

## Sekcja 4: CO ZOSTAŁO NA STOLE

### A) Batch injekcja 210 postów — NIEZAKOŃCZONA

- **Stan przed VSE:** 44/210 wstrzykniętych (shadow-perihelion batch-worker-02)
- **Stan po:** Brak nowej injekcji batch w VSE — nie przeprowadzono `vse inject --batch`
- **Problem:** `batch_inject.py` jest złamany na WSL2 (hardcoded Windows path + import z `inject_rest_v5.py`)
- **Rzeczywista liczba do injekcji:** ~166 postów (210 − 44 wstrzykniętych)
- **JSON-e SEO:** status nieznany — nie wiadomo ile z 210 ma JSON po przeniesieniu na WSL2

### B) Channel Monitor — wymaga CHANNEL_ID

- `core/monitor.py` i `vse watch` są gotowe, ale **nigdy nie uruchomione live**
- Bloker: brak `CHANNEL_ID` Prawy TV w `.env` (format `UCxxxx`)
- Bloker 2: brak `YT_API_KEY` (YouTube Data API v3) w konfiguracji

### C) pytest — zero testów

- Żaden moduł `core/` nie ma testu jednostkowego
- Ryzyko: każda zmiana może złamać pipeline bez widzialnych objawów

### D) yt_admin.py — nie przetestowany produkcyjnie

- Duży moduł (499 linii) do zarządzania opisami YouTube przez OAuth
- OAuth credentials są w `yt_oauth_result.json` + `client_secret.json` (gitignore? — sprawdzić!)
- Brak dowodu na live run po deploymencie

### E) Otwarte pytania techniczne

1. Ile JSONów SEO jest dostępnych na WSL2? (były generowane na Windows `D:\Biblioteki\prawy.pl`)
2. Czy `seo_results_v5/` został skopiowany na WSL2?
3. Czy `prawy_tv_matches.json` (210 par WP↔YT) jest dostępny w repo lub lokalnie?
4. Czy `client_secret.json` w root repo to wyciek danych? (jest w gitignore czy nie?)

---

## Sekcja 5: REKOMENDACJA — od czego zacząć

### Priorytet #1: Uruchomienie batch injekcji pozostałych ~166 postów

To jest **największa wartość biznesowa zalegająca na stole**. 44/210 postów to 21% execution rate — zostało 79%.

**Zalecana sekwencja dla vse-dev-01:**

1. **Audit data availability** — sprawdzić czy `seo_results_v5/` i `prawy_tv_matches.json` są dostępne pod WSL2 (mogą być tylko na starym Windows)
2. **Fix batch_inject.py** — przepisać na używanie `core/injector.py` zamiast `inject_rest_v5.py`, usunąć hardcoded Windows path, dodać `--seo-dir` arg
3. **Przeprowadzić `vse inject --batch seo_results/`** z `--sleep 30 --dry-run` najpierw
4. **Aktywować Channel Monitor** z CHANNEL_ID + YT_API_KEY po udanym batchu

**Alternatywa dla Stratega:** Jeśli dane (JSONy SEO) nie przeżyły migracji z Windows → zamówić regenerację przez `vse generate --batch prawy_tv_matches.json` (Gemini API jest gotowe).

---

## Załącznik: Mapa commitów VSE (13-16 maja)

```
2026-05-12  ea4d5f7  Create README.md (GitHub init)
2026-05-13  d5efd2c  init: heartbeat
2026-05-13  0ac923a  docs: README
2026-05-13  6e7c01e  init: AGENTS.md
2026-05-13  70d3dbc  feat: migrate fetcher.py
2026-05-13  3d1e4a8  feat: migrate matcher.py
2026-05-13  5b89d78  feat: migrate sitemap.py
2026-05-13  4a82742  init: core scaffolding
2026-05-13  142fa92  init: .gitignore, .env.example, requirements.txt
2026-05-13  f31a913  docs: knowledge base
2026-05-13  dbdd8c8  report: bootstrap complete
2026-05-13  bee365b  heartbeat: bootstrap done ✅
2026-05-13  86c1310  dispatch: Migrate core generator and injector
2026-05-13  cda7162  feat: migrate core pipeline scripts v5.3
2026-05-13  0dd1a4d  feat: migrate match + matches inventory
2026-05-13  71bcb12  dispatch: VSE-ARCHITECT-02
2026-05-13  dba7014  fix: KROK 0 protocol
2026-05-13  4d7a707  heartbeat: DISPATCH-02 in progress
2026-05-13  3f9c243  feat: GENERATOR.PY ← test_full_seo_v4.py
2026-05-13  cde3bb2  feat: INJECTOR.PY ← inject_rest_v5.py
2026-05-13  5e67aa5  feat: .env.example extended
2026-05-13  f75e2a0  feat: cli/main.py generate + inject
2026-05-13  9f3e0ba  heartbeat: DISPATCH-02 done
2026-05-13  8252d1a  report: DISPATCH-02 Faza1 complete
2026-05-13  cb10ced  dispatch: VSE-VALIDATE-01
2026-05-13  f20dc44  heartbeat: validation start
2026-05-13  f6fef0f  fix: CP1250 Unicode fix
2026-05-13  5cfee39  heartbeat: VALIDATE-01 done ✅
2026-05-13  81968ca  report: VALIDATE-01 sukces
2026-05-14  3435596  registry: U9HLRRXs5EU
2026-05-14  ea147eb  feat: CHANNEL_ID + MONITOR_INTERVAL
2026-05-14  58a9ff6  feat: MONITOR.PY ← Faza 2
2026-05-14  f6f0a5c  feat: vse watch + vse fetch
2026-05-14  62ac145  docs: knowledge Fazy 1-7
2026-05-14  8ea08ea  heartbeat: DISPATCH-03 done ✅
                     --- (przerwa 2 dni) ---
2026-05-16  4705b56  feat: YT_ADMIN.PY (OAuth + desc writer)
2026-05-16  1dfb6fa  feat: monitor.py smart scheduling
2026-05-16  fa5ca69  feat: vse update-yt + publish-delay
2026-05-16  2789562  fix: THUMBNAIL ALT + RANKMATH META ← ostatni commit ✅
```

---

*[vse-analyst-01 | video-seo-engine | 2026-05-18T20:40 CEST] — raport kompletny*
