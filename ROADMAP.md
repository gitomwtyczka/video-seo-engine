# 🗺️ Video SEO Engine (VSE) — Master Roadmap v2.0 & Plan Komercjalizacji

> **Data konsolidacji:** 16.10.2026 | **Autor:** Supervisor 01 (`sonic-void`)  
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

| Plan | Cena Brutto / mies. | Prowizja Stripe (1,5% + 1 zł) | Przychód Netto (po VAT 23% i Stripe) | Limit filmów / mies. (`monthly_quota`) | Limit Premium (Claude Sonnet) | Portale WP | Koszt AI przy 100% zużycia limitu | Gwarantowana Marża Netto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FREE** *(Wtyczka WP + Trial)* | **0 zł** | 0,00 zł | 0,00 zł | **5 filmów** | 0 (tylko Gemini Flash) | 1 portal | **max 0,08 zł** (8 groszy!) | Lead Magnet (CAC = 0,08 zł) |
| **STARTER** | **49 zł** | 1,74 zł | **38,10 zł** | **50 filmów** | 0 (tylko Gemini Flash) | 3 portale | **0,80 zł** | **+37,30 zł (97,9% 🟢)** |
| **PRO** | **149 zł** | 3,24 zł | **117,90 zł** | **250 filmów** | **do 30 filmów** (reszta Gemini Flash) | 10 portali | **26,02 zł** *(30×0,75 zł + 220×0,016 zł)* | **+91,88 zł (77,9% – 96,6% 🟢)** |
| **AGENCY** | **499 zł** | 8,49 zł | **397,20 zł** | **1 000 filmów** | **do 150 filmów** (reszta Gemini Flash) | 50 portali | **126,10 zł** *(150×0,75 zł + 850×0,016 zł)* | **+271,10 zł (68,3% – 96,0% 🟢)** |

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
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/rollback_code.sh vse <git_sha>"
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

### 🔴 FAZA 2B — Stabilizacja Kodu, Naprawa Bomb P0 i Porządek w Git (PRIORYTET 1 — TERAZ)
> [!IMPORTANT]
> Wszystkie zmiany poprzedzone analizą edytowanego pliku oraz pełnym zrzutem Pre-Deploy Backup.

- [ ] **2B.1. Konsolidacja i Merge Gałęzi Frontend (`refactor/dashboard-modularization` → `main`):**
  - Usunięcie zduplikowanych deklaracji typów (linie 23–98) i funkcji pomocniczych (linie 101–246) w `web/src/app/dashboard/dashboard-inner.tsx` na rzecz czystych importów z `./types` i `./utils`.
  - Naprawa błędu nadpisywania ręcznie edytowanego opisu YouTube: dodanie i obsługa propa `overrideDescription?: string` w `web/src/app/dashboard/YouTubePublishModal.tsx`.
  - Naprawa kodowania znaków emoji UTF-8 w dashboardzie *(odzyskane z Roadmapy v3)*.
  - Weryfikacja `npm run build` i scalenie gałęzi `refactor/dashboard-modularization` do `main`.
- [ ] **2B.2. Hotfix P0 #1 — Usunięcie tożsamości `prawy.pl` z promptu (Neutralność White-Label):**
  - W `core/generator.py` (linia 716) zastąpienie sztywnego wpisu `"Jestes ekspertem SEO i redaktorem portalu prawy.pl"` dynamiczną nazwą portalu klienta (lub neutralnym `"redaktorem nowoczesnego portalu informacyjnego"`).
- [ ] **2B.3. Hotfix P0 #2 — Naprawa błędu `403 Forbidden` na `TranscriptJob` dla klientów SaaS:**
  - Przekazywanie `user_id=current_user.id` do `_create_transcript_job()` w `api/services/pipeline.py` (linie 167–177) oraz poprawka warunku autoryzacji w `api/routers/jobs.py` (linie 355–358).
  - Dodanie izolacji `user_id` / `tenant_id` w plikach rejestru `core/monitor.py`.
