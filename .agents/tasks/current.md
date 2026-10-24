# Current Tasks (Stan na 24.10.2026 — K4.1 Deploy + T1 & W1 Priorytet)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1, WP Plugin v3.0 + Limity 5/30/110/250 + Top-Up 99/249/699 + Niezawodność Napisów & Blokada Anty-Konfabulacyjna + UX `/ustawienia` + K4 Job Per Click + K4.1 Gaps)
- [x] **Zadanie K4.1 — Reużycie job_id w Local Runnerze, publication_type w /historia, job_id w InjectModal (PR #7, merge `7943870`, TAG `20261024-184707`):**
  - **Reużycie `job_id`:** `_create_transcript_job()` i `_fetch_transcript_local_runner()` przyjmują `existing_job_id: Optional[str] = None`. Przy wywołaniu z `run_generate()` istniejący job jest aktualizowany (`status='pending'`), eliminując problem podwójnych wierszy w `transcript_jobs`.
  - **Filtrowanie w `/historia`:** `GET /v1/jobs/history` filtruje techniczne sieroty `status='fetched'` bez wyników SEO za pomocą warunku `or_(TranscriptJob.schema_data.isnot(None), TranscriptJob.status.in_(["done", "failed", "processing"]))`.
  - **Badge `publication_type`:** dodany estetyczny badge publikacji w `web/src/app/historia/page.tsx` (`🎬 Strona filmu`, `🔥 Discover`, `📰 Pełna analiza` itd.).
  - **Przekazywanie `job_id` do `InjectModal`:** `activeJobId` z dashboardu jest przekazywany do `InjectModal` i wysyłany w ciele requestu `POST /v1/inject`.
  - **Weryfikacja:** 20/20 testów (pytest) PASS, HTTP checks PASS, DB status PASS.
- [x] **Zadanie K4 — Job per click, kolumna publication_type, scoping user_id (R1/R2) (PR #5, merge `89f24dc`, TAG `20261024-173832`):**
  - **Wiersz per kliknięcie:** `run_generate()` na starcie tworzy nowy rekord w `transcript_jobs` ze statusem `processing` i `publication_type`, eliminując problem pojedynczego wiersza w historii dla wielu analiz tego samego filmu.
  - **Aktualizacja po PK:** `_save_schema_to_job()` aktualizuje konkretny rekord po `job_id`, eliminując nadpisywanie w miejscu poprzednich generacji.
  - **Kolumna `publication_type`:** dodana do `TranscriptJob`, `JobResponse`, `FullJobResponse`, `HistoryJobResponse` z zero-downtime migracją i backfillem.
  - **Scoping `user_id` (R1/R2):** `_save_schema_to_job()` i `_get_cached_transcript_from_db()` filtrują po `user_id`, zapobiegając wyciekowi prywatnych transkryptów (OAuth) między kontami.
  - **Deterministyczna rezolucja w `run_inject`:** profil i schema pobierane z `portal_id` lub `job_id` (z `req.job_id`), bez sięgania po "ostatni job".
- [x] **Quotes — Przywrócenie sekcji Cytaty w `ArticleTab.tsx` (PR #4, merge `c3e07f9`, TAG `20261021-223954`):**
- [x] **Przebudowa UX `/ustawienia` + Język Białoruski (`be`) + Ujednolicenie limitu 50 portali WP w Agency (`3e0cb38`, `59ca091`, `c17a7a6`):**
- [x] **Wdrożenie KROK A+B+C: Limity 5/30/110/250 + Top-Up 99/249/699 PLN + OAuth Channel Match + Instant Runner Wakeup + Blokada Anty-Konfabulacyjna.**

---

## 🟡 W toku
- [ ] **T1 — Przywrócenie miniatur WP (Featured Image), opisów SEO z PressAI Vision (D11) i schemy `ImageObject` JSON-LD:**
  - Pełna diagnoza i 4 root causes opisane w `.agents/handoff/2026-10-21_vse-reviewer_handoff.md`.

---

## 🔵 Następne (Master Roadmap v2.2)
- [ ] **1. T1 — Przywrócenie miniatur WP, PressAI Vision (D11) i ImageObject JSON-LD.**
- [ ] **2. W1 — Format wpisu WP (`video` zamiast `standard`) oraz wymogi Watch Page (TASK-01 do TASK-06):**
  - Rozwiązanie problemu formatu `standard` (wtyczka VSE 3.0, update_post).
  - Wymogi Watch Page: zero CLS playera (aspect-ratio 16/9), schema Article/SeekToAction, rozbudowa tekstu watching_page (150–250 słów, cytaty), linkowanie wewnętrzne.
- [ ] **3. K3'** — `POST /v1/generate` → 202 + `job_id`, background worker, polling `GET /v1/jobs/{id}`.
- [ ] **4. K5' + SEC1** — jeden silnik publikacji WP + szyfrowany `publish_secret` HMAC, usunięcie hardcode `prawy.pl`.
- [ ] **5. E2 + Komercjalizacja:** tabele `generations` + `transcript_cache`, synchronizacja dokumentacji, Stripe live, test polowy wtyczki.
