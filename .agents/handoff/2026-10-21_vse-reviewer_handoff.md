# HANDOFF — vse-reviewer → następna sesja (video-seo-engine)
**Data:** 2026-10-24 20:55 · **Poprzednia sesja:** conversation 298ad161-b28d-46f8-8c8d-2b5a6cb1382b / deploy k4.1 (rola: vse-dev-k4-1-deploy)

## 🧠 Namiary na Brain tej sesji (dla nowego agenta)
- **Główna sesja Supervisora/Reviewera:** `C:\Users\tomas2\.gemini\antigravity\brain\298ad161-b28d-46f8-8c8d-2b5a6cb1382b` (transkrypt: `.system_generated\logs\transcript.jsonl`)
- **Subagenci analityczni i wdrożeniowi w tej sesji:**
  - `38bcef8f-1a1a-47bc-b467-6c934d3421b5` — Audyt Roadmapy i gotowości do komercjalizacji (`vse-analyst-01`)
  - `a4aaac13-947e-4e11-ac5a-b7c9c63d5d9b` — Diagnoza braku miniatur WP, opisów SEO i `ImageObject` (`vse-analyst-thumbs`)
  - `250cb4b2-5c6f-45ee-9ab1-09b74dc42d0d` — Audyt zgodności z założeniami PressAI API / D11 / A7 (`vse-analyst-pressai`)
  - `5328ca09-248f-4665-937a-465e456d135e` — Audyt formatu wpisu WP (`video` vs `standard`) i wymogów Watch Page (`vse-analyst-watchpage`)
  - `7901ddfd-9e0b-4d14-8f78-4ef96ef3973b` — Audyt, deploy i testy K4.1 (`vse-dev-k4-1-deploy`)

## ✅ Zamknięte (produkcja)
| Krok | Co | Commit | Snapshot/rollback TAG |
|---|---|---|---|
| Review | Krytyczny review dossier (`.agents/reports/2026-10-20_vse-reviewer_claude-architecture-review.md`) | `09faf10` | — |
| H0 | SEC2: usunięty fallback `all_keys[0]` w `_inject_via_plugin_endpoint` | `2593a92` | `20261020-203832` |
| K1+K2 | Generator: `clean_transcript` w Pythonie, `watching_page` single-pass, `LLM_TRUNCATED` logi, Gemini `max_output_tokens` | PR #2 merge `ca8bd7a` | `20261020-210157` |
| N1 | Nawigacja: `PublicHeader`, `not-found.tsx`, logo → `/` (smoke 8/8 PASS) | PR #3 merge `471d0a8` | `20261020-220032` |
| Y1 | YouTube publish: preselekcja kanału właściciela, widoczne błędy YT, czysty snippet, youtube_updated rzetelny | PR #6 merge `d07e3eb` | `20261021-195852` |
| Quotes | Przywrócenie sekcji Cytaty w `ArticleTab.tsx` | PR #4 merge `c3e07f9` | `20261021-223954` |
| K4 | `job_id` na starcie `run_generate`, update po PK, kolumna `publication_type`, zakres `user_id` (R1/R2), `run_inject` bez "ostatniego joba" | PR #5 merge `89f24dc` | `20261024-173832` |
| K4.1 | Reużycie `job_id` w Local Runnerze (brak duplikatów), badge `publication_type` w `/historia`, przekazywanie `job_id` do `InjectModal` | PR #7 merge `7943870` | `20261024-184707` |

Wynik K1: watching_page 25 min → **54,8 s** (było ~300 s), 2737 tok. out, 0 nagłówków, brak truncation.

## 🛠 Infrastruktura (VPS)
- `/home/ubuntu/scripts/vse_snapshot.sh` — backup DB (backup_pre_deploy.sh) + docker tag obrazów vse-api/vse-web `:rollback-$TAG` + commit + kopia `.env`/compose (chmod 600), max 10 punktów.
- `/home/ubuntu/scripts/vse_rollback.sh <TAG> [--code]` / `--list` — przywraca obrazy bez rebuildu; `--code` = git reset + config. **DB nie jest cofana automatycznie** (ręcznie z `/home/ubuntu/backups/db/`).

