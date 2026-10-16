# 🎯 DISPATCH: VSE Commercial v2.0 (Etap 1 Deploy + Faza 4 Wtyczka WP + Faza 5.1 YouTube OAuth)

> **Data:** 16.10.2026  
> **Nadawca:** Supervisor 01 (`sonic-void`)  
> **Odbiorca:** Agent Workspace `video-seo-engine` (`vse-dev-01`, `vse-worker`)  
> **Status:** AKTYWNY DO REALIZACJI  
> **Kontekst:** Wdrożenie przygotowanego Etapu 1, wdrożenie mikro-wtyczki WP oraz integracja YouTube Data API OAuth Captions  

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)
1. **Mandatory Pre-Deploy Backup:** Przed jakimkolwiek dotknięciem kodu lub kontenerów na VPS Oracle (`147.224.162.100`), ZAWSZE uruchom:
   ```bash
   ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
   ```
2. **SCP na Windows:** ZAWSZE używaj pełnych ścieżek Windows (np. `C:\Users\tomas2\...`), NIGDY znaku `~` w ścieżce lokalnej.
3. **Migracje PostgreSQL:** Pamiętaj, że `Base.metadata.create_all` NIE modyfikuje istniejących tabel – wszelkie nowe kolumny muszą mieć `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` w `api/main.py`.
4. **Post-Action Gate:** Po każdym deployu sprawdź logi kontenerów: `docker logs --tail 20 vse-api` oraz `docker logs --tail 20 vse-web`.
5. **Punkt One-Click Revert:** Na wypadek jakichkolwiek problemów ze stanem roboczym masz utworzony lokalny snapshot `backup/pre-v2-commercial-20261016` oraz plik patcha `backup_pre_v2_commercial_diff.patch`.

---

## 📋 1. Stan Wyjściowy (Co Zostało Przygotowane w Etapie 1)

W gałęzi `refactor/dashboard-modularization` przygotowano i przetestowano syntaktycznie kompletny zestaw zmian:
1. **Modularność Dashboardu:** Podział monolitu `dashboard-inner.tsx` na podkomponenty, wydzielenie `types.ts` i `utils.ts`, poprawka `overrideDescription` w `YouTubePublishModal.tsx`.
2. **Hotfix P0 #1 (White-Label):** Usunięcie hardcodowanego `"redaktorem portalu prawy.pl"` na rzecz dynamicznego `site_brand` portalu klienta.
3. **Hotfix P0 #2 (SaaS Transcript 403):** Przekazywanie `user_id` w `pipeline.py` i poprawne sprawdzanie uprawnień w `jobs.py`.
4. **Hotfix P0 #3 & Model Tiering:** Wymuszenie Gemini 2.5 Flash w planach Free i Starter, twarda blokada limitu miesięcznego `monthly_quota`, auto-fallback `Claude → Gemini` przy błędach API.
5. **Rejestracja Tokenów i Kosztów:** Wątkowy tracker tokenów w `core/generator.py` (`contextvars.ContextVar`), funkcja `calculate_cost_usd`, rozszerzenie `UsageLog` oraz migracja `ALTER TABLE usage_logs` w `api/main.py`.
6. **Poprawka Przekazywania `user_id` w Pipeline:** `run_process` w `api/services/pipeline.py` oraz `api/routers/process.py` w pełni przekazują `user_id`.
7. **Cennik i Landing Page:** Usunięcie cen 29/99/299 zł i słowa „Nieograniczony”, wyrównanie cennika z `ROADMAP.md` (Free 5, Starter 49 zł / 50 filmów, Pro 149 zł / 250 filmów, Agency 499 zł / 1000 filmów).

---

## 🚀 2. Kolejne Zadania do Wykonania

### 📌 Zadanie 1: QA, Merge & Deploy Etapu 1 na Produkcję
1. **Weryfikacja QA:**
   - Wykonaj testowy build frontendu w `web/`: `npm run build` (upewnij się, że TypeScript i Next.js nie zgłaszają błędów).
   - Sprawdź kompilację backendu: `python -m py_compile api/main.py core/generator.py api/services/pipeline.py`.
