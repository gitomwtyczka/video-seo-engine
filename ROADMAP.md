# 🗺️ Video SEO Engine (VSE) — Master Roadmap v2.1 & Plan Komercjalizacji

> **Data konsolidacji:** 16.10.2026 | **Ostatnia aktualizacja:** 17.10.2026 (`vse-dev-01` — v2.1 Multi-Language Engine)  
> **Źródło:** Konsolidacja 4 historycznych wersji roadmapy (`PROJECTS.md` 06.2026, `ecosystem-roadmap.md` 30.06.2026, `ROADMAP.md` 8-fazowy 12.07.2026, `README.md` 5-fazowy 20.07.2026) + głęboki audyt kodu źródłowego, architektury WordPress i rzeczywistych kosztów tokenów LLM / prowizji Stripe.

---

## 📊 1. Model Biznesowy, Cennik i Twarde Progi Rentowności (Zatwierdzone)

### 1.1. Anatomia kosztu 1 filmu (na rzeczywistych danych z produkcji Prawy TV / Biblia / Płużański)
Przetworzenie jednego filmu w VSE wykonuje **2 główne przebiegi LLM**:
- **Pass 1 (`generate_seo_v4`):** Transkrypt VTT z timestampami (do 200 000 znaków) → JSON-LD (`VideoObject`, `Clip`, `FAQPage`), rozdziały, cytaty, opis YouTube, linki zewnętrzne.
- **Pass 2 (`generate_article_content`):** Transkrypt (do 120 000 znaków) → pełny artykuł redakcyjny HTML (800–1200 słów).
- **Średni wolumen dla 30-minutowego filmu (~4 200 słów):** ~36 000 Input Tokens + ~3 500 Output Tokens (**łącznie ~39 500 tokenów**).

| Model AI | Koszt 1 filmu (10 min) | Koszt 1 filmu (30 min — średni) | Koszt 1 filmu (60 min) | Rola w architekturze VSE |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini 2.5 Flash** | **0,008 zł** (0,8 gr) | **0,016 zł** (**1,6 gr**) | **0,026 zł** (2,6 gr) | **Domyślny silnik bazowy** we wszystkich planach (gwarantuje >95% marży) |
| **Gemini 2.5 Pro** | 0,136 zł (14 gr) | **0,250 zł** (25 gr) | 0,426 zł (43 gr) | Silnik pośredni / Fallback dla trybu Premium |
| **Claude Sonnet 4.5** | 0,380 zł (38 gr) | **0,750 zł** (**75 gr**) | **1,092 zł** (1,09 zł) | **Tryb Redakcyjny Premium** — dostępny wyłącznie w planach Pro i Agency z twardym sub-limitem miesięcznym |

### 1.2. Zatwierdzona Tabela Pakietów i Limitów (Eliminacja „Nieograniczonych” strat)

| Plan | Cena Brutto / mies. | Prowizja Stripe (1,5% + 1 zł) | Przychód Netto (po VAT 23% i Stripe) | Limit filmów / mies. (`monthly_quota`) | Limit Premium (Claude Sonnet) | Wielojęzyczność (8 języków) | Portale WP | Koszt AI przy 100% zużycia limitu | Gwarantowana Marża Netto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FREE** *(Wtyczka WP + Trial)* | **0 zł** | 0,00 zł | 0,00 zł | **5 filmów** | 0 (tylko Gemini Flash) | Cross-Language → język panelu (`ui_lang`) | 1 portal | **max 0,08 zł** (8 groszy!) | Lead Magnet (CAC = 0,08 zł) |
| **STARTER** | **49 zł** | 1,74 zł | **38,10 zł** | **50 filmów** | 0 (tylko Gemini Flash) | Cross-Language → `ui_lang` + **Opcja Add-on (+29 zł/mies.)** | 3 portale | **0,80 zł** | **+37,30 zł (97,9% 🟢)** |
| **PRO** | **149 zł** | 3,24 zł | **117,90 zł** | **250 filmów** | **do 30 filmów** (reszta Gemini Flash) | **🌐 W CENIE (8 języków + adaptacja 1 kliknięciem)** | 10 portali | **26,02 zł** *(30×0,75 zł + 220×0,016 zł)* | **+91,88 zł (77,9% – 96,6% 🟢)** |
| **AGENCY** | **499 zł** | 8,49 zł | **397,20 zł** | **1 000 filmów** | **do 150 filmów** (reszta Gemini Flash) | **🌐 W CENIE (pełny Multi-Language bez limitu)** | 50 portali | **126,10 zł** *(150×0,75 zł + 850×0,016 zł)* | **+271,10 zł (68,3% – 96,0% 🟢)** |