- [ ] **2B.4. Hotfix P0 #3 — Twarda Blokada Limitów (`monthly_quota`) i Model Tiering:**
  - Wdrożenie sprawdzania `used_this_month >= current_user.plan.monthly_quota` przed uruchomieniem generacji w `api/routers/generate.py` oraz dodanie `Depends(get_current_user)` w `api/routers/process.py`.
  - Ustawienie `gemini-2.5-flash` jako domyślnego silnika LLM oraz weryfikacja sub-limitu `premium_quota` dla wywołań `claude-sonnet`.
  - Dodanie automatycznego fallbacku `Claude → Gemini` w `_call_llm()` (`core/generator.py`, linie 284–303) na wypadek błędu `429 RateLimit` lub `529 Overloaded`.
  - Rozszerzenie `UsageLog` o logowanie rzeczywistych tokenów (`input_tokens`, `output_tokens`, `llm_provider`, `estimated_cost_usd`).
- [ ] **2B.5. Hotfix P1 — Trwałość danych i porządek konfiguracji:**
  - Podmontowanie wolumenu `./profiles:/app/profiles` w `docker-compose.vse.yml` (zapobieganie utracie profili portali przy rebuildzie kontenera).
  - Ujednolicenie zmiennych środowiskowych komunikacji z PressAI (`SAAS_API_URL`, `SAAS_API_TOKEN`) w `core/generator.py` i `api/services/pipeline.py`.
  - Szyfrowanie haseł aplikacyjnych WordPress (`wp_app_password`) w bazie danych *(odzyskane z Roadmapy v3)*.

---

### 💰 FAZA 3 — Domknięcie Komercjalizacji Portalu VSE i Płatności Stripe (PRIORYTET 2)
- [ ] **3.1. Ujednolicenie Cennika i Limitów we wszystkich warstwach:**
  - Wyrównanie cen i limitów w:
    1. `web/src/app/page.tsx` (Landing Page — usunięcie cen 29/99/299 zł oraz usunięcie słowa „Nieograniczony”!),
    2. `web/src/app/cennik/page.tsx` (Podstrona cennika),
    3. `api/main.py` (`_seed_plans()` — aktualizacja limitów: Free 5, Starter 49 zł / 50, Pro 149 zł / 250, Agency 499 zł / 1000).
  - Przekierowanie przycisków CTA na Landing Page bezpośrednio do `/register?plan=starter|pro|agency`.
- [ ] **3.2. Pełne spięcie Stripe Checkout, Upgrades & Kuponów:**
  - Uzupełnienie `stripe_price_id` w `_seed_plans()` i migracji bazy danych (eliminacja błędu HTTP 400 przy kliknięciu zakupu).
  - Włączenie obsługi kodów rabatowych Stripe (`allow_promotion_codes=True` w sesji Checkout).
  - Wdrożenie bezpiecznego upgrade/downgrade subskrypcji (`subscription_update` z `proration_behavior='always_invoice'` — brak dublowania subskrypcji).
  - Automatyczne anulowanie subskrypcji w Stripe przy usunięciu konta użytkownika (eliminacja „ghost charging”).
- [ ] **3.3. Wymogi prawne i autoryzacyjne przed startem publicznym:**
  - Podstrony `/regulamin` (Terms of Service) oraz `/polityka-prywatnosci` (RODO/GDPR).
  - Weryfikacja adresu e-mail przy rejestracji oraz logowanie jednym kliknięciem przez Google OAuth.

---

### 🔌 FAZA 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet → Portal) (PRIORYTET 3)
> [!TIP]
> Rozwiązuje krytyczny problem techniczny wycinania tagów `<script type="application/ld+json">` przez filtr WordPressa `wp_kses_post()` u klientów zewnętrznych oraz pełni rolę darmowego konia trojańskiego w repozytorium WP.org.

