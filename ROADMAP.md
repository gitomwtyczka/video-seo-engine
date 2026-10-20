# 🗺️ Video SEO Engine (VSE) — Master Roadmap v2.2 & Plan Komercjalizacji

> **Data konsolidacji:** 16.10.2026 | **Ostatnia aktualizacja:** 20.10.2026 (`vse-dev-01` — v2.2: Limity 5/30/110/250, Pakiety Top-Up 99/249/699 zł, Wtyczka WordPress `vse-video-seo` v3.0.0, Panel `/admin` Bez Stripe, Multi-Language Engine v2.1)  
> **Źródło:** Konsolidacja 4 historycznych wersji roadmapy (`PROJECTS.md` 06.2026, `ecosystem-roadmap.md` 30.06.2026, `ROADMAP.md` 8-fazowy 12.07.2026, `README.md` 5-fazowy 20.07.2026) + głęboki audyt kodu źródłowego, architektury WordPress v3.0 i rzeczywistych kosztów tokenów LLM / prowizji Stripe.

---

## 📊 1. Model Biznesowy, Cennik i Twarde Progi Rentowności (Zatwierdzone v2.2)

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

### 1.2. Zatwierdzona Tabela Pakietów Bazowych (`5 / 30 / 110 / 250`)

| Plan | Cena Brutto / mies. | Prowizja Stripe (1,5% + 1 zł) | Przychód Netto (po VAT 23% i Stripe) | Limit filmów / mies. (`monthly_quota`) | Cena jednostkowa w abonamencie | Wielojęzyczność (8 języków) | Portale WP | Koszt AI przy 100% zużycia limitu | Gwarantowana Marża Netto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FREE** *(Wtyczka WP + Trial)* | **0 zł** | 0,00 zł | 0,00 zł | **5 filmów** | 0,00 zł / film | Cross-Language → język panelu (`ui_lang`) | 1 portal | **max 0,08 zł** (8 groszy!) | Lead Magnet (CAC = 0,08 zł) |
| **STARTER** | **49 zł** | 1,74 zł | **38,10 zł** | **30 filmów** | **1,63 zł / film** | Cross-Language → `ui_lang` + **Opcja Add-on (+29 zł/mies.)** | 3 portale | **0,48 zł** *(Gemini Flash)* | **+37,62 zł (98,7% 🟢)** |
| **PRO** | **149 zł** | 3,24 zł | **117,90 zł** | **110 filmów** | **1,35 zł / film** | **🌐 W CENIE (8 języków + adaptacja 1 kliknięciem)** | 10 portali | **1,76 zł – 23,78 zł** | **+94,12 zł – 116,14 zł (79,8% – 98,5% 🟢)** |
| **AGENCY** | **499 zł** | 8,49 zł | **397,20 zł** | **250 filmów** | **1,99 zł / film** *(+ ShortMachine AI)* | **🌐 W CENIE (pełny Multi-Language bez limitu)** | 50 portali | **4,00 zł – 86,20 zł** | **+311,00 zł – 393,20 zł (78,3% – 99,0% 🟢)** |
| **ENTERPRISE / CUSTOM** *(>250 filmów/mies.)* | **Wycena indywidualna B2B** | Faktura VAT / Stripe | Indywidualnie | **`custom_monthly_quota` (>250 lub `-1` Unlimited)** | Negocjowalna | **🌐 W CENIE + Dedykowane wsparcie VIP** | 50+ portali | Zależny od wolumenu | **Kontrakt B2B / Media House** |

### 1.3. Dodatek Wielojęzyczny (Add-on) oraz Bezterminowe Pakiety Top-Up (`extra_quota_balance`)

- **🌐 Add-on: Pakiet Wielojęzyczny (+29 zł / mies. do planu Starter, lub pakiet łączony Starter + 8 Języków za 78 zł / mies.):**
  - Odblokowuje generowanie w dowolnym z 8 języków (`PL, EN, DE, ES, FR, IT, UK, PT`) oraz tłumaczenie pojedynczych zakładek i całego pakietu 1 kliknięciem (w planach `Pro` i `Agency` w cenie).
