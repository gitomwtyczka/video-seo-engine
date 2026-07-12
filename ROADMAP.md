# VSE — Video SEO Engine | Roadmap Produktowy

> Ostatnia aktualizacja: 2026-07-12 | Antigravity  
> Status: 🟡 Faza 3 KOMERCJALIZACJA MVP W TOKU  
> **Adnotacja 2026-07-10:** Usunięto VPS Cookie fetcher na rzecz LocalRunnera — strategia cookies.txt dla VPS została oznaczona jako ZROBIONE / NIEAKTUALNE. Wdrożono Windows Service po stronie środowiska użytkownika.

---

## ⚠️ Znane ograniczenia systemu

### Filmy prywatne i zaplanowane (“private” / “scheduled”) — brak transkryptu

**Objaw:** “Rozdziały (0)”, “Brak rozdziałów w wygenerowanej schemacie”, opis YT bez timestampów.

**Przyczyna:** yt-dlp nie może pobrać napisw (VTT) dla filmów prywatnych lub zaplanowanych.
YouTube API udostępnia napisy prywatnych filmów tylko przez OAuth z uprawnieniami właści ciela kanału.

**Skutek braku VTT:**
- Brak rozdziałów z timestampami (M4)
- PressAI generuje opis bez sekcji czasowych
- Pipeline działa w trybie `partial_result=True`

**Obecny workaround (bez kodu):**
1. Ustaw film na `Unlisted` przed generowaniem SEO
2. Wygeneruj + wyślij opis na YouTube
3. Zmień film z powrotem na `Private` lub `Scheduled`

**Docelowe rozwiązanie:** OAuth do prywatnych filmów (Faza 7) lub ręczny upload pliku VTT w dashboardzie.

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

**Status:** Działa end-to-end. Brakuje UI artykułu (D2) i inject flow z podglądem (D3).

---

### 📺 Use Case B — YouTube Channel Manager (NOWY — wymagany)

> Użytkownik loguje się swoim kontem YouTube (OAuth) → widzi swój kanał → masowo optymalizuje opisy, tytuły, rozdziały bez wychodzenia z VSE.

```text
Użytkownik łączy konto Google (YouTube Data API v3)
         ↓
   /channels — lista kanałów / filmów
   └─ YouTube Data API: GET playlistItems, GET videos
         ↓
   Wybierz filmy do optymalizacji (batch lub jeden)
         ↓
   VSE pipeline (jak Use Case A — transkrypt → LLM → schema)
         ↓
   Podgląd zmian: tytuł, opis, rozdziały (timestamps), tagi
         ↓
   Zatwierdź → YouTube Data API: PUT videos (update metadata)
   └─ chapters → opis wideo (format YT: 00:00 Rozdział 1\n02:15 Rozdział 2)
   └─ opis → SEO-optymalizowany
   └─ tagi → z analizy LLM
```

**Wymagane OAuth scope:** `https://www.googleapis.com/auth/youtube`  
**Technicznie:** Google OAuth 2.0 przez NextAuth.js — osobny provider YT z właściwymi scopami. Token przechowywany w sesji użytkownika, refresh automatyczny.

**Status:** Część infrastruktury wdrożona. Panel do zarządzania w trakcie projektowania.

---

## Architektura systemu

```text
vse.impresjapr.pl
│
├── / (Next.js frontend — port 3000)
│   ├── Landing page (SSR, SEO)
│   ├── /login, /register
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
    ├── /v1/portals/*   ← portale WP (PLANNED)
    ├── /v1/admin/*     ← admin endpoints ✅
    └── /v1/youtube/*   ← YouTube Data API proxy (IN PROGRESS)
```

---

## ⚙️ Zasady operacyjne — Local Runner

### 🔒 ZASADA: Runner musi być standalone

**Local Runner (Windows Service) MUSI działać bez doinstalowywania jakichkolwiek zewnętrznych komponentów na maszynie użytkownika.**

- ✅ Wszystkie zależności bundlowane w paczce instalacyjnej (`runner.exe` lub folder z `requirements.txt` + venv bootstrapped)
- ✅ Instalacja = rozpakuj + uruchom install script — zero manualnych kroków
- ✅ Aktualizacje przez `git fetch + git checkout` konkretnego pliku — nie `git pull`
- ❌ Zakaz: wymagania instalacji Python osobno przez użytkownika
- ❌ Zakaz: wymagania ręcznego pip install przed startem
- ❌ Zakaz: zależność od globalnego środowiska systemowego

**Powód:** Każda dodatkowa zależność to bloker wdrożenia. Celem jest instalacja w 5 minut na dowolnym Windows 10+ bez wiedzy technicznej.

---

## ✅ Faza 1 — CLI Pipeline i Infrastruktura Core (DONE)

- [x] Core pipeline v5.4 (VideoObject + Clip + FAQ + interactionStatistic)
- [x] VTT fetching bez API key
- [x] Local Runner (Windows Service) + VTT Timestamps support
- [x] Nginx routing (`vse.impresjapr.pl`) + FastAPI service
- [x] Video sitemap generation
- [x] Claude (Anthropic) LLM provider
- [x] inject_video + YouTube description update (OAuth)
- [x] RankMath integration