- [ ] **4.1. Backend VSE — Obsługa Kluczy Licencyjnych Wtyczki (`/v1/plugin/*`):**
  - Tabela `api_keys` (hash SHA-256, `key_prefix`, `allowed_domain`, `is_active`).
  - Pancerny dependency provider `get_plugin_client` weryfikujący nagłówek `X-VSE-Key` oraz domenę `X-Site-URL`.
  - Endpointy: `POST /v1/plugin/validate`, `POST /v1/plugin/preview`, `POST /v1/plugin/inject-data`.
- [ ] **4.2. Wtyczka WordPress (`vse-video-seo` na bazie 80% kodu `pressai-wp`):**
  - **Clean Head Injection:** Rejestracja pola `_vse_schema_json` w `register_post_meta` (`show_in_rest => true`) i wstrzykiwanie czystego JSON-LD (`VideoObject`, `Clip`, `FAQPage`) w sekcji `<head>` przez hook `add_action('wp_head', ...)` — zero ingerencji w `post_content`, zero błędów walidacji bloków Gutenberga!
  - **Asset Player JS:** Ładowanie lekkiego skryptu `assets/js/player.js` (2 KB) obsługującego przewijanie rozdziałów (`vseSeek`).
  - **Uniwersalny Adapter SEO:** Automatyczne zapisywanie meta title/description/focus keyword niezależnie od tego, czy klient używa **RankMath, Yoast SEO czy SEOPress**.
- [ ] **4.3. Gutenberg Sidebar UI (Aha-Moment w 30s + Upsell do Portalu):**
  - Wklejenie linku YouTube w Gutenbergu → błyskawiczny podgląd Google Rich Result, wyliczenie Video SEO Score (np. 38/100 → 92/100) i darmowe wstawienie podstawowego Schema + 3 rozdziałów (limit Free: 5 filmów/mies.).
  - Zablokowane kafelki Pro w pasku bocznym (*Pełny artykuł 800 słów z wideo*, *Screenshots HD*, *Autopilot kanału YT*, *Masowy skaner portalu*) przekierowujące bezpośrednio do rejestracji/upgrade'u w Portalu `vse.impresjapr.pl`.

---

### 🎬 FAZA 5 — Rozwój Produktu: YouTube OAuth Captions & Zaawansowane SEO *(Odzyskane z v3 i v4)*
- [ ] **5.1. Pobieranie napisów przez oficjalne YouTube Data API v3 z OAuth klienta (`captions.download`):**
  - Przekazywanie tokena OAuth z tabeli `youtube_channels` do `fetch_transcript_api_v3()` w `core/fetcher.py`.
  - **Efekt:** Dla własnych kanałów klienta podłączonych przez OAuth napisy pobierają się bezpośrednio na VPS (zero blokad IP YouTube!) oraz działają dla filmów **Prywatnych i Zaplanowanych (Private / Scheduled)** przed ich premierą!
- [ ] **5.2. Ręczny upload pliku `.vtt` / `.srt` w dashboardzie** (fallback dla filmów bez napisów).
- [ ] **5.3. Moduł M4B:** Cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **5.4. Przeglądarka kanału (`/channels`) i Channel Monitor E2E** (automatyczny nasłuch nowych filmów na kanale YT klienta).
- [ ] **5.5. Local Runner ulepszenia:** Automatyczna aktualizacja `yt-dlp` raz dziennie + raportowanie pokrycia VTT (`last segment at Xs`).
- [ ] **5.6. Batch Processing & SEO Scoring Dashboard** + tryb White-label dla planu Agency.

---

### 🌐 FAZA 6 — Integracja Ekosystemu (VSE + PressAI + SocialPulse)
- [ ] Wspólny standard kluczy API (`X-VSE-Key` / `X-PressAI-Key`) i zunifikowana tabela `api_keys`.
- [ ] Pakiet łączony (Bundle Pricing: VSE + PressAI + SocialPulse).
- [ ] Izolacja S2S dla konkurujących agencji SEO (`org_id` / competing tenants).
