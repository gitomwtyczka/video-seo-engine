# DISPATCH-VSE-ARCHITECT-02 — App Build + Roadmap Update

**Wystawia:** Supervisor 01  
**Do:** vse-architect-01  
**Data:** 2026-05-13  
**Priorytet:** HIGH  
**Repo:** `video-seo-engine` | branch: `main`

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Callsign:** `vse-architect-01`  
**Workspace:** `video-seo-engine`  
**Model sugerowany:** Gemini 2.5 Pro (złożona migracja kodu)

**0. Wczytaj blok systemowy (skills + file bridge + protokół):**
```
view_file → /home/tobroz/projects/sonic-void\.agents\protocols\dispatch-system-block.md
```

**1. Napisz heartbeat** (GitHub MCP — nie lokalnie):
```
mcp_github_create_or_update_file:
  repo: video-seo-engine | branch: main
  path: .agents/heartbeat.json
  content: {"callsign":"vse-architect-01","status":"working","current_task":"Faza 1 core migration","timestamp":"[ISO]"}
  message: "heartbeat: start [vse-architect-01]"
```
Jeśli plik już istnieje → najpierw pobierz SHA przez `mcp_github_get_file_contents`, potem zaktualizuj.

**2. Protokół callsign** — każda odpowiedź MUSI zaczynać się i kończyć:
```
[vse-architect-01 | video-seo-engine DD.MM.YYYY HH:MM] online
... treść ...
[vse-architect-01 | video-seo-engine DD.MM.YYYY HH:MM] — status
```
Brak callsignu = naruszenie protokołu.

**3. Reguły shellowe (ABSOLUTNE — nie łam):**
1. `run_command` = ZABLOKOWANY (Windows sandbox). Nie próbuj. Nigdy.
2. Komendy lokalne → run_command (bash natywny WSL2)
3. Pliki repo → **tylko** GitHub MCP `create_or_update_file` (NIE write_to_file — zawiesza się)
4. `mcp_stellar-relay_*` MCP tools = ZAKAZ bezpośredniego użycia (hang FastMCP)

**4. Vitals** — śledź V1-V5 od początku. Gdy 2+ 🔴 → STOP + zapisz handoff.

**5. Twój deliverable:** działająca migracja `core/generator.py` + `core/injector.py` + zaktualizowany CLI + raport do Supervisora.

**6. Scope:** Jesteś Architektem. Implementujesz moduły core. Nie wychodzisz poza Fazę 1.

---

## Kontekst — co się zmieniło od DISPATCH-01

### ✅ Nowe skrypty w repo (root)
Supervisor 01 zmigował realne skrypty produkcyjne do root repo (commit `cda7162`, `0dd1a4d`):

| Plik w root | Cel | Akcja |
|---|---|---|
| `inject_rest_v5.py` | → `core/injector.py` | Zastąp placeholder realnym kodem |
| `test_full_seo_v4.py` | → `core/generator.py` | Zastąp placeholder realnym kodem |
| `batch_seo_generate.py` | → `cli/batch_generate.py` | Nowy CLI wrapper |
| `batch_inject.py` | → `cli/batch_inject.py` | Nowy CLI wrapper |
| `match_prawy_tv.py` | → `core/matcher.py` aktualizacja | Scal z istniejącym |
| `youtube_fetch.py` | → `core/fetcher.py` aktualizacja | Scal z istniejącym |

**UWAGA:** Pliki w root to oryginalne skrypty z D:\Biblioteki\prawy.pl — nie architektura modułowa. Twoim zadaniem jest migracja ich logiki do modułów `core/` z zachowaniem architektury wieloportalowej.

---

## Odzyskana wiedza — roadmap z zaginionych sesji

Sesje z 07-12.05.2026 (częściowo utracone) zawierały spójny roadmap. Oto co było ustalone:

### Faza 1 — Core Pipeline (PRAWY.PL) ← w toku
- [x] VideoObject schema v5.3 — duration, timezone, viewCount
- [x] Chapters (Clip) z fuzzy matching VTT  
- [x] FAQPage z transkryptu
- [x] Batch processing 213+ postów
- [ ] `core/generator.py` — placeholder → realny kod (**to zadanie**)
- [ ] `core/injector.py` — placeholder → realny kod (**to zadanie**)