---

## 🛡️ 2. Procedura Bezpieczeństwa: Mandatory Pre-Deploy Backup & One-Click Revert

Każde wdrożenie na VPS Oracle (`147.224.162.100`) podlega żelaznej procedurze **Krok Zero**:

1. **Przed dotknięciem kodu / kontenerów (Backup Gate):**
   ```bash
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
   ```
   Skrypt tworzy snapshot w `/home/ubuntu/backups/pre_integration_YYYYMMDD_HHMMSS/` zawierający:
   - Zrzut bazy PostgreSQL: `pg_vse.sql.gz`
   - Pełną kopię pliku `.env` oraz katalogu `./profiles/`
   - Zapis aktualnego commita: `git rev-parse HEAD` w `git_state.txt`
2. **One-Click Revert Bazy Danych (w razie awarii migracji/danych):**
   ```bash
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/rollback_vse.sh YYYYMMDD"
   ```
3. **One-Click Revert Kodu i Kontenerów (w razie regresji po deployu):**
   ```bash
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/revert_vse_v2.sh"
   # Oraz dedykowany rollback przed wdrożeniem Multi-Language (gałąź backup/pre-multilang-20261017):
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/revert_vse_multilang.sh"
   ```

---

## 🚀 3. Pełna Skonsolidowana Roadmapa VSE (Fazy 1–6)

### ✅ FAZA 1 & 2A — Fundamenty Silnika CLI, API i Dashboardu (ZREALIZOWANE)
- [x] Core pipeline v5.4 (`VideoObject` + `Clip` + `FAQPage` + artykuł HTML + integracja RankMath)
- [x] VTT fetching z fallbackiem (`youtube-transcript-api` → `yt-dlp` → Graceful Degradation bez napisów)
- [x] `VSELocalRunner` (usługa Windows omijająca blokady IP datacenter + fix ucinania długich transkrypcji z 20.07.2026)
- [x] FastAPI app + PostgreSQL + Auth JWT + Next.js 14 Dashboard + Admin Panel wdrożone na `vse.impresjapr.pl`
- [x] YouTube OAuth2: podpinanie kanałów, publikacja opisów M1-M8 (`build_yt_description`), aktualizacja tytułów `yt_title`, stopka `footer_text` per kanał

---

### ✅ FAZA 2B — Stabilizacja Kodu, Naprawa Bomb P0 i Porządek w Git (ZREALIZOWANE 17.10.2026)
> [!IMPORTANT]
> Wszystkie zmiany wdrożone na produkcję (`7aa982e`, `1ccbf8d`, `d7e05b1`, `803235f`, `d8ff306`, `128570b`) po pełnym Pre-Deploy Backup.

- [x] **2B.1. Konsolidacja i Merge Gałęzi Frontend (`refactor/dashboard-modularization` → `main`):**
  - Usunięcie zduplikowanych deklaracji typów i funkcji pomocniczych w `web/src/app/dashboard/dashboard-inner.tsx` na rzecz czystych importów z `./types` i `./utils` przy zachowaniu wydzielonych subkomponentów `./components/*` oraz obsługi MP3 (`d8ff306`).
  - Naprawa błędu nadpisywania ręcznie edytowanego opisu YouTube: dodanie i obsługa propa `overrideDescription?: string` w `web/src/app/dashboard/YouTubePublishModal.tsx` (`803235f`).
  - Weryfikacja `npm run build` i wdrożenie kontenera `vse-web` na produkcję.
