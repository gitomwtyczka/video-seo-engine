# Handoff: Komercjalizacja VSE v2.2 (Limity 5/30/110/250, Pakiety Top-Up 99/249/699 zł, Panel `/admin`) + Wtyczka WordPress (`vse-video-seo` v3.0.0)

- **Data:** 2026-10-20 13:00
- **Autor:** `vse-dev-01` / Supervisor 01 (`video-seo-engine`)
- **Status produkcji (`https://vse.impresjapr.pl`):** Kod wdrożony na gałęzi `main` w GitHub (`gitomwtyczka/video-seo-engine`), baza `vse-postgres` (`plans`) zaktualizowana do limitów `5 / 30 / 110 / 250`.

---

## 1. Co zostało zrealizowane w wydaniu v2.2 (Stan Aktualny)

1. **Zatwierdzone Limity Planów Bazowych (`5 / 30 / 110 / 250`) i Pakiety Top-Up (`99 / 249 / 699 zł`):**
   - We wszystkich warstwach (`api/main.py`, `api/routers/plugin.py`, `api/routers/admin.py`, `web/src/app/cennik/page.tsx`, `web/src/app/page.tsx`, `web/src/app/admin/page.tsx`, `scripts/setup_stripe_live.py` oraz bezpośrednio w tabeli `plans` w PostgreSQL) obowiązują spójne limity:
     - `Free`: **5 filmów / mies.** (`0 zł`, `1 portal WP`)
     - `Starter`: **30 filmów / mies.** (`49 zł`, `3 portale WP`, opcjonalny Add-on 8 Języków `+29 zł/mies.`)
     - `Pro`: **110 filmów / mies.** (`149 zł`, `10 portali WP`, `8 języków w cenie`)
     - `Agency`: **250 filmów / mies.** (`499 zł`, `50 portali WP`, `8 języków w cenie + moduł ShortMachine`)
   - **Pakiety Top-Up (`api/routers/payments.py` + `web/src/app/cennik/page.tsx`):** Bezterminowe kredyty (`extra_quota_balance`), które nie przepadają z końcem miesiąca i nie kanibalizują abonamentów:
     - `topup_50`: **+50 filmów — 99 zł** (`9900 gr`, `1,98 zł / film`)
     - `topup_150`: **+150 filmów — 249 zł** (`24900 gr`, `1,66 zł / film`)
     - `topup_500`: **+500 filmów — 699 zł** (`69900 gr`, `1,40 zł / film`)
   - **Sekcja Enterprise (>250 filmów/mies.):** Na `/cennik` dodano baner informujący o możliwości skorzystania z pakietów Top-Up lub indywidualnie negocjowanego Planu Enterprise / Media House (`custom_monthly_quota`).

2. **Wtyczka WordPress `vse-video-seo` v3.0.0 (`plugins/vse-video-seo/` + `api/routers/plugin.py`):**
   - **Menu Główne w WP Admin (`🎬 VSE Video SEO`):** Dedykowana pozycja w pasku bocznym WordPressa z 3 zakładkami: *Generator AI (YouTube → Wpis WP)*, *Biblioteka / Historia VSE (import gotowych materiałów za 0 kredytów)* oraz *Klucz API & Status Połączenia*.
   - **Klasyczny Meta Box (`add_meta_box`) + Gutenberg Sidebar:** Widoczny pod każdym wpisem/stroną (Classic Editor + Gutenberg). Pozwala jednym kliknięciem wygenerować i wstawić pełny pakiet VSE (Artykuł HTML + osadzone wideo + TL;DR + Rozdziały + FAQ + Schema JSON-LD w `<head>` + pola RankMath / Yoast / SEOPress) lub zaimportować wcześniej wygenerowany materiał z historii VSE za **0 kredytów**.
   - **Dwukierunkowy Most VSE ↔ WordPress bez Application Passwords:**
     - Walidacja klucza `POST /v1/plugin/validate` automatycznie paruje portal w tabeli `wp_portals` (`auth_mode="plugin_token"`).
     - Endpoint wtyczki `POST /wp-json/vse/v1/publish` odbiera publikacje bezpośrednio z przycisku „Publikuj do WordPress” w panelu `vse.impresjapr.pl` (z automatycznym fallbackiem do `/wp-json/wp/v2/posts`).

3. **Panel Administratora `/admin` (Zarządzanie bez Stripe):**
   - Rozbudowany endpoint `PATCH /v1/admin/users/{id}/plan` oraz modal `ChangePlanModal` w `web/src/app/admin/page.tsx` umożliwiają ręczne nadawanie planu bazowego (`5 / 30 / 110 / 250`), aktywację pakietu `MultiLang`, ustawianie indywidualnego limitu miesięcznego VIP (`custom_monthly_quota` lub `-1` Nielimitowany), doładowywanie darmowych kredytów Top-Up (`+50 / +150 / +500`) oraz anulowanie subskrypcji Stripe jednym kliknięciem.

4. **Multi-Language Engine v2.1:**
   - Wsparcie dla 8 języków (`PL, EN, DE, ES, FR, IT, UK, PT`), architektura *Dual-Language Anchor* zachowująca precyzyjne timestampy VTT oraz tłumaczenie pojedynczych zakładek i całego pakietu bez zużywania limitu filmów.

---

## 2. Kolejne kroki (Pending Roadmap)

1. **Przełączenie Stripe z `sk_test_` na `sk_live_` (po decyzji Właściciela):**
   - Po podmianie kluczy w `.env` na VPS uruchom:
     ```bash
     docker exec vse-api python3 /app/scripts/setup_stripe_live.py
     ```
2. **Faza 5 (Kolejne funkcje produktowe):**
   - `5.3` Ręczny upload pliku `.vtt` / `.srt` w dashboardzie (fallback dla filmów bez napisów),
   - `5.4` Moduł M4B: Cytaty z klikalnymi deep-linkami czasowymi,
   - `5.5` Przeglądarka kanału (`/channels`) i Channel Monitor E2E.
