# Wzorcowy Handoff: Video SEO Engine v2.2 (KROK A+B+C, Wtyczka WP v3.0, Panel `/admin`, UX `/ustawienia`, Język `be`)

- **Data:** 2026-10-20 18:00 CEST
- **Autor:** `vse-architect-01` / `vse-dev-01` (`video-seo-engine`)
- **Status produkcji (`https://vse.impresjapr.pl`):** Wszystkie kontenery (`vse-api`, `vse-web`, `vse-postgres`) działają na najnowszym kodzie z gałęzi `main`.
- **Spójność repozytorium (`GitHub == VPS == Local`):**
  - Gałąź `origin/main` na GitHub (`gitomwtyczka/video-seo-engine`), klon produkcyjny na VPS (`/home/ubuntu/video-seo-engine`) oraz lokalny klon (`c:\Users\tomas2\.gemini\antigravity\playground\video-seo-engine`) są **w 100% zsynchronizowane (`zero unpushed commits`, `working tree clean`)**.
  - Ostatnie kluczowe commity kodu:
    - `3e0cb38` — `feat(ustawienia): redesign settings layout into 4 clean cards with collapsible YT footers and download accordions`
    - `59ca091` — `feat(lang): add full Belarusian (be) language support across generator, translations and UI`
    - `c17a7a6` — `fix(pricing): unify Agency portal limit description to 50 portals across landing and cennik`
    - `212c588` / `93cf930` — `perf(jobs,pipeline): trigger in-memory asyncio.Event wakeup on POST /v1/jobs/{id}/result + LOCAL_RUNNER_POLL_INTERVAL=2.0s`
    - `87e21a3` / `4d0ed16` — `fix(generator,generate): hard anti-confabulation block HTTP 422 (0 credits charged), ASR phonetic correction, and clean_transcript field`
    - `64e83e2` / `2009f30` — `fix(pipeline,fetcher): match video channel_id for YT OAuth, DB transcript cache, multi-track fallback`
    - `581f232` / `5196757` / `a63cb06` — `feat(cennik,payments,plugin): set quotas to 5/30/110/250 and Top-Up prices to 99/249/699 PLN`

---

## 1. Obowiązujące Limity i Ceny (Zatwierdzone przez Właściciela — Stan Produkcyjny)

Wszystkie warstwy systemu (tabela `plans` w PostgreSQL, `api/main.py`, `api/quota.py`, `api/routers/plugin.py`, `api/routers/admin.py`, `api/routers/payments.py`, `scripts/setup_stripe_live.py`, `web/src/app/page.tsx`, `web/src/app/cennik/page.tsx`, `web/src/app/admin/page.tsx`) używają jednego źródła prawdy:

| Plan / Pakiet | Limit filmów | Cena | Portale WP | Języki & Funkcje |
|---|---|---|---|---|
| **Free** | **5 filmów / mies.** | **0 zł** | 0 z Dashboardu (1 przez wtyczkę WP v3.0) | 1 język, ręczne kopiowanie HTML + wtyczka WP v3.0 |
| **Starter** | **30 filmów / mies.** | **49 zł / mies.** | **3 portale WP** | Auto-publikacja 1-klikiem; opcjonalny **Add-on 8+ Języków (+29 zł/mies.)** |
| **Pro** | **110 filmów / mies.** | **149 zł / mies.** | **10 portali WP** | **Wszystkie języki w cenie** (`PL, EN, DE, ES, FR, IT, UK, BE, PT`) + YouTube OAuth |
| **Agency** | **250 filmów / mies.** | **499 zł / mies.** | **50 portali WP** | Wszystkie języki w cenie + moduł **ShortMachine 9:16** |
| **Top-Up +50** (`topup_50`) | **+50 filmów** (bezterminowo) | **99 zł** jednorazowo | — | `1,98 zł / film` — dopisywane do `extra_quota_balance` |
| **Top-Up +150** (`topup_150`) | **+150 filmów** (bezterminowo) | **249 zł** jednorazowo | — | `1,66 zł / film` — dopisywane do `extra_quota_balance` |
| **Top-Up +500** (`topup_500`) | **+500 filmów** (bezterminowo) | **699 zł** jednorazowo | — | `1,40 zł / film` — dopisywane do `extra_quota_balance` |
| **Enterprise / VIP (>250)** | Indywidualny (`custom_monthly_quota` lub `-1` = ∞) | Wycena indywidualna | Bez limitu | Nadawane ręcznie w panelu `/admin` bez udziału Stripe |

