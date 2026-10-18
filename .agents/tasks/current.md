# Current Tasks (Stan na 18.10.2026)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1 — VSE v2.1 Multi-Language Engine Wdrożone na Produkcję)
- [x] **Faza 4.5 / 5.2: Wielojęzyczność — Cross-Language & Per-Material Translation Engine („Złoty Środek”, `93cef05`):**
  - **Backup & One-Click Revert (`backup/pre-multilang-20261017`):** Dedykowana gałąź Git na GitHubie (`140b478`), snapshot `/home/ubuntu/scripts/backup_pre_deploy.sh`, tagi obrazów Docker `video-seo-engine-vse-api:rollback-pre-multilang` (`8145bb467860`) i `video-seo-engine-vse-web:rollback-pre-multilang` (`d0003a06fd0a`) oraz wykonywalny skrypt `/home/ubuntu/scripts/revert_vse_multilang.sh` (`chmod +x`).
  - **KROK 1 (Fetcher & Local Runner):** Uniwersalne wykrywanie języka źródłowego (`detect_transcript_language()`, `normalize_lang_code()`, `default_audio_language` z YouTube Data API v3 i `yt-dlp`) oraz 8-języczny fallback pobierania napisów (`pl`, `en`, `de`, `es`, `fr`, `it`, `uk`, `pt`, `orig`) w `core/fetcher.py` i `local-runner/runner.py`.
  - **KROK 2 (Generator & Injector — Dual-Language Anchor):** Stała `SUPPORTED_LANGUAGES` (8 języków ze zlokalizowanymi `WatchAction` i źródłami E-E-A-T), architektura **Dual-Language Anchor** (`chapters[].anchor_text` i `quotes[].anchor_text` w `source_lang` dla 100% trafności `find_anchor_in_vtt()`, przy jednoczesnym generowaniu wszystkich pól treści w `target_lang`), `build_jsonld_schemas(seo, target_lang)` oraz `adapt_material_language()` w `core/generator.py` i `core/injector.py`.
  - **KROK 3 (Quota, Modele, Endpointy i Stripe Add-on):** Kolumna `has_multilang_addon` w tabelach `users` i `subscriptions` (migracja `ALTER TABLE` zweryfikowana na `vse-postgres`), `get_multilang_entitlements()` i `check_multilang_access()` w `api/quota.py`, wykluczenie `adapt_material` z limitu `monthly_quota`, endpoint `POST /v1/adapt-material` w `api/routers/generate.py` oraz `POST /v1/payments/checkout-addon` (+29 PLN/mies. dla planu Starter) w `api/routers/payments.py`.
  - **KROK 4 (Frontend Dashboard & Cennik):** Kompaktowy przełącznik języka panelu `🌐 PL ▾` w sidebarze (`localStorage: vse_ui_lang`), selektor „Język wyniku SEO” (`targetLang`) w generatorze, plakietka `🌐 Źródło: XX → Wynik: YY`, pasek tłumaczenia poszczególnych zakładek 1 kliknięciem z pamięcią podręczną `materialTranslations[activeTab][lang]` w `dashboard-inner.tsx`, oraz zaktualizowane karty planów i baner Add-on (+29 zł/mies.) w `web/src/app/cennik/page.tsx` i `web/src/app/page.tsx`.
  - **KROK 5 & 6 (Roadmapa, Deploy & Live E2E Test):** Aktualizacja `ROADMAP.md` (v2.1), sekwencyjny deploy `vse-api` i `vse-web` na VPS Oracle (`147.224.162.100`) oraz pomyślny test E2E na filmie `https://www.youtube.com/watch?v=3pZi3uoLLzY` (`pl` → `de` Cross-Language + `de` → `en` `adapt_material_language`).
- [x] **Etap 1 + Faza 2B, 3.1-3.2, 4, 5.1 (Komercjalizacja VSE v2.0):**
  - Wszystkie wcześniejsze zadania Etapu 1, wtyczki WordPress `vse-video-seo` (`/v1/plugin/*`) oraz YouTube Data API v3 OAuth Captions (`1ccbf8d`, `bd82107`, `128570b`) zamknięte i wdrożone.

---

## 🟡 W toku
- Brak zadań w toku — dispatch Multi-Language & Cross-Language Engine v2.1 zamknięty w 100%.

---

## 🔵 Następne (Zgodnie z Master Roadmap v2.1 — Fazy 5.3–5.7, 6)
- [ ] **Faza 5.3:** Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów).
- [ ] **Faza 5.4:** Moduł M4B — cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **Faza 5.5:** Przeglądarka kanału (`/channels`) i Channel Monitor E2E z izolacją `user_id`/`tenant_id`.
- [ ] **Faza 5.6 & 5.7:** Local Runner auto-update `yt-dlp` + raportowanie pokrycia VTT oraz Batch Processing & SEO Scoring Dashboard.
- [ ] **Faza 6:** Integracja ekosystemu (VSE + PressAI + SocialPulse — wspólne klucze API i Bundle Pricing).