## 📜 Zasady Właściciela (OBOWIĄZKOWE)
1. **Backup first** — każdy deploy przez `vse_snapshot.sh`; zawsze podać komendę rollbacku.
2. **Po kolei** — jedna zmiana na produkcji na raz; kod równolegle tylko na branchach, merge przez PR.
3. **Minimum kliknięć** — Właściciel zatwierdza każdy run_command. Workerzy: zero lokalnych npm/tsc/git; czytanie przez GitHub MCP / read_file; deploy = write_file skryptu + JEDEN run_command (scp; ssh bash). Build weryfikuje `docker build` na VPS.
4. W trywialnych rzeczach — tanie workery (Flash/Pro). Właściciel zdaje się na rekomendacje reviewera.
5. **Testy maszynowe i czytanie debugu po każdej zmianie** — po każdym wdrożeniu i próbie obowiązkowo uruchamiać testy maszynowe (pytest, curl, DB check) oraz czytać rozbudowane logi debugowania (`docker logs vse-api/vse-web`, logi `[generate]`/`[inject]`/D11, stan `transcript_jobs`).

## 🔵 Następne (kolejność)
1. **T1 — Przywrócenie miniatur WP (Featured Image), opisów SEO z PressAI Vision (D11) i schemy `ImageObject` JSON-LD (pełna diagnoza gotowa):**
   - *Root cause 1 (kolejność w `api/services/pipeline.py`):* `_describe_image_via_saas` (`POST /api/external/describe-image` w PressAI) jest wywoływane PRZED `generate_schema()`, przez co bez GSC wysyła puste `focus_keywords: []` i surowy tytuł YT. Trzeba przesunąć wywołanie ZA `generate_schema()`, przekazując `seo["focus_keyphrase"]` i `seo["post_title"]`, oraz dodać obsługę aliasów env `SAAS_API_URL`/`PRESSAI_API_URL` i `EXTERNAL_API_TOKEN`/`PRESSAI_EXTERNAL_TOKEN`.
   - *Root cause 2 (skasowany `TemporaryDirectory` i nadpisywanie danych PressAI w `core/injector.py`):* Po `run_generate()` katalog `tmp_dir` jest usuwany, więc podczas `POST /v1/inject` ścieżki `img["path"]` nie istnieją — `_upload_image_to_wp` musi pobierać obrazek przez HTTP z `img["url"]`. W `set_youtube_thumbnail` użyć 5 pól z PressAI (`filename`, `alt_text`, `title`, `caption`, `description`) zamiast sztywnego szablonu `{domain}-{yt_id}.jpg` oraz dodać `.rstrip('/')` do `wp_base_url`.
   - *Root cause 3 (`ImageObject` JSON-LD w `core/injector.py`):* `build_schema_jsonld` dodaje `"image": [ImageObject]` tylko gdy `uploaded_images` nie jest puste — trzeba budować pełny `@type: ImageObject` (`url`, `width`, `height`, `caption`, `name` z frazą kluczową) zawsze (z `uploaded_images` lub `seo["image_data"]`).
   - *Root cause 4 (Ścieżka wtyczki VSE 3.0 `api/routers/inject.py` + `plugins/vse-video-seo/vse-video-seo.php`):* `_inject_via_plugin_endpoint` nie wysyła `thumbnail_url` ani `image_data`, a `rest_external_publish` w PHP nie ma `media_sideload_image()` / `set_post_thumbnail()`. Trzeba przekazać miniaturę i opisy PressAI do wtyczki (lub wgrać przed publikacją) i ustawić Featured Image + metadane w Media Library.