## ✅ Faza 2A — VSE API Service i Admin Panel (DONE)

- [x] FastAPI app (api/ moduł)
- [x] PostgreSQL + plans seed (auto przy starcie)
- [x] Auth: register, login, JWT
- [x] POST /v1/generate — **OPERACYJNY**
- [x] POST /v1/inject, /v1/process, /v1/monitor/start
- [x] Next.js 14 dashboard (2 ścieżki: Free/Pro)
- [x] Admin Panel: 4 endpointy (users, user/{id}, plan, stats)
- [x] Deployment oracle-crimson — **LIVE**

## 🟡 Faza 2B — YouTube Unblock + E2E (IN PROGRESS)

- [x] ~~cookies.txt strategy — fetcher.py + docker volume~~ — **ZROBIONE / NIEAKTUALNE (Zastąpione przez Windows Service: Local Transcript Runner na PC użytkownika)**.
- [ ] End-to-end test z realnym video PrawyTV
- [ ] POST /v1/monitor/start — testy E2E
- [ ] deno JS runtime w api/Dockerfile (eliminuje WARNING yt-dlp)

## 🔴 Faza 3 — VSE Komercjalizacja MVP (BLOCKER)

- [x] ✅ **Moduł YouTube Update — aktualizacja opisów, hashtagów i rozdziałów bezpośrednio na YT ze spersonalizowaną stopką per kanał (wdrożone 2026-07-12)**
- [x] ✅ **PressAI YT Description pipeline — pełny opis M1-M8 generowany przez crimson-void (wdrożone 2026-07-12)**
- [ ] 🔴 Stripe checkout flow (Products + Prices + Webhooks)
- [ ] 🔴 Terms of Service + Privacy Policy (EU/RODO)
- [ ] 🟡 System kuponów promocyjnych dla Stripe (rabaty na upgrade / nowe abonamenty)
- [ ] 🟡 Email verification flow (token exists, flow TBD)
- [ ] 🟡 Google OAuth login (google_id exists, flow TBD)
- [ ] 🟡 Landing page visual polish + pricing page
- [x] ✅ Pre-deploy backup system (VPS cron + deploy gate)
- [x] ✅ `org_id` nullable column prep (future org layer)

## 🔵 Faza 4 — Dashboard UI Artykułu + Inject Flow (D2 + D3) / VSE Growth (NEXT)

- [ ] UI Artykułu: Podgląd leadu, treści, FAQ, Chapters w Next.js przed publikacją
- [ ] **Podgląd opisu YouTube przed wysyłką** — endpoint `/v1/preview-yt-description` + textarea w dashboardzie (dispatch gotowy)
- [ ] **Aktualizacja tytułu YouTube** — rozszerzenie `YouTubePublishRequest` o pole `title` + `videos.update` snippet (TODO z 2026-07-12)
- [ ] Inject Flow UI: Modal z wyborem portalu, test połączenia
- [ ] Batch processing (wiele wideo naraz)
- [ ] SEO Scoring dashboard
- [ ] Channel Monitor E2E
- [ ] API keys for Pro/Agency (model exists)

## 🔵 Faza 5 — Zarządzanie Portalami WordPress / Integracja ekosystemu (PLANNED)

- [ ] Endpointy i UI dla /settings -> Portale WordPress
- [ ] Szyfrowanie Application Passwords w DB
- [ ] Opcjonalna user federation VSE↔PressAI
- [ ] S2S user-scoped izolacja (competing tenants scenario)
- [ ] Organization/Tenant layer

## 🔵 Faza 6 — Billing (PLANNED)

- [ ] Stripe Checkout — upgrade Starter/Pro/Agency
- [ ] Stripe Tax — automatyczny VAT PL/UE
- [ ] /pricing — strona z porównaniem planów
- [ ] Billing portal (Stripe Customer Portal) + Faktury PDF

## 🔵 Faza 7 — YouTube Channel Manager / Use Case B (PLANNED)

- [ ] Połączenie konta YouTube (Google OAuth scope dla read/write)
- [ ] Przeglądarka kanału (/channels) z filtrowaniem
- [ ] Optymalizacja i batch publikacja na YouTube
- [ ] **OAuth dostęp do prywatnych i zaplanowanych filmów** — VTT pobieranie bez konieczności zmiany statusu na Unlisted *(workaround: zmień na Unlisted przed generowaniem)*
- [ ] Ręczny upload pliku VTT w dashboardzie (alternatywa dla OAuth do prywatnych)

## 🔵 Faza 8 — WordPress Plugin + Enterprise (FUTURE)

- [ ] WordPress plugin (pressai-video-seo) freemium
- [ ] Bundle pricing VSE+PressAI
- [ ] Integracja z press.impresjapr.pl (SaaS crimson-void)
- [ ] White-label (Agency) — własna domena klienta
