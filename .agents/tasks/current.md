# Current Tasks (Stan na 18.10.2026)

## ✅ Zamknięte (Etap 1 + Faza 2B, 3.1-3.2, 4, 4.5/5.2, 5.1, WP Plugin v3.0 + Model >250 filmów + Admin Quota Management)
- [x] **Wtyczka WordPress `vse-video-seo` v3.0 + Model >250 filmów (Top-Up + VIP Quota) + Rozbudowa `/admin` (`3cb5a15`, `46f79ac`, `571f237`, `325ece7`):**
  - **Wtyczka WordPress v3.0 (`plugins/vse-video-seo/`):** Główna pozycja w lewym menu WP Admin (`🎬 VSE Video SEO` z podstronami: *Generuj z YouTube*, *Historia / Biblioteka VSE*, *Połączenie & Quota*), natywny Meta Box pod edytorem wpisu/strony (Gutenberg + Classic Editor), 1-Click Full Package (*Artykuł SEO + TL;DR + Rozdziały Key Moments + FAQ + Schema JSON-LD do `<head>` + synchronizacja RankMath/Yoast/SEOPress*), pobieranie historii generacji z VSE za **0 kredytów** (`POST /v1/plugin/history`, `POST /v1/plugin/history-item`), zewnętrzne endpointy `/wp-json/vse/v1/ping` i `/wp-json/vse/v1/publish` z autoryzacją `X-VSE-Key-Hash` (Push z VSE do WordPressa **bez Application Passwords**) oraz automatyczne parowanie portalu (`auth_mode="plugin_token"`) przy walidacji klucza (`POST /v1/plugin/validate`).
  - **Pobieranie paczki `.zip` (`GET/HEAD /v1/plugin/download`):** Dynamiczne generowanie `vse-video-seo.zip` (v3.0.0) gotowego do bezpośredniego wgrania w WP Admin (*Wtyczki -> Dodaj nową -> Wyślij wtyczkę na serwer*).
  - **Model >250 filmów (Pakiety Top-Up + Custom/VIP Quota):** Kolumny `extra_quota_balance` (bezterminowa pula kredytów nieprzepadająca na koniec miesiąca) oraz `custom_monthly_quota` (`NULL` = domyślny limit planu, `-1` = Unlimited, `>0` = indywidualny limit VIP/Enterprise). Endpoint `POST /v1/payments/checkout-topup` oraz idempotentna obsługa webhooka/verify-session dla pakietów: `+50 filmów` (`39 PLN`), `+150 filmów` (`99 PLN`), `+500 filmów` (`279 PLN`). Automatyczny fallback w `api/quota.py` i `api/routers/plugin.py` pobierający 1 kredyt z `extra_quota_balance` po wyczerpaniu limitu miesięcznego.
  - **Rozbudowa panelu `/admin` (`api/routers/admin.py`, `web/src/app/admin/page.tsx`):** Zarządzanie planem, przełącznikiem MultiLang Add-on, indywidualnym limitem miesięcznym (VIP / Unlimited `-1`), ręcznym doładowaniem puli Top-Up (`+50`, `+150`, `+500` lub dowolna wartość) oraz bezpiecznikiem anulowania starej subskrypcji Stripe jednym kliknięciem bez wchodzenia do bazy danych.
- [x] **Faza 4.5 / 5.2: Wielojęzyczność — Cross-Language & Per-Material Translation Engine („Złoty Środek”, `93cef05`):**
  - **Backup & One-Click Revert (`backup/pre-multilang-20261017`):** Dedykowana gałąź Git na GitHubie (`140b478`), snapshot `/home/ubuntu/scripts/backup_pre_deploy.sh`, tagi obrazów Docker `video-seo-engine-vse-api:rollback-pre-multilang` (`8145bb467860`) i `video-seo-engine-vse-web:rollback-pre-multilang` (`d0003a06fd0a`) oraz wykonywalny skrypt `/home/ubuntu/scripts/revert_vse_multilang.sh` (`chmod +x`).
  - **KROK 1–6:** Uniwersalne wykrywanie języka źródłowego, 8-języczny fallback napisów, architektura Dual-Language Anchor, `adapt_material_language()`, Stripe Add-on (+29 PLN/mies.) i wdrożenie E2E na produkcję.
- [x] **Etap 1 + Faza 2B, 3.1-3.2, 4, 5.1 (Komercjalizacja VSE v2.0):**
  - Wszystkie wcześniejsze zadania Etapu 1, wtyczki WordPress `vse-video-seo` (`/v1/plugin/*`) oraz YouTube Data API v3 OAuth Captions (`1ccbf8d`, `bd82107`, `128570b`) zamknięte i wdrożone.

---

## 🟡 W toku
- Brak zadań w toku — wdrożenie Wtyczki WordPress v3.0, pakietów Top-Up (+50/+150/+500) oraz rozbudowy panelu `/admin` zamknięte i zweryfikowane E2E na produkcji.

---

## 🔵 Następne (Zgodnie z Master Roadmap v2.1 — Fazy 5.3–5.7, 6)
- [ ] **Faza 5.3:** Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów).
- [ ] **Faza 5.4:** Moduł M4B — cytaty z klikalnymi deep-linkami czasowymi (fuzzy match VTT → timestamp).
- [ ] **Faza 5.5:** Przeglądarka kanału (`/channels`) i Channel Monitor E2E z izolacją `user_id`/`tenant_id`.
- [ ] **Faza 5.6 & 5.7:** Local Runner auto-update `yt-dlp` + raportowanie pokrycia VTT oraz Batch Processing & SEO Scoring Dashboard.
- [ ] **Faza 6:** Integracja ekosystemu (VSE + PressAI + SocialPulse — wspólne klucze API i Bundle Pricing).
