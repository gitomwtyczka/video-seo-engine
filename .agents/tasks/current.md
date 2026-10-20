# Current Tasks (Stan na 20.10.2026)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1, WP Plugin v3.0 + Limity 5/30/110/250 + Top-Up 99/249/699 + Niezawodność Napisów & Blokada Anty-Konfabulacyjna)
- [x] **Wdrożenie KROK A+B+C: Limity 5/30/110/250 + Top-Up 99/249/699 PLN + OAuth Channel Match + Instant Runner Wakeup + Blokada Anty-Konfabulacyjna (`212c588`, `93cf930`, `87e21a3`, `4d0ed16`, `3d651cd`, `64e83e2`, `2009f30`, `a480164`, `d43c544`, `581f232`, `c3fac7c`, `3a62af9`, `5196757`, `a63cb06`):**
  - **KROK A — Ujednolicenie limitów planów (`5 / 30 / 110 / 250`) i cen pakietów Top-Up (`99 / 249 / 699 PLN`):** Zsynchronizowano limity planów (`Free: 5`, `Starter: 30`, `Pro: 110`, `Agency: 250`) w bazie PostgreSQL (`plans`), `api/main.py`, `api/quota.py`, `api/routers/plugin.py`, `api/routers/admin.py`, `scripts/setup_stripe_live.py`, na stronie głównej (`web/src/app/page.tsx`), w cenniku (`web/src/app/cennik/page.tsx`) oraz w panelu `/admin` (`web/src/app/admin/page.tsx`). Zaktualizowano cennik pakietów Top-Up (`+50 filmów = 99 PLN`, `+150 filmów = 249 PLN`, `+500 filmów = 699 PLN`) w `api/routers/payments.py` i `web/src/app/cennik/page.tsx` wraz z banerem VIP/Enterprise `>250 filmów`.
  - **KROK B — Niezawodność pobierania napisów (YouTube OAuth Channel Match + Multi-Track Fallback + Instant Runner Wakeup):**
    - Dopasowanie kanału OAuth po `channel_id` filmu w `_get_user_yt_access_tokens(user_id, target_channel_id)` (`api/services/pipeline.py`) oraz multi-track fallback w `fetch_transcript_api_v3()` (`core/fetcher.py`) — zweryfikowane E2E na filmie `lAdOs4IcHvY` (kanał `Studio Prawy_PL` / `UCoH2G9By4OX3kcLsc8lHgDw`, pobrano `154 983 zn.` VTT w `~1.8s`).
    - Cache transkrypcji w bazie (`usage_logs` / `transcript_jobs`) — ponowna generacja tego samego filmu omija ponowne pobieranie VTT.
    - Natychmiastowe wybudzanie in-memory (`asyncio.Event` w `api/services/pipeline.py` i `api/routers/jobs.py` przy `POST /v1/jobs/{id}/result`), `LOCAL_RUNNER_POLL_INTERVAL=2.0s` (redukcja obciążenia DB o 75% względem 0.5s), `LOCAL_RUNNER_TIMEOUT=90s` oraz akceptacja spóźnionych wyników runnera w statusach `cloud_fallback`/`processing`.
  - **KROK C — Twarda blokada anty-konfabulacyjna (`HTTP 422` + `0 kredytów`) + `clean_transcript` z korektą fonetyczną ASR:**
    - Całkowita eliminacja generowania artykułów z samych metadanych: brak napisów przerywa pipeline z czytelnym błędem `TranscriptUnavailableError` (`HTTP 422 Unprocessable Entity`) i **nie pobiera kredytu** z puli użytkownika (`0 credits charged`).
    - Dodano instrukcje korekty fonetycznej błędów ASR (nazwiska, nazwy własne, interpunkcja) oraz nowe pole `clean_transcript` w `core/generator.py`.
- [x] **Wtyczka WordPress `vse-video-seo` v3.0 + Model >250 filmów (Top-Up + VIP Quota) + Rozbudowa `/admin` (`3cb5a15`, `46f79ac`, `571f237`, `325ece7`):**
  - Wtyczka WordPress v3.0 (`plugins/vse-video-seo/`), dynamiczny `GET/HEAD /v1/plugin/download`, paczka Desktop Runnera (`GET /v1/users/desktop-runner-package`), kolumny `extra_quota_balance` i `custom_monthly_quota` oraz rozbudowany panel `/admin`.
- [x] **Faza 4.5 / 5.2: Wielojęzyczność — Cross-Language & Per-Material Translation Engine („Złoty Środek”, `93cef05`):**
  - Uniwersalne wykrywanie języka źródłowego, 8-języczny fallback napisów, architektura Dual-Language Anchor, `adapt_material_language()`, Stripe Add-on (+29 PLN/mies.).
- [x] **Etap 1 + Faza 2B, 3.1-3.2, 4, 5.1 (Komercjalizacja VSE v2.0):**
  - Wszystkie wcześniejsze zadania Etapu 1, wtyczki WordPress `vse-video-seo` (`/v1/plugin/*`) oraz YouTube Data API v3 OAuth Captions (`1ccbf8d`, `bd82107`, `128570b`) zamknięte i wdrożone.

---

## 🟡 W toku
- Brak zadań w toku — wdrożenie KROK A+B+C (limity `5/30/110/250`, Top-Up `99/249/699 PLN`, dopasowanie kanału OAuth po `channel_id`, wybudzanie `asyncio.Event` + `POLL_INTERVAL=2.0s` / `TIMEOUT=90s`, twarda blokada anty-konfabulacyjna `HTTP 422`, `clean_transcript` z korektą fonetyczną ASR) zamknięte i zweryfikowane E2E na produkcji.

---

## 🔵 Następne (Zgodnie z Master Roadmap v2.2 — Fazy 5.3–5.7, 6)
- [ ] **Faza 5.3:** Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów).
- [ ] **Faza 5.4:** Moduł M4B — cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **Faza 5.5:** Przeglądarka kanału (`/channels`) i Channel Monitor E2E z izolacją `user_id`/`tenant_id`.
- [ ] **Faza 5.6 & 5.7:** Local Runner auto-update `yt-dlp` + raportowanie pokrycia VTT oraz Batch Processing & SEO Scoring Dashboard.
- [ ] **Faza 6:** Integracja ekosystemu (VSE + PressAI + SocialPulse — wspólne klucze API i Bundle Pricing).