---

## 2. Architektura Kluczowych Modułów (v2.2)

### A. Architektura Pobierania Transkryptów i Blokada Anty-Konfabulacyjna (`api/services/pipeline.py`, `core/fetcher.py`, `core/generator.py`)
1. **Krok 0 — Dopasowanie kanału YouTube OAuth po `channel_id`:**
   - Funkcja `_get_user_yt_access_tokens(user_id, target_channel_id=metadata.channel_id)` porównuje `channel_id` filmu z podłączonymi kanałami OAuth użytkownika (`youtube_channels`).
   - Jeśli film należy do podłączonego kanału użytkownika, jego token OAuth jest próbowany jako pierwszy w `fetch_transcript_api_v3()` (z obsługą multi-track fallback dla ścieżek ASR/manualnych).
   - Jeśli film pochodzi z **obcego kanału**, pipeline nie marnuje czasu na `403 Forbidden` z YouTube Captions API i natychmiast przechodzi do Cache DB / Local Runnera.
2. **Krok 1 — DB Transcript Cache (`usage_logs` / `transcript_jobs`):**
   - Jeśli ten sam `video_id` miał już wcześniej pobrany transkrypt VTT w bazie, pipeline pobiera go natychmiast z bazy (`0.01s`).
3. **Krok 2 — VSE Local Runner z Instant Wakeup (`asyncio.Event`):**
   - Tworzy lub reużywa zadanie w `transcript_jobs` (`status='pending'`).
   - Gdy Local Runner na komputerze użytkownika odeśle wynik przez `POST /v1/jobs/{job_id}/result` (`api/routers/jobs.py`), wywoływane jest `notify_transcript_job_ready(job_id)`, które ustawia `asyncio.Event` w pamięci procesu i budzi oczekujący request w **~0.001s** (fallback polling co `LOCAL_RUNNER_POLL_INTERVAL = 2.0s`, maksymalny czas oczekiwania `LOCAL_RUNNER_TIMEOUT = 90.0s`).
   - Endpoint `/v1/jobs/{job_id}/result` akceptuje również wyniki ze statusem `cloud_fallback` / `processing`.
4. **Krok 3 — Twarda Blokada Anty-Konfabulacyjna (`HTTP 422 Unprocessable Entity` + `0 kredytów`):**
   - Całkowicie usunięto dawne generowanie artykułów z samych metadanych (tytułu/opisu), które powodowało halucynacje AI.
   - Gdy wszystkie ścieżki zawiodą (brak napisów na filmie i brak odpowiedzi Local Runnera), pipeline rzuca `TranscriptUnavailableError`, a `POST /v1/generate` oraz `POST /v1/plugin/generate` zwracają `HTTP 422` z czytelną instrukcją dla użytkownika i **nie pobierają kredytu z konta (`0 credits charged`)**.
5. **Krok 4 — Korekta fonetyczna ASR i pole `clean_transcript` (`core/generator.py`):**
   - Prompt systemowy Claude zawiera twardy zakaz konfabulacji, nakaz weryfikacji nazwisk i nazw własnych względem tytułu/opisu filmu (naprawa błędów fonetycznych ASR) oraz generuje dodatkowe pole `clean_transcript` (oczyszczony, zredagowany transkrypt z akapitami i śródtytułami `<h3>`), wyświetlane w nowej zakładce **„📜 Czysty Transkrypt”** w Dashboardzie.