- [x] **2B.2. Hotfix P0 #1 — Usunięcie tożsamości `prawy.pl` z promptu (Neutralność White-Label):**
  - W `core/generator.py` zastąpienie sztywnego wpisu `"Jestes ekspertem SEO i redaktorem portalu prawy.pl"` dynamiczną nazwą portalu klienta lub neutralnym `"redaktorem nowoczesnego portalu informacyjnego"` (`d7e05b1`).
- [x] **2B.3. Hotfix P0 #2 — Naprawa błędu `403 Forbidden` na `TranscriptJob` dla klientów SaaS:**
  - Przekazywanie `user_id=current_user.id` do `_create_transcript_job()` w `api/services/pipeline.py` oraz poprawka warunku autoryzacji w `api/routers/jobs.py` i `api/routers/process.py` (`7aa982e`, `1ccbf8d`).
- [x] **2B.4. Hotfix P0 #3 — Twarda Blokada Limitów (`monthly_quota`) i Model Tiering:**
  - Wdrożenie sprawdzania `used_this_month >= current_user.plan.monthly_quota` przed uruchomieniem generacji w `api/routers/generate.py` oraz dodanie `Depends(get_current_user)` w `api/routers/process.py` (`7aa982e`).
  - Wymuszenie `gemini` w planach `free` i `starter` oraz automatyczny fallback `Claude → Gemini` w `_call_llm()` (`core/generator.py`) na wypadek błędu `429 RateLimit` lub `529 Overloaded` (`d7e05b1`).
  - Rozszerzenie `UsageLog` o logowanie rzeczywistych tokenów (`input_tokens`, `output_tokens`, `llm_provider`, `estimated_cost_usd`) i migracja tabeli `usage_logs` na produkcji (`7aa982e`, `1ccbf8d`, `d7e05b1`).
- [x] **2B.5. Hotfix P1 — Trwałość danych i porządek konfiguracji:**
  - Podmontowanie wolumenu `./profiles:/app/profiles:rw` w `docker-compose.vse.yml` (`7aa982e`).
  - Ujednolicenie zmiennych środowiskowych komunikacji z PressAI (`SAAS_API_URL`, `SAAS_API_TOKEN`) w `core/generator.py` i `api/services/saas_enricher.py` (`7aa982e`, `d7e05b1`).

---

### ✅ FAZA 3 — Domknięcie Komercjalizacji Portalu VSE i Płatności Stripe (ZREALIZOWANE 17.10.2026)
- [x] **3.1. Ujednolicenie Cennika i Limitów we wszystkich warstwach (`803235f`, `bd82107`):**
  - Wyrównanie cen i limitów w `web/src/app/page.tsx`, `web/src/app/cennik/page.tsx` oraz `api/main.py` (`_seed_plans()`: Free 5, Starter 49 zł / 50, Pro 149 zł / 250, Agency 499 zł / 1000).
  - Przekierowanie przycisków CTA na Landing Page bezpośrednio do `/register?plan=starter|pro|agency`.
- [x] **3.2. Pełne spięcie Stripe Checkout, Upgrades & Kuponów (`7aa982e`):**
  - Uzupełnienie `stripe_price_id` w `_seed_plans()` i migracji bazy danych.
  - Włączenie obsługi kodów rabatowych Stripe (`allow_promotion_codes=True` w sesji Checkout).
  - Wdrożenie bezpiecznego upgrade/downgrade subskrypcji (`proration_behavior='always_invoice'`).
- [x] **3.3. Wymogi prawne i autoryzacyjne:**
  - Podstrony `/regulamin` oraz `/polityka-prywatnosci` aktywne w buildzie produkcyjnym Next.js.