- **⚡ Jednorazowe Pakiety Top-Up (bezterminowe kredyty nieprzepadające z końcem miesiąca, niekanibalizujące abonamentu przy limitach 30/110/250):**
  - **`topup_50` (+50 filmów):** **99 zł** (`1,98 zł / film`) — bezterminowy rollover, uruchamiany automatycznie po wykorzystaniu puli miesięcznej planu.
  - **`topup_150` (+150 filmów):** **249 zł** (`1,66 zł / film`) — *Najpopularniejszy* dla redakcji w gorących okresach wydawniczych.
  - **`topup_500` (+500 filmów):** **699 zł** (`1,40 zł / film`) — pakiet hurtowy na masową indeksację archiwum YouTube.

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
- [x] **2B.1. Konsolidacja i Merge Gałęzi Frontend (`refactor/dashboard-modularization` → `main`):**
  - Usunięcie zduplikowanych deklaracji typów i funkcji pomocniczych w `web/src/app/dashboard/dashboard-inner.tsx` na rzecz czystych importów z `./types` i `./utils` przy zachowaniu wydzielonych subkomponentów `./components/*` oraz obsługi MP3 (`d8ff306`).
  - Naprawa błędu nadpisywania ręcznie edytowanego opisu YouTube: dodanie i obsługa propa `overrideDescription?: string` w `web/src/app/dashboard/YouTubePublishModal.tsx` (`803235f`).
- [x] **2B.2. Hotfix P0 #1 — Usunięcie tożsamości `prawy.pl` z promptu (Neutralność White-Label):**
  - W `core/generator.py` zastąpienie sztywnego wpisu `"Jestes ekspertem SEO i redaktorem portalu prawy.pl"` dynamiczną nazwą portalu klienta lub neutralnym `"redaktorem nowoczesnego portalu informacyjnego"` (`d7e05b1`).
- [x] **2B.3. Hotfix P0 #2 — Naprawa błędu `403 Forbidden` na `TranscriptJob` dla klientów SaaS:**
  - Przekazywanie `user_id=current_user.id` do `_create_transcript_job()` w `api/services/pipeline.py` oraz poprawka warunku autoryzacji w `api/routers/jobs.py` i `api/routers/process.py` (`7aa982e`, `1ccbf8d`).
- [x] **2B.4. Hotfix P0 #3 — Twarda Blokada Limitów (`monthly_quota`), Top-Up (`extra_quota_balance`) i Model Tiering:**
  - Wdrożenie sprawdzania `effective_monthly_quota` (`custom_monthly_quota` → `plan.monthly_quota`) oraz automatycznego pobierania z bezterminowej puli `extra_quota_balance` po wyczerpaniu limitu miesięcznego w `api/quota.py`, `api/routers/generate.py`, `api/routers/process.py` i `api/routers/plugin.py`.
  - Wymuszenie `gemini` w planach `free` i `starter` oraz automatyczny fallback `Claude → Gemini` w `_call_llm()` (`core/generator.py`).
  - Rozszerzenie `UsageLog` o logowanie rzeczywistych tokenów (`input_tokens`, `output_tokens`, `llm_provider`, `estimated_cost_usd`).
- [x] **2B.5. Hotfix P1 — Trwałość danych i porządek konfiguracji:**
  - Podmontowanie wolumenu `./profiles:/app/profiles:rw` w `docker-compose.vse.yml` (`7aa982e`).
  - Ujednolicenie zmiennych środowiskowych komunikacji z PressAI (`SAAS_API_URL`, `SAAS_API_TOKEN`).

---