### Faza 2 — Channel Monitor
- `core/monitor.py` — YouTube Channel Monitor
- Automatyczne wykrywanie nowych filmów (polling co 1h)
- Auto-tworzenie draft postów w WP z embeddednym video
- Triggerowanie pipeline v5.3 na nowych filmach

### Faza 3 — Multi-Portal
- Portal Scanner dla Kurier365, BiznesCiti
- Unified `config/portals.yaml` — każdy portal: WP_URL, YT_CHANNEL_ID, CATEGORY_ID
- Adapter pattern: jeden pipeline, wiele portali

### Faza 4 — Video Sitemap
- `core/sitemap.py` już istnieje — do dopracowania
- Auto-regeneracja: `save_post` WordPress hook (via WP plugin)
- Cross-category discovery (nie tylko Prawy TV)

### Faza 5 — PressAI SaaS Module
- REST API wrapper nad pipeline
- Endpoint: `POST /api/v1/process-video` → async job
- Wynik do crimson-void jako moduł PressAI

### Faza 6 — WordPress Plugin (standalone)
- Dystrybucja jako self-contained WP plugin
- GUI w WP admin: kolejka filmów, status injekcji, video sitemap stats

### Faza 7 — YouTube Description Sync
- YouTube Data API v3 OAuth2 (Manager scope)
- GCP project: `antigravity-mcp-keys` (już istnieje)
- Opis YT aktualizowany po wygenerowaniu SEO (chapters jako timestamps)
- **BLOKER:** wymaga OAuth2 setup — osobny dispatch

---

## Zadania dla tego dispatchu (Faza 1 — dokończenie)

### TASK-1: Migracja `core/generator.py`
Przeczytaj `test_full_seo_v4.py` z root repo.  
Zastąp placeholder w `core/generator.py` realną logiką:
- `parse_vtt_full()` — parser VTT z anchor matching
- `find_anchor_in_vtt()` — fuzzy matching
- `generate_seo_v4()` — Gemini call z promptem v5.3
- `format_duration_iso()` — ISO 8601 converter
- Zachowaj architekturę multi-portal (parametry konfigurowalne, nie hardcoded paths)
- Gemini model: `gemini-2.5-flash` (aktualne)

### TASK-2: Migracja `core/injector.py`
Przeczytaj `inject_rest_v5.py` z root repo.  
Zastąp placeholder w `core/injector.py`:
- `build_schema_jsonld()` — VideoObject + Clip + FAQPage
- `build_post_content()` — WP blocks z seekTo JS
- `update_post()` — REST API PATCH
- `set_youtube_thumbnail()` — thumbnail upload + dedup
- `get_youtube_view_count()` — z `YT_API_KEY` env var
- `get_post_date()` — fetch upload date z WP
- Usuń hardcoded credentials — wszystko z `.env`

### TASK-3: Zaktualizuj `.env.example`
Dodaj wszystkie wymagane zmienne:
```
GEMINI_API_KEY=
YT_API_KEY=
WP_URL=https://prawy.pl
WP_USER=
WP_APP_PASS=
PORTAL=prawy  # prawy | kurier365 | biznesciti
```

### TASK-4: CLI update
Zaktualizuj `cli/main.py` aby obsługiwał:
```bash
vse generate --video <yt_id>          # single video
vse generate --batch prawy_tv_matches.json
vse inject --video <yt_id> --wp-id <id>
vse inject --batch seo_results/
vse match --portal prawy
vse sitemap --portal prawy
```

### TASK-5: Zaktualizuj wiedzę + roadmap
Zaktualizuj `.agents/knowledge/video-seo-pipeline.md`:
- Dodaj sekcję Roadmap Fazy 1-7 (z tego dispatchu)
- Zaktualizuj status operacyjny: 6 live, 156 w kolejce

---

## Schema Standard — nie zmieniaj
Zachowaj wszystkie decyzje z `video-seo-pipeline.md`:
- Quotation: NIE dodawać nowych
- BroadcastEvent: oddzielny pipeline
- SeekToAction: zachować dla completeness
- `gemini-2.5-flash` jako model

---

## Raportowanie po sesji
1. Heartbeat `status: done` w `video-seo-engine/.agents/heartbeat.json` (GitHub MCP)
2. Raport do `video-seo-engine/.agents/reports/YYYY-MM-DD_vse-architect-01_faza1-complete.md`
3. Raport do `sonic-void/.agents/reports/inbox/YYYY-MM-DD_vse-architect-01_faza1-complete.md`

---

*Supervisor 01 | sonic-void | 2026-05-13*