---

### ✅ FAZA 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet → Portal) (ZREALIZOWANE 17.10.2026)
> [!TIP]
> Rozwiązuje krytyczny problem techniczny wycinania tagów `<script type="application/ld+json">` przez filtr WordPressa `wp_kses_post()` u klientów zewnętrznych oraz pełni rolę darmowego konia trojańskiego w repozytorium WP.org.

- [x] **4.1. Backend VSE — Obsługa Kluczy Licencyjnych Wtyczki (`/v1/plugin/*`, `bd82107`):**
  - Tabela `api_keys` (hash SHA-256, `key_prefix`, `allowed_domain`, `is_active`).
  - Dependency provider weryfikujący nagłówek `X-VSE-Key` oraz domenę `X-Site-URL`.
  - Endpointy: `POST /v1/plugin/validate`, `POST /v1/plugin/preview`, `POST /v1/plugin/inject-data` (zweryfikowane E2E na `https://vse.impresjapr.pl/v1/plugin/preview`).
- [x] **4.2. Wtyczka WordPress (`wordpress-plugin/vse-video-seo/`, `bd82107`):**
  - **Clean Head Injection:** Rejestracja pola `_vse_schema_json` w `register_post_meta` (`show_in_rest => true`) i wstrzykiwanie czystego JSON-LD (`VideoObject`, `Clip`, `FAQPage`) w sekcji `<head>` przez hook `add_action('wp_head', ...)`.
  - **Asset Player JS:** Skrypt `assets/js/player.js` obsługujący przewijanie rozdziałów (`vseSeek`).
  - **Uniwersalny Adapter SEO:** Automatyczne zapisywanie meta title/description/focus keyword dla **RankMath, Yoast SEO i SEOPress**.
- [x] **4.3. Gutenberg Sidebar UI (Aha-Moment w 30s + Upsell do Portalu, `bd82107`):**
  - Wklejenie linku YouTube w Gutenbergu → błyskawiczny podgląd Google Rich Result, wyliczenie Video SEO Score i darmowe wstawienie podstawowego Schema + 3 rozdziałów (limit Free: 5 filmów/mies.) + kafelki Pro z upsellem.

---

### ✅ FAZA 4.5 / 5.2 — Wielojęzyczność: Cross-Language & Per-Material Translation Engine („Złoty Środek”) (✅ WDROŻONE v2.1 — 17.10.2026)
> [!IMPORTANT]
> Pełne wsparcie dla **8 języków** (`pl`, `en`, `de`, `es`, `fr`, `it`, `uk`, `pt`) w całym pipeline VSE z zachowaniem precyzyjnych timestampów rozdziałów (`Clip`) i cytatów.

- [x] **4.5.1. Uniwersalne wykrywanie i pobieranie transkryptów (`source_lang`):**
  - W `core/fetcher.py` oraz `local-runner/runner.py` usunięto sztywne ograniczenie do `['pl', 'en']`. System automatycznie wykrywa oryginalny język audio (`defaultAudioLanguage` / `defaultLanguage` z YouTube Data API v3 oraz `yt-dlp`) i pobiera najlepszy dostępny transkrypt (ręczny → auto-generated → dowolny dostępny język), zwracając znormalizowany kod ISO (`source_lang`).
- [x] **4.5.2. Architektura „Dual-Language Anchor” w `core/generator.py` i `core/injector.py`:**
  - Podczas generowania cross-language (`source_lang != target_lang`), pola `chapters[].anchor_text` oraz `quotes[].anchor_text` pozostają **dosłownie w oryginalnym języku transkryptu (`source_lang`)**, co gwarantuje 100% skuteczności dopasowania znaczników czasu przez `find_anchor_in_vtt()`, podczas gdy wszystkie pola widoczne dla czytelnika (`title`, `article_html`, `faq`, `summary`, `social`, `yt_description`) są generowane natywnie w `target_lang`.
  - Pełna lokalizacja JSON-LD (`"inLanguage": target_lang` w `VideoObject` i `FAQPage`, zlokalizowane `"WatchAction"` oraz autorytatywne źródła E-E-A-T dopasowane do kraju docelowego).