### B. Wtyczka WordPress `vse-video-seo` v3.0.0 (`plugins/vse-video-seo/` + `api/routers/plugin.py`)
- **Pobieranie paczki `.zip`:** `GET /v1/plugin/download` oraz `HEAD /v1/plugin/download` dynamicznie pakują aktualny katalog `plugins/vse-video-seo/` w locie.
- **Auto-Parowanie bez Application Passwords:** Wklejenie klucza `vse_live_...` w WP Admin wywołuje `POST /v1/plugin/validate` z `site_url` i `plugin_secret`, automatycznie tworząc/aktualizując portal w `wp_portals` (`auth_mode="plugin_token"`).
- **Publikacja z Dashboardu VSE do WP:** Przycisk „Publikuj do WordPress” dla portalu z `auth_mode="plugin_token"` uderza do `POST /wp-json/vse/v1/publish` z nagłówkiem `X-VSE-Plugin-Secret` (z automatycznym fallbackiem do `/wp-json/wp/v2/posts`).
- **Funkcje wewnątrz WP Admin:** Menu boczne `🎬 VSE Video SEO` (Generator AI, Biblioteka / Historia VSE za 0 kredytów, Ustawienia API), Classic Meta Box pod edytorem oraz Gutenberg Sidebar + wstrzykiwanie JSON-LD (`VideoObject + Clip + FAQPage`) w `wp_head`.

### C. Panel Administratora `/admin` (`web/src/app/admin/page.tsx` + `api/routers/admin.py`)
- Pozwala właścicielowi zarządzać dowolnym kontem bez udziału Stripe: zmiana planu (`free / starter / pro / agency`), włączanie `has_multilang_addon`, ustawianie indywidualnego limitu miesięcznego VIP (`custom_monthly_quota` lub `-1` = Nielimitowany), doładowywanie bezterminowych kredytów Top-Up (`extra_quota_balance`) oraz ręczne zerowanie/anulowanie subskrypcji.

### D. Nowy układ strony `/ustawienia` (`web/src/app/ustawienia/page.tsx`, commit `3e0cb38`)
- Uporządkowany w **4 czyste karty** (bez dawnego duplikatu sekcji „Plan subskrypcji”):
  1. **👤 Konto & Subskrypcja** (połączona karta: email, plan, odznaki `8 Jęz.` / `VIP`, `⚙ Zarządzaj subskrypcją`, `↑ Zmień plan / Dokup Top-Up`, pasek zużycia i saldo Top-Up).
  2. **🌐 Portale WordPress (Auto-Publikacja 1-klikiem)** (lista portali z plakietkami `🔌 Wtyczka v3.0 (Auto-Parowanie)` vs `🔑 App Password`, przycisk dodawania i kotwica do akordeonu wtyczki).
  3. **▶️ Kanały YouTube (OAuth 2.0)** (kompaktowa lista kanałów ze zwijaną edycją stopki pod przyciskiem `📝 Edytuj stopkę kanału ▾`).
  4. **📦 Wtyczki, Integracje API & Narzędzia do pobrania** (2 zwijane akordeony: `#wp-plugin` dla Wtyczki WP v3.0 + Kluczy API oraz `#local-runner` dla VSE Local Runner).

---

## 3. Co zostało do zrobienia w kolejnej sesji (Pending)

1. **Test praktyczny Wtyczki WordPress v3.0.0 na żywych portalach:**
   - Po pobraniu i zainstalowaniu świeżej paczki `.zip` z `/ustawienia` (`#wp-plugin`) zweryfikować E2E auto-parowanie, generowanie bezpośrednio z WP Admin oraz 1-klikowy import z historii VSE za `0 kredytów`.
2. **Przełączenie Stripe z `sk_test_` na `sk_live_` (po decyzji Właściciela):**
   - Podmienić `STRIPE_SECRET_KEY` i `STRIPE_WEBHOOK_SECRET` w `.env` na VPS i wykonać:
     ```bash
     docker exec vse-api python3 /app/scripts/setup_stripe_live.py
     ```
3. **Kolejne fazy Master Roadmap v2.2:**
   - **Faza 5.3:** Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów).
   - **Faza 5.4:** Moduł M4B — cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
   - **Faza 5.5:** Przeglądarka kanału (`/channels`) i Channel Monitor E2E.
