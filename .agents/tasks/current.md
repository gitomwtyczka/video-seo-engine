# Current Tasks (Stan na 21.10.2026 — K4 Job Per Click)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1, WP Plugin v3.0 + Limity 5/30/110/250 + Top-Up 99/249/699 + Niezawodność Napisów & Blokada Anty-Konfabulacyjna + UX `/ustawienia` + K4 Job Per Click)
- [x] **Zadanie K4 — Job per click, kolumna publication_type, scoping user_id (R1/R2) (PR #5):**
  - **Wiersz per kliknięcie:** `run_generate()` na starcie tworzy nowy rekord w `transcript_jobs` ze statusem `processing` i `publication_type`, eliminując problem pojedynczego wiersza w historii dla wielu analiz tego samego filmu.
  - **Aktualizacja po PK:** `_save_schema_to_job()` aktualizuje konkretny rekord po `job_id`, eliminując nadpisywanie w miejscu poprzednich generacji.
  - **Kolumna `publication_type`:** dodana do `TranscriptJob`, `JobResponse`, `FullJobResponse`, `HistoryJobResponse` z zero-downtime migracją (`ALTER TABLE transcript_jobs ADD COLUMN IF NOT EXISTS publication_type VARCHAR(50);`) i backfillem w `api/main.py`, `api/migrate.py` i Alembic.
  - **Scoping `user_id` (R1/R2):** `_save_schema_to_job()` i `_get_cached_transcript_from_db()` filtrują po `user_id`, zapobiegając wyciekowi prywatnych transkryptów (OAuth) między kontami.
  - **Deterministyczna rezolucja w `run_inject`:** profil i schema pobierane z `portal_id` lub `job_id` (z `req.job_id`), bez sięgania po "ostatni job".
  - **Weryfikacja:** 7/7 testów w `tests/test_k4_job_per_click.py` PASS, 13/13 w `tests/test_generator.py` PASS, `py_compile` PASS.
- [x] **Przebudowa UX `/ustawienia` + Język Białoruski (`be`) + Ujednolicenie limitu 50 portali WP w Agency (`3e0cb38`, `59ca091`, `c17a7a6`):**
  - Przebudowa `web/src/app/ustawienia/page.tsx` na 4 logiczne karty oraz wsparcie języka białoruskiego.
- [x] **Wdrożenie KROK A+B+C: Limity 5/30/110/250 + Top-Up 99/249/699 PLN + OAuth Channel Match + Instant Runner Wakeup + Blokada Anty-Konfabulacyjna:**
  - Synchronizacja limitów planów i cen pakietów Top-Up.
  - Niezawodność transkrypcji YouTube OAuth Channel Match + Multi-Track Fallback.
  - Twarda blokada anty-konfabulacyjna (HTTP 422 + 0 kredytów) przy braku transkryptu.

---

## 🟡 W toku
- [ ] **Wdrożenie PR #5 na produkcję (dla Właściciela):** Merge PR #5 do `main`, wykonanie `/home/ubuntu/scripts/vse_snapshot.sh` i deploy obrazu `vse-api`.

---

## 🔵 Następne (Master Roadmap v2.2)
- [ ] **K3'** — `POST /v1/generate` → 202 + `job_id` (+ idempotency), wykonanie w tle (`asyncio.create_task`), polling `GET /v1/jobs/{id}`.
- [ ] **K5'** — publikacja WP: jeden silnik `core/injector.py` + `VseHmacAuth` ↔ wtyczka filtr `determine_current_user`.
- [ ] **E2** — tabele `generations` + `transcript_cache` (scope public/owner), backfill.
- [ ] **Priorytet 1 — Test praktyczny Wtyczki WordPress v3.0.0 (`plugins/vse-video-seo/`) na żywych portalach.**
- [ ] **Priorytet 2 — Przełączenie Stripe z `sk_test_` na `sk_live_`.**
