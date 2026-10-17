# Current Tasks (Stan na 17.10.2026)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 5.1 — Komercjalizacja VSE v2.0 Wdrożona na Produkcję)
- [x] **Głęboki Audyt 3 Obszarów VSE:** Kod źródłowy i architektura, mikro-wtyczka WordPress (`pressai-wp`), finanse i Unit Economics na realnych danych (`2026-10-16_sup-01_deep-audit-and-stage1.md`).
- [x] **Master Roadmap v2.0:** Skonsolidowany dokument strategiczny i techniczny w `ROADMAP.md` oraz pełna synchronizacja z `README.md`.
- [x] **Zadanie 1 (QA, Bezkonfliktowy Merge & Sekwencyjny Deploy Etapu 1 na Produkcję):**
  - 3-warstwowy punkt **One-Click Backup & Revert**: branch `backup/pre-v2-deploy-20261017`, obrazy Docker `:rollback-20261017`, skrypt `/home/ubuntu/scripts/revert_vse_v2.sh` oraz snapshot `/home/ubuntu/scripts/backup_pre_deploy.sh`.
  - Bezkonfliktowe nałożenie zmian Etapu 1 (`8792895`) na `origin/main` z zachowaniem wszystkich nowszych commitów (`b3fecb4`, `bd82107`, `c7634b1`, `bb0780d`, `0d2f6b4`, `cca5178` — w tym obsługi MP3 i komponentów `web/src/app/dashboard/components/*`).
  - Modularność `dashboard-inner.tsx` (deduplikacja `types.ts` i `utils.ts`, zachowanie `overrideDescription` w `YouTubePublishModal.tsx`).
  - Hotfix P0 #1 (White-Label): neutralizacja promptu w `core/generator.py` na rzecz dynamicznego `site_brand`.
  - Hotfix P0 #2 (SaaS Transcript 403): przekazywanie `user_id` w `pipeline.py` i poprawka autoryzacji w `api/routers/jobs.py` oraz `api/routers/process.py`.
  - Hotfix P0 #3 & Model Tiering: wymuszenie Gemini Flash w planach Free/Starter, blokada `monthly_quota`, auto-fallback `Claude → Gemini` przy błędach 429/529.
  - Precyzyjny Tracker Tokenów i Kosztów: zliczanie tokenów wejściowych i wyjściowych LLM w `core/generator.py` (`ContextVar`), kalkulacja kosztów USD (`calculate_cost_usd`), zapis do `UsageLog` i migracja `ALTER TABLE usage_logs` na produkcji.
  - Ujednolicenie Cennika i Landing Page (`web/src/app/page.tsx`, `web/src/app/cennik/page.tsx`, `_seed_plans()` w `api/main.py`: Free 5, Starter 49 zł / 50, Pro 149 zł / 250, Agency 499 zł / 1000) + obsługa kodów rabatowych i proracji w Stripe (`api/routers/payments.py`).
  - Dodanie jawnych zależności `sqlalchemy[asyncio]>=2.0.0` i `greenlet>=3.0.0` w `requirements.txt` dla kompatybilności z SQLAlchemy 2.1+ na architekturze ARM64 (`128570b`).
- [x] **Zadanie 2: Faza 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet):**
  - Tabela `api_keys` (z kolumnami `key_prefix`, `allowed_domain`) i endpointy `/v1/plugin/*` (`validate`, `preview`, `inject-data`) zweryfikowane E2E na `https://vse.impresjapr.pl/v1/plugin/preview`.
  - Kompletna wtyczka `wordpress-plugin/vse-video-seo/` (Clean Head Injection `_vse_schema_json` w `wp_head`, uniwersalny adapter SEO RankMath/Yoast/SEOPress, Gutenberg Sidebar UI z upsellem).
- [x] **Zadanie 3: Faza 5.1 — YouTube Data API v3 OAuth Captions (Priorytet 0):**
  - Rozbudowa `fetch_transcript_api_v3()` w `core/fetcher.py` o obsługę `oauth_token: Optional[str] = None` (`Authorization: Bearer`, listowanie i pobieranie ścieżek VTT przez YouTube Data API v3, w tym dla filmów **Prywatnych i Zaplanowanych**).
  - Ustawienie Priorytetu 0 w `fetch_transcript()` (gdy `oauth_token` jest dostępny, próbuje YouTube API v3 z OAuth przed `youtube-transcript-api` i `yt-dlp`).
  - Automatyczne pobieranie i odświeżanie tokena OAuth z tabeli `youtube_channels` w `api/services/pipeline.py` (`_get_Valid_yt_oauth_token`) przed uruchomieniem `fetch_all()`.

---

## 🟡 W toku
- Brak zadań w toku — dispatch `dispatch_2026-10-16_vse_commercial_v2.md` zamknięty w 100%.

---

## 🔵 Następne (Zgodnie z Master Roadmap v2.0 — Fazy 3.3, 5.2–5.6, 6)
- [ ] **Faza 5.2:** Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów).
- [ ] **Faza 5.3:** Moduł M4B — cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **Faza 5.4:** Przeglądarka kanału (`/channels`) i Channel Monitor E2E z izolacją `user_id`/`tenant_id`.
- [ ] **Faza 5.5 & 5.6:** Local Runner auto-update `yt-dlp` + raportowanie pokrycia VTT oraz Batch Processing & SEO Scoring Dashboard.
- [ ] **Faza 6:** Integracja ekosystemu (VSE + PressAI + SocialPulse — wspólne klucze API i Bundle Pricing).