### ✅ FAZA 3 — Komercjalizacja Portalu VSE, Płatności Stripe, Pakiety Top-Up i Panel `/admin` (ZREALIZOWANE v2.2 — 20.10.2026)
- [x] **3.1. Ujednolicenie Cennika i Limitów (`5 / 30 / 110 / 250`) we wszystkich warstwach:**
  - Wyrównanie cen i limitów w `api/main.py` (`_seed_plans()`), `api/routers/plugin.py` (`PLAN_LIMITS`), `api/routers/admin.py` (`DEFAULT_PLAN_QUOTAS`), `web/src/app/admin/page.tsx`, `web/src/app/page.tsx`, `web/src/app/cennik/page.tsx` oraz `scripts/setup_stripe_live.py`:
    - `Free`: **5 filmów / mies.** (0 zł, 1 portal WP)
    - `Starter`: **30 filmów / mies.** (49 zł, 3 portale WP, opcjonalny Add-on 8 Języków +29 zł)
    - `Pro`: **110 filmów / mies.** (149 zł, 10 portali WP, 8 języków w cenie)
    - `Agency`: **250 filmów / mies.** (499 zł, 50 portali WP, 8 języków w cenie + moduł ShortMachine)
- [x] **3.2. Pakiety Doładowań Top-Up (`99 / 249 / 699 zł`) i Sekcja Enterprise (>250 filmów/mies.):**
  - Endpoint `POST /v1/payments/checkout-topup` oraz idempotentna obsługa webhooka `checkout.session.completed` dla pakietów:
    - `+50 filmów` za **99 zł** (`1,98 zł / film`)
    - `+150 filmów` za **249 zł** (`1,66 zł / film`)
    - `+500 filmów` za **699 zł** (`1,40 zł / film`)
  - Sekcja Planu Negocjowalnego / Enterprise na `/cennik` dla wydawców potrzebujących powyżej 250 filmów miesięcznie.
- [x] **3.3. Panel Administratora `/admin` — Kompleksowe Zarządzanie Kontami Bez Stripe:**
  - Rozbudowa `PATCH /v1/admin/users/{user_id}/plan` w `api/routers/admin.py` oraz modalu `ChangePlanModal` w `web/src/app/admin/page.tsx`:
    - Ręczna zmiana planu bazowego (`Free / Starter / Pro / Agency`),
    - Włączanie/wyłączanie dodatku `has_multilang_addon` (🌐 MultiLang),
    - Ustawianie indywidualnego limitu miesięcznego `custom_monthly_quota` (własna liczba VIP np. 400 / 2000 lub `♾️ Nielimitowany -1`),
    - Dodawanie darmowych kredytów Top-Up (`+50`, `+150`, `+500`, własna pula) bez udziału Stripe,
    - Bezpiecznik anulowania aktywnej subskrypcji w Stripe (`cancel_stripe_subscription`) przy ręcznym nadaniu planu VIP.
- [x] **3.4. Pełne spięcie Stripe Checkout, Verify-Session, Upgrades & Kuponów:**
  - Endpoint `POST /v1/payments/verify-session` gwarantujący natychmiastową synchronizację planu, add-onu i kredytów Top-Up po powrocie z Checkoutu,
  - Skrypt `scripts/setup_stripe_live.py` do automatycznego tworzenia produktów/cen Live i ukrytego kuponu retencyjnego `LOYALTY20` (`-20% na 3 mies.`).

---

### ✅ FAZA 4 — Wtyczka WordPress `vse-video-seo` v3.0.0 (Pełny Generator, Biblioteka 0 Kredytów & Dwukierunkowy Most) (ZREALIZOWANE 20.10.2026)
> [!TIP]\n> Wtyczka `vse-video-seo` v3.0.0 (`plugins/vse-video-seo/`, pobierana z `GET /v1/plugin/download`) rozwiązuje problem wycinania `<script type="application/ld+json">` przez WordPressa oraz całkowicie eliminuje konieczność ręcznego konfigurowania *Application Passwords* przy publikacji z chmury VSE!

