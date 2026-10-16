# Current Tasks (Stan na 16.10.2026)

## ✅ Zamknięte (Etap 1 — Stabilizacja i Przygotowanie Komercjalizacji v2.0)
- [x] **Głęboki Audyt 3 Obszarów VSE:** Kod źródłowy i architektura, mikro-wtyczka WordPress (`pressai-wp`), finanse i Unit Economics na realnych danych (raport `2026-10-16_sup-01_deep-audit-and-stage1.md`).
- [x] **Master Roadmap v2.0:** Skonsolidowany dokument strategiczny i techniczny w `ROADMAP.md` oraz pełna synchronizacja z `README.md`.
- [x] **Modularność Dashboardu:** Podział monolitu `dashboard-inner.tsx` na komponenty, wydzielenie `types.ts` i `utils.ts`, obsługa propa `overrideDescription` w `YouTubePublishModal.tsx`.
- [x] **Hotfix P0 #1 (White-Label):** Neutralizacja promptu w `core/generator.py` (usunięcie tożsamości `prawy.pl` na rzecz dynamicznego `site_brand` portalu klienta).
- [x] **Hotfix P0 #2 (SaaS Transcript 403):** Przekazywanie `user_id` w `pipeline.py` i poprawka autoryzacji w `api/routers/jobs.py`.
- [x] **Hotfix P0 #3 & Model Tiering:** Wymuszenie Gemini Flash w planach Free/Starter, blokada `monthly_quota`, auto-fallback `Claude → Gemini` przy błędach 429/529.
- [x] **Precyzyjny Tracker Tokenów i Kosztów:** Zliczanie tokenów wejściowych i wyjściowych LLM w `core/generator.py` (`ContextVar`), kalkulacja kosztów USD, przekazywanie do `UsageLog` i bezpieczna migracja `ALTER TABLE usage_logs` w `api/main.py`.
- [x] **Naprawa `run_process`:** Pełne przekazywanie `user_id` w `api/services/pipeline.py` i `api/routers/process.py`.
- [x] **Ujednolicenie Cennika i Landing Page:** Wyrównanie limitów i cen (Free: 5, Starter 49 zł / 50 filmów, Pro 149 zł / 250 filmów, Agency 499 zł / 1000 filmów) oraz bezpośrednie linki rejestracji CTA.
- [x] **Punkt One-Click Revert:** Utworzenie brancha `backup/pre-v2-commercial-20261016` oraz patcha `backup_pre_v2_commercial_diff.patch`.

---

## 🟡 W toku (Kolejne Zadania do Wykonania)
- [ ] **Zadanie 1 (QA, Merge & Deploy Etapu 1 na Produkcję):**
  - Niezależna weryfikacja zmian na branchu `refactor/dashboard-modularization` (`npm run build` w `web/`, syntax check w Pythonie).
  - Wykonanie obowiązkowego snapshotu na VPS: `/home/ubuntu/scripts/backup_pre_deploy.sh`.
  - Merge gałęzi do `main` i wdrożenie kontenerów na `vse.impresjapr.pl` (`docker compose -f docker-compose.vse.yml up -d --build`).
  - Sprawdzenie endpointu `/health` oraz migracji kolumn w tabeli `usage_logs`.

---

## 🔵 Następne (Zgodnie z Master Roadmap v2.0 i Dispatch)
- [ ] **Zadanie 2: Faza 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet):**
  - Tabela `api_keys` i endpointy `/v1/plugin/*` (`validate`, `preview`, `inject-data`).
  - Budowa wtyczki na bazie 80% kodu `pressai-wp`:
    - Clean Head Injection: wstrzykiwanie czystego JSON-LD w `wp_head` przez pole `_vse_schema_json` (ominięcie filtra `wp_kses_post`).
    - Uniwersalny adapter SEO: obsługa RankMath, Yoast SEO i SEOPress.
    - Gutenberg Sidebar UI z limitem 5 darmowych filmów/mies. i banerami upsellingowymi do portalu.
- [ ] **Zadanie 3: Faza 5.1 — YouTube Data API v3 OAuth Captions:**
  - Przekazanie tokena OAuth z tabeli `youtube_channels` do `fetch_transcript_api_v3()` w `core/fetcher.py`.
  - Bezpośrednie pobieranie napisów na VPS bez blokad IP YouTube oraz obsługa filmów **Prywatnych i Zaplanowanych**.
- [ ] **Faza 3 — Płatności Stripe i Wymogi Prawne:**
  - Pełne spięcie Stripe Checkout, obsługa kuponów promocyjnych, podstrony `/regulamin` i `/polityka-prywatnosci`.