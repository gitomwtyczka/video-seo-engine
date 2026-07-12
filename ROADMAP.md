# VSE — Video SEO Engine | Roadmap Produktowy

> Ostatnia aktualizacja: 2026-07-12 | Supervisor 01  
> Status: 🟡 Faza 3 KOMERCJALIZACJA MVP W TOKU

---

## 🚨 ZNANY PROBLEM — UI podglądu YT i footer_text (NIE ZAMYKAJ BEZ PRZECZYTANIA)

> Wpisane: 2026-07-12 [Supervisor 01] — powtórzony problem przez 2-3 sesje

### Czego brakuje w UI:
1. **Podgląd opisu YouTube** przed kliknięciem "Wyślij na YouTube" — textarea pokazująca pełny zbudowany opis (M1-M8) zanim coś zostanie wysłane
2. **Pole footer_text per kanał** — edytowalne w ustawieniach kanału YT

### Historia prób:
- Fix dispatch: `dispatch_vse_yt_preview.md` (nie wdrożony)
- Wielokrotne próby dodania komponentów — nie widoczne w UI
- Hipoteza: stary komponent modalny ma pierwszeństwo przed nowym i go przesłania

### Stan na 2026-07-12:
- Analityk dispatched: `tmp/dispatch_vse_analyst_ui.md`
- Analityk ma odpowiedzieć: gdzie blokada, co dokladnie zmienić, który modal ma pierwszeństwo
- **DO NASTĘPNEJ SESJI: przeczytaj raport analityka z inbox przed wdrożeniem**
  `sonic-void/.agents/reports/inbox/2026-07-12_vse-analyst_ui-preview-footer.md`

### Backend gotowy (tylko UI do zrobienia):
- `GET /v1/youtube/channels` — zwraca `footer_text` ✅
- `PUT /v1/youtube/channels/{id}` — zapisuje `footer_text` ✅  
- `build_yt_description()` — używa `footer_text` z DB ✅
- Endpoint `/v1/youtube/publish-description` — server-side składa M1-M8 ✅

---

## ⚠️ Znane ograniczenia systemu

### Filmy prywatne i zaplanowane (“private” / “scheduled”) — brak transkryptu

**Objaw:** Rozdziały (0), opis bez timestampów.

**Przyczyna:** yt-dlp nie może pobrać VTT dla filmów prywatnych. Wymaga OAuth właściciela.

**Workaround:** Ustaw na `Unlisted` przed generowaniem → generuj → wyślij opis → z powrotem `Private`.

**Docelowe:** OAuth do prywatnych filmów (Faza 7) lub ręczny upload VTT w dashboardzie.

---

## Dwa tryby pracy — Use Cases produktu

### 🎬 Use Case A — Paste URL (obecny flow, działa)

> Użytkownik wkleja link do dowolnego wideo YouTube → system pobiera transkrypt → generuje SEO schema → użytkownik publikuje na wybranym portalu WP.

```text
Użytkownik wkleja URL YouTube
         ↓
   /dashboard — formularz
         ↓
   Local Runner (Windows PC)
   └─ youtube-transcript-api → [MM:SS] VTT format
         ↓
   FastAPI pipeline
   └─ generator.py → LLM (Gemini/Claude)
   └─ schema JSON-LD: title, description, chapters, FAQ, lead, article_body
         ↓
   Dashboard: podgląd artykułu + rozdziały z czasami
         ↓
   [Wybierz portal WP] → /v1/inject → WordPress REST API
```

**Status:** Działa end-to-end.

---

### 📺 Use Case B — YouTube Channel Manager (NOWY — wymagany)

> Użytkownik loguje się swoim kontem YouTube (OAuth) → widzi swój kanał → masowo optymalizuje opisy, tytuły, rozdziały bez wychodzenia z VSE.

**Wymagane OAuth scope:** `https://www.googleapis.com/auth/youtube`

**Status:** Część infrastruktury wdrożona. Panel do zarządzania w trakcie projektowania.

---

## Architektura systemu

```text
vse.impresjapr.pl
│
├── / (Next.js frontend — port 3000)
│   ├── /dashboard — Use Case A: wklej URL → generuj → inject
│   ├── /channels — Use Case B: kanały YouTube (PLANNED)
│   ├── /settings — portale WP, API keys, połączenia OAuth
│   ├── /admin — panel administracyjny (✅ LIVE)
│   └── /pricing
│
└── /v1/* (FastAPI backend — port 8085)
    ├── /v1/generate    ← generowanie schema z transkryptu ✅
    ├── /v1/inject      ← wstrzykiwanie do WP ✅
    ├── /v1/jobs/*      ← Local Runner polling ✅
    ├── /v1/users/*     ← konta, plany, quotas ✅
    ├── /v1/admin/*     ← admin endpoints ✅
    └── /v1/youtube/*   ← YouTube Data API proxy ✅ (w toku)
```

---

## ✅ Faza 1 — CLI Pipeline i Infrastruktura Core (DONE)

- [x] Core pipeline v5.4 (VideoObject + Clip + FAQ)
- [x] VTT fetching bez API key
- [x] Local Runner (Windows Service) + VTT Timestamps
- [x] Nginx routing + FastAPI service
- [x] Claude (Anthropic) LLM provider
- [x] inject_video + YouTube description update (OAuth)
- [x] RankMath integration

## ✅ Faza 2A — VSE API Service i Admin Panel (DONE)

- [x] FastAPI app, PostgreSQL, Auth JWT
- [x] POST /v1/generate, /v1/inject operacyjne
- [x] Next.js 14 dashboard
- [x] Admin Panel
- [x] Deployment oracle-crimson — LIVE

## 🟡 Faza 2B — YouTube Unblock + E2E (IN PROGRESS)

- [x] Local Runner (Windows Service) — zastąpił cookies.txt
- [ ] POST /v1/monitor/start — testy E2E
- [ ] deno JS runtime w api/Dockerfile

## 🔴 Faza 3 — VSE Komercjalizacja MVP

- [x] ✅ **PressAI YT Description pipeline** — pełny opis M1-M8 z crimson-void (2026-07-12)
- [x] ✅ **YouTube publish-description** — server-side `build_yt_description` (2026-07-12)
- [x] ✅ **Formatowanie rozdziałów** — `ROZDZIALY:` + `00:00 Tytuł`, deduplikacja (2026-07-12)
- [x] ✅ **M2 placeholder** — `[WSTAW LINK]` gdy brak wp_url (2026-07-12)
- [x] ✅ **Aktualizacja tytułu YT** — `update_youtube_metadata` (2026-07-12)
- [ ] 🔴 Stripe checkout flow
- [ ] 🔴 Terms of Service + Privacy Policy
- [ ] 🟡 Email verification, Google OAuth login
- [ ] 🟡 Landing page + pricing
- [x] ✅ Pre-deploy backup system

## 🔵 Faza 4 — Dashboard UI YT + Inject Flow (NEXT — PRIORYTET)

> ⚠️ BLOKERY UI — przeczytaj sekcję "ZNANY PROBLEM" na górze przed implementacją!

### UI podglądu YT (wielokrotnie próbowane, jeszcze niewidoczne)
- [ ] **Podgląd opisu YT** — textarea w dashboardzie PRZED kliknięciem "Wyślij na YouTube"
  - Backend: endpoint `/v1/preview-yt-description` — dispatch gotowy w `tmp/dispatch_vse_yt_preview.md`
  - Problem: stary modal ma pierwszeństwo, nowy nie jest renderowany
  - Analityk: `inbox/2026-07-12_vse-analyst_ui-preview-footer.md` — PRZECZYTAJ PRZED WDROŻENIEM
- [ ] **footer_text per kanał** — pole edytowalne w ustawieniach kanału
  - Backend: `PUT /v1/youtube/channels/{id}` — gotowy ✅
  - Problem: brak UI do edycji
  - Analityk: jw.

### M4B cytaty (z VTT — nowe)
- [ ] **M4B: cytaty z deep linkami** — fuzzy match VTT → timestamp → cytat z linkiem
  - Wymaga: transkrypt VTT + logika fuzzy match w inject.py
  - Spec: 2-3 cytaty per opis

### Pozostałe
- [ ] Aktualizacja tytułu YT w UI (frontend przekazuje `yt_title` z schema_data)
- [ ] Fix emoji UTF-8 w dashboard
- [ ] Batch processing
- [ ] SEO Scoring dashboard

## 🔵 Faza 5 — Zarządzanie Portalami WordPress

- [ ] Endpointy i UI dla /settings → Portale WordPress
- [ ] Szyfrowanie Application Passwords w DB
- [ ] Opcjonalna user federation VSE↔PressAI

## 🔵 Faza 6 — Billing

- [ ] Stripe Checkout, Tax, /pricing, Billing portal

## 🔵 Faza 7 — YouTube Channel Manager / Use Case B

- [ ] Połączenie konta YouTube (Google OAuth)
- [ ] Przeglądarka kanału (/channels)
- [ ] **OAuth dostęp do prywatnych/zaplanowanych filmów** *(workaround: Unlisted przed generowaniem)*
- [ ] Ręczny upload pliku VTT w dashboardzie

## 🔵 Faza 8 — WordPress Plugin + Enterprise

- [ ] WordPress plugin (pressai-video-seo) freemium
- [ ] Bundle pricing VSE+PressAI
- [ ] White-label (Agency)

---

## ⚙️ Zasady operacyjne — Local Runner

**Local Runner (Windows Service) MUSI działać standalone** — zero manualnych kroków instalacji.

- ✅ Wszystkie zależności bundlowane
- ✅ Instalacja = rozpakuj + uruchom install script
- ❌ Zakaz: wymagania instalacji Python osobno

---

*[Supervisor 01 | sonic-void | 2026-07-12] — aktualizacja po sesji: YT pipeline, UI blokery, M4B spec*