- [x] **4.1. Menu Główne w WP Admin (`🎬 VSE Video SEO` — `class-vse-admin-menu.php`):**
  - Widoczna pozycja w głównym menu bocznym WordPressa (`add_menu_page` z ikoną `dashicons-video-alt3`, pozycja `58`) z 3 zakładkami:
    1. **🚀 Generator AI (YouTube → Wpis WP):** Wklejenie linku YouTube, wybór języka docelowego (`PL/EN/DE/ES/FR/IT/UK/PT`), podgląd SEO Score i utworzenie kompletnego szkicu/wpisu WordPress jednym kliknięciem.
    2. **📚 Biblioteka / Historia VSE (0 kredytów):** Pobieranie listy materiałów wygenerowanych wcześniej na `vse.impresjapr.pl` (`POST /v1/plugin/history` i `POST /v1/plugin/history-item`) i importowanie ich do WordPressa jako gotowy wpis za **0 kredytów**.
    3. **🔑 Klucz API & Status Połączenia:** Wklejenie klucza `vse_live_...`, podgląd planu i pozostałego limitu (`remaining_quota` + `extra_quota_balance`).
- [x] **4.2. Klasyczny Meta Box (`class-vse-metabox.php`) + Gutenberg Sidebar (`gutenberg-sidebar.js`):**
  - Widoczny pod każdym edytorem wpisów/stron (działa zarówno w Gutenbergu, jak i w Classic Editorze / Elementorze / Divi).
  - Przycisk **„✨ Wygeneruj i wstaw cały pakiet VSE (Artykuł + Wideo + Rozdziały + FAQ + Schema + Meta)”** oraz przyciski selektywne (tylko rozdziały + FAQ, tylko Schema JSON-LD w `<head>` + Meta RankMath/Yoast/SEOPress) i zakładka wyboru gotowego materiału z Biblioteki VSE za 0 kredytów.
- [x] **4.3. Dwukierunkowy Most VSE ↔ WordPress bez Application Passwords (`class-vse-rest-receiver.php` + `/v1/plugin/validate`):**
  - **Auto-Parowanie Portalu:** Kliknięcie „Zapisz i połącz klucz API” w WordPressie wywołuje `POST /v1/plugin/validate` z `site_url` i `site_name`, co automatycznie tworzy lub aktualizuje rekord `WpPortal` (`auth_mode="plugin_token"`) na koncie użytkownika w VSE.
  - **Bezpośredni Push z VSE do WordPressa (`/wp-json/vse/v1/publish`):** Wtyczka rejestruje endpoint REST API w WordPressie autoryzowany nagłówkiem `X-VSE-Plugin-Key`. Gdy użytkownik kliknie „Publikuj do WordPress” w panelu `vse.impresjapr.pl`, backend (`core/injector.py` / `api/routers/inject.py`) wysyła artykuł, Schema JSON-LD i pola RankMath/Yoast bezpośrednio do wtyczki (z automatycznym fallbackiem do klasycznego `/wp-json/wp/v2/posts`).

---

### ✅ FAZA 4.5 / 5.2 — Wielojęzyczność: Cross-Language & Per-Material Translation Engine v2.1 (ZREALIZOWANE)
- [x] **4.5.1. Uniwersalne wykrywanie i pobieranie transkryptów (`source_lang`)** w `core/fetcher.py` oraz `local-runner/runner.py`.
- [x] **4.5.2. Architektura „Dual-Language Anchor” w `core/generator.py` i `core/injector.py`:**
  - `chapters[].anchor_text` oraz `quotes[].anchor_text` pozostają w oryginalnym języku transkryptu (`source_lang`) dla 100% celności timestampów VTT, podczas gdy cały artykuł, rozdziały, FAQ, streszczenie, opis YouTube i JSON-LD (`inLanguage`) są generowane w `target_lang`.
- [x] **4.5.3. Tłumaczenie całego pakietu oraz pojedynczych zakładek (`POST /v1/adapt-material`) z trwałym zapisem w DB:**
  - Tłumaczenia zakładek są zapisywane w `TranscriptJob.schema_data["material_translations"]` i nie pomniejszają miesięcznego limitu filmów (`monthly_quota`).

---

### 🎬 FAZA 5 — Rozwój Produktu: YouTube OAuth Captions & Zaawansowane SEO
- [x] **5.1. Pobieranie napisów przez oficjalne YouTube Data API v3 z OAuth klienta (`captions.download`, `1ccbf8d`).**
- [x] **5.2. Wielojęzyczność — Cross-Language & Per-Material Translation Engine (8 języków, v2.1).**
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
