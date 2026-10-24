# HANDOFF — vse-reviewer → następna sesja (video-seo-engine)
**Data:** 2026-10-21 00:00 · **Poprzednia sesja:** conversation 47075134 (Claude, rola: reviewer/supervisor)

## ✅ Zamknięte (produkcja)
| Krok | Co | Commit | Snapshot/rollback TAG |
|---|---|---|---|
| Review | Krytyczny review dossier (`.agents/reports/2026-10-20_vse-reviewer_claude-architecture-review.md`) | `09faf10` | — |
| H0 | SEC2: usunięty fallback `all_keys[0]` w `_inject_via_plugin_endpoint` | `2593a92` | `20261020-203832` |
| K1+K2 | Generator: `clean_transcript` w Pythonie, `watching_page` single-pass, `LLM_TRUNCATED` logi, Gemini `max_output_tokens` | PR #2 merge `ca8bd7a` | `20261020-210157` |
| N1 | Nawigacja: `PublicHeader`, `not-found.tsx`, logo → `/` (smoke 8/8 PASS) | PR #3 merge `471d0a8` | `20261020-220032` |
| Y1 | YouTube publish: preselekcja kanału właściciela, widoczne błędy YT, czysty snippet, youtube_updated rzetelny | PR #6 merge `d07e3eb` | `20261021-195852` |

Wynik K1: watching_page 25 min → **54,8 s** (było ~300 s), 2737 tok. out, 0 nagłówków, brak truncation.

## 🛠 Infrastruktura (VPS)
- `/home/ubuntu/scripts/vse_snapshot.sh` — backup DB (backup_pre_deploy.sh) + docker tag obrazów vse-api/vse-web `:rollback-$TAG` + commit + kopia `.env`/compose (chmod 600), max 10 punktów.
- `/home/ubuntu/scripts/vse_rollback.sh <TAG> [--code]` / `--list` — przywraca obrazy bez rebuildu; `--code` = git reset + config. **DB nie jest cofana automatycznie** (ręcznie z `/home/ubuntu/backups/db/`).

## 📜 Zasady Właściciela (OBOWIĄZKOWE)
1. **Backup first** — każdy deploy przez `vse_snapshot.sh`; zawsze podać komendę rollbacku.
2. **Po kolei** — jedna zmiana na produkcji na raz; kod równolegle tylko na branchach, merge przez PR.
3. **Minimum kliknięć** — Właściciel zatwierdza każdy run_command. Workerzy: zero lokalnych npm/tsc/git; czytanie przez GitHub MCP / read_file; deploy = write_file skryptu + JEDEN run_command (scp; ssh bash). Build weryfikuje `docker build` na VPS.
4. W trywialnych rzeczach — tanie workery (Flash/Pro). Właściciel zdaje się na rekomendacje reviewera.

## 🔵 Następne (kolejność)
0. **Y1** — czeka na test Właściciela (nowe generowanie → Tylko YT → Portal+YT); jeśli błąd Google — diagnozować po treści błędu.
1. **K4** — `job_id` tworzony na starcie `run_generate()`, przekazywany do `_save_schema_to_job` (update po PK), nowy wiersz per kliknięcie, kolumna `publication_type`, **zakres `user_id` w `_save_schema_to_job` i `_get_cached_transcript_from_db`** (R1/R2 — warunek przed zapisem transkryptów OAuth do DB). `run_inject` ma brać profil z `req.portal_id`, nie z ostatniego joba.
2. **K3'** — `POST /v1/generate` → 202 + `job_id` (+ `request_id` idempotencji), wykonanie w tle (`asyncio.create_task` + sweeper osieroconych `processing`), dashboard polluje `GET /v1/jobs/{id}`; usunąć pętlę 524 opartą o historię. Osobny `ThreadPoolExecutor` dla LLM (R4), krótkie sesje DB (R3), atomowa rezerwacja quota (R5). NIE używać obecnego `/v1/generate/stream`.
3. **K5'** — publikacja WP: jeden silnik `core/injector.py` + `VseHmacAuth` (requests AuthBase) ↔ wtyczka filtr `determine_current_user` z HMAC(ts, nonce, body). Osobny `publish_secret` szyfrowany (SEC1: dziś `key_hash` z DB jest poświadczeniem do WP!). `PublishPlan`: layout vs `wp_post_format` rozdzielone, kategorie z `WpPortal` (hardcode prawy.pl usunąć), format/kategorie także przy update, tagi nazwa→ID. `/vse/v1/publish` deprecated. Wymaga aktualizacji wtyczki na prawy.pl.
4. **E2** — tabele `generations` + `transcript_cache` (scope public/owner), backfill.
5. Drobne: watching_page 136 słów (cel 150–250) — dostroić; `plugin.py /inject-data` sztywne `full_analysis`.

## ⚠️ Pułapki
- `dashboard-inner.tsx` duży — grep+sed, nie czytać całości. GitHub MCP: weryfikacja newlines po zapisie.
- Lokalny klon jest stale — źródło prawdy GitHub `main`.
- Szczegóły ryzyk R1–R7 i SEC1–SEC5: raport review (link wyżej).