- [x] **4.5.3. Endpoint `POST /v1/adapt-material` (Tłumaczenie poszczególnych zakładek 1 kliknięciem):**
  - Błyskawiczna adaptacja językowa pojedynczej zakładki (`article`, `summary`, `faq`, `social`, `yt_description`, `schema`) bez ponownego pobierania filmu i bez przesyłania całego transkryptu VTT (~1 500 tokenów, koszt ~0,0015 zł na Gemini 2.5 Flash).
  - Wywołania `/v1/adapt-material` są logowane w `UsageLog`, ale **nie pomniejszają miesięcznego limitu filmów (`monthly_quota`)** klienta.
- [x] **4.5.4. Model Komercjalizacji Wielojęzyczności („Złoty Środek”) i Stripe Add-on:**
  - **Free & Starter:** Domyślny Cross-Language do języka interfejsu (`ui_lang`) — np. angielski film → polski artykuł i Schema (lub odwrotnie).
  - **Add-on „Pakiet Wielojęzyczny” (+29 zł/mies. dla planu Starter):** Kolumna `has_multilang_addon` w tabelach `subscriptions` i `users` oraz endpoint `POST /v1/payments/checkout-addon` (Stripe Checkout 29 PLN/mies.).
  - **Pro (149 zł) & Agency (499 zł):** Pełny Pakiet Wielojęzyczny (8 języków + pasek błyskawicznego tłumaczenia zakładek z pamięcią podręczną `materialTranslations[activeTab][lang]`) **w cenie planu**.

---

### 🎬 FAZA 5 — Rozwój Produktu: YouTube OAuth Captions & Zaawansowane SEO
- [x] **5.1. Pobieranie napisów przez oficjalne YouTube Data API v3 z OAuth klienta (`captions.download`, `1ccbf8d`):**
  - Przekazywanie odświeżanego tokena OAuth z tabeli `youtube_channels` (`_get_Valid_yt_oauth_token` w `api/services/pipeline.py`) do `fetch_transcript_api_v3()` w `core/fetcher.py` jako **Priorytet 0** w `fetch_transcript()`.
  - **Efekt:** Dla własnych kanałów klienta podłączonych przez OAuth napisy pobierają się bezpośrednio na VPS (zero blokad IP YouTube!) oraz działają dla filmów **Prywatnych i Zaplanowanych (Private / Scheduled)** przed ich premierą!
- [x] **5.2. Wielojęzyczność — Cross-Language & Per-Material Translation Engine (8 języków)** *(zrealizowane w Fazie 4.5 / v2.1 powyżej)*.
- [ ] **5.3. Ręczny upload pliku `.vtt` / `.srt` w dashboardzie** (fallback dla filmów bez napisów).
- [ ] **5.4. Moduł M4B:** Cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **5.5. Przeglądarka kanału (`/channels`) i Channel Monitor E2E** (automatyczny nasłuch nowych filmów na kanale YT klienta).
- [ ] **5.6. Local Runner ulepszenia:** Automatyczna aktualizacja `yt-dlp` raz dziennie + raportowanie pokrycia VTT (`last segment at Xs`).
- [ ] **5.7. Batch Processing & SEO Scoring Dashboard** + tryb White-label dla planu Agency.

---

### 🌐 FAZA 6 — Integracja Ekosystemu (VSE + PressAI + SocialPulse)
- [ ] Wspólny standard kluczy API (`X-VSE-Key` / `X-PressAI-Key`) i zunifikowana tabela `api_keys`.
- [ ] Pakiet łączony (Bundle Pricing: VSE + PressAI + SocialPulse).
- [ ] Izolacja S2S dla konkurujących agencji SEO (`org_id` / competing tenants).