2. **Commit & Merge:**
   - Zatwierdź zmiany na branchu `refactor/dashboard-modularization`:
     `git commit -am "feat(commercial-v2): stage 1 stabilization, modular dashboard, token logging and model tiering"`
   - Scal branch do `main` (`git checkout main && git merge refactor/dashboard-modularization`).
3. **Pre-Deploy Backup na VPS:**
   - Połącz się przez SSH i uruchom snapshot:
     ```bash
     ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
     ```
4. **Wdrożenie Kontenerów:**
   - Wdróż zaktualizowany kod na serwerze Oracle VPS (`147.224.162.100`) w `/home/ubuntu/video-seo-engine`:
     `git pull origin main && docker compose -f docker-compose.vse.yml up -d --build`
   - Sprawdź `curl https://vse.impresjapr.pl/health` oraz logi `docker logs --tail 30 vse-api`.

---

### 📌 Zadanie 2: Faza 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet)
1. **Backend VSE (Klucze Licencyjne API):**
   - Utwórz model i tabelę `api_keys` (`id`, `user_id`, `key_hash`, `key_prefix`, `allowed_domain`, `is_active`, `created_at`).
   - Wdrożenie endpointów:
     - `POST /v1/plugin/validate` – sprawdza ważność klucza i powiązanej domeny.
     - `POST /v1/plugin/preview` – generuje darmowy podgląd Google Rich Result + Score.
     - `POST /v1/plugin/inject-data` – zwraca payload JSON-LD do wstrzyknięcia.
2. **Budowa Wtyczki WordPress (`plugins/vse-video-seo/`):**
   - Wykorzystaj 80% architektury z repozytorium `pressai-wp`.
   - **Clean Head Injection:** Zapisuj Schema do meta pola wpisu `_vse_schema_json` i wstrzykuj czysty tag `<script type="application/ld+json">` przez hook `add_action('wp_head', ...)` – całkowite ominięcie filtra `wp_kses_post`!
   - **Uniwersalny Adapter SEO:** Zapis do RankMath (`rank_math_title`, `rank_math_description`), Yoast (`_yoast_wpseo_title`, `_yoast_wpseo_metadesc`) lub SEOPress.
   - **Player Script:** Dołącz lekki skrypt JS (`assets/js/player.js`) obsługujący interaktywne rozdziały.
3. **Gutenberg Sidebar UI:**
   - Panel boczny w edytorze wpisu (Sidebar Plugin).
   - Wklejenie linku wideo → wyliczenie Video SEO Score + podgląd Rich Result w Google.
   - Darmowe dodanie Schema dla pierwszych 5 filmów w miesiącu.
   - Banery Pro z bezpośrednim przekierowaniem do zakupu planu na `vse.impresjapr.pl`.

---

### 📌 Zadanie 3: Faza 5.1 — YouTube Data API v3 OAuth Captions
1. **Cel:** Ominięcie blokad IP datacenter YouTube oraz obsługa filmów **Prywatnych i Zaplanowanych (Private / Scheduled)**.
2. **Implementacja w `core/fetcher.py`:**
   - Zaktualizuj `fetch_transcript_api_v3(video_id, access_token)`.
   - W `api/services/pipeline.py` pobierz aktywny `access_token` z tabeli `youtube_channels` dla danego `user_id` i przekaż do fetchera.
   - Jeśli kanał jest powiązany przez OAuth, pobierz napisy bezpośrednio przez oficjalne YouTube API endpoint: `GET https://www.googleapis.com/youtube/v3/captions/{id}`.
3. **Fallback:** Jeśli kanał nie jest podpięty lub film nie należy do użytkownika, kontynuuj dotychczasową ścieżkę (`youtube-transcript-api` → `VSELocalRunner` → Graceful Degradation).

---

## 📈 3. Definition of Done dla Zadań
- [ ] Etap 1 przetestowany, scalony do `main` i wdrożony na `vse.impresjapr.pl`.
- [ ] Tabela `usage_logs` poprawnie rejestruje tokeny wejściowe, wyjściowe i szacowany koszt USD.
- [ ] Mikro-wtyczka `vse-video-seo` przetestowana na testowej instancji WordPressa.
- [ ] Napisy z filmów zaplanowanych/prywatnych pobierają się bezbłędnie przez OAuth token.