2. **W1 — Format wpisu WP (`video` zamiast `standard`) oraz wymogi Watch Page (diagnoza z subagenta `5328ca09`):**
   - **Dlaczego posty zapisują się jako `standard` zamiast `video` (3 luki w kodzie):**
     1. *Ścieżka wtyczki VSE 3.0 (`api/routers/inject.py` L100–130 → `plugins/vse-video-seo/vse-video-seo.php` L480–530):* `_inject_via_plugin_endpoint` w `inject.py` (L116–128) w ogóle NIE wysyła pola `post_format` (z `req.post_format`) w payloadzie do `/wp-json/vse/v1/publish` (dodatkowo w L103 przekazuje wewnętrzny `post_format="full_article"` do `build_wp_post_html`, myląc układ HTML z formatem WP!). A `rest_external_publish` w `vse-video-seo.php` (L480–530) nie odbiera `post_format` i nigdy nie wywołuje `set_post_format($post_id, 'video')`.
     2. *Ścieżka natywna wtyczki WP (`plugins/vse-video-seo/vse-video-seo.php`):* `rest_create_post_from_video` (L400–435), `rest_import_history_item` (L450–480) oraz `rest_inject_data` (L345–380) nie wywołują `set_post_format($post_id, 'video')`.
     3. *Ścieżka aktualizacji przez REST API (`core/injector.py` L445–470, `update_post`):* przy tworzeniu nowego posta (`_create_wp_post` w `pipeline.py` L640) wysyłane jest `"format": post_format`, ale przy update istniejącego (`wp_post_id`) funkcja `update_post` wysyła tylko `{"content": content}` bez `"format": "video"`.
   - **Luki Watch Page (dla wszystkich 3 trybów: `watching_page`, `discover`, `full_analysis`):**
     - **TASK-01 (`api/routers/inject.py` & `vse-video-seo.php`):** Przekazywanie `post_format` (domyślnie `"video"`) w payloadzie `/wp-json/vse/v1/publish` i wywołanie `set_post_format($post_id, $post_format ?: 'video')` we wszystkich 4 funkcjach zapisu w `vse-video-seo.php` (`rest_external_publish`, `rest_create_post_from_video`, `rest_import_history_item`, `rest_inject_data`).
     - **TASK-02 (`core/injector.py` L445–470):** Dodanie `"format": "video"` do `update_post` przy aktualizacji istniejącego wpisu.
     - **TASK-03 (Zero CLS playera — `core/injector.py` L365–375 & L705–715):** Dodanie inline `style="aspect-ratio:16/9;width:100%;max-width:100%;"` na kontenerze embeda YouTube (jak w `vse-video-seo.php` L170–185).
     - **TASK-04 (Schema.org Watch Page — `core/injector.py` L280–360):** Rozszerzenie `@graph` JSON-LD o `Article`/`NewsArticle` (z relacją `video` → `VideoObject`), `BreadcrumbList` oraz `SeekToAction` w `VideoObject.potentialAction` (zamiast samego `WatchAction`).
     - **TASK-05 (Helpful Content / eliminacja Thin Content w `watching_page` + `<!--more-->` w `discover` — `core/generator.py` L120, L230, L320, L676–705 & `core/injector.py` L360–390):** Rozbudowa `watching_page` z 1–2 krótkich akapitów bez cytatów do pełnoprawnego Watch Page (unikalny wstęp, rozwinięcie z H2/H3, 1–2 cytaty wymagane, podsumowanie/wnioski, FAQ, rozdziały z `seekTo`); poprawa pozycji `<!--more-->` w `discover`.
     - **TASK-06 (Linkowanie wewnętrzne / Orphan Page prevention — `core/generator.py` L250–320 & `core/injector.py`):** Przekazywanie `internal_links` także do Pass 2 (`_generate_article_fallback`) oraz deterministyczna sekcja powiązanych artykułów/materiałów, gdy linki nie weszły w treść.

3. **K3'** — async `POST /v1/generate` → 202 + `job_id` + polling `GET /v1/jobs/{id}`, eliminacja pętli 524.
4. **K5' + SEC1** — jeden silnik publikacji WP + szyfrowany `publish_secret` z HMAC (zamiast `key_hash`), usunięcie hardcode `prawy.pl`, `plugin.py /inject-data` publication_type.
5. **E2 + Checklist komercjalizacji (według `ROADMAP.md` v2.2 z 20.10.2026):** tabele `generations` + `transcript_cache`, synchronizacja przestarzałego `README.md` (z 16.10) i `docs/ROADMAP.md` (z 14.07) do `ROADMAP.md` v2.2, przełączenie Stripe na `sk_live_`, test polowy wtyczki WP v3.0.0 poza `prawy.pl`.

## ⚠️ Pułapki
- `dashboard-inner.tsx` duży — grep+sed, nie czytać całości. GitHub MCP: weryfikacja newlines po zapisie.
- Lokalny klon jest stale — źródło prawdy GitHub `main`.
- Szczegóły ryzyk R1–R7 i SEC1–SEC5: raport review (link wyżej).
