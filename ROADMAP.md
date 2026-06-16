# VSE — Video SEO Engine | Roadmap Produktowy

> Ostatnia aktualizacja: 2026-06-16 | Supervisor 03  
> Status: 🟢 Faza 3 KOMPLETNA → Faza 4 w planowaniu

---

## Dwa tryby pracy — Use Cases produktu

### 🎬 Use Case A — Paste URL (obecny flow, działa)

> Użytkownik wkleja link do dowolnego wideo YouTube → system pobiera transkrypt → generuje SEO schema → użytkownik publikuje na wybranym portalu WP.

```
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

```
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

**Status:** Niezaimplementowany. Zaplanowany jako Faza 5.

---

## Architektura systemu

```
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
    ├── /v1/portals/*   ← portale WP (PLANNED Faza 4)
    ├── /v1/admin/*     ← admin endpoints ✅
    └── /v1/youtube/*   ← YouTube Data API proxy (PLANNED Faza 5)
```

**Stack:**
- Frontend: Next.js (NextAuth.js)
- Backend: FastAPI (Python 3.11)
- Auth: NextAuth.js — Google OAuth (logowanie do VSE) + Google OAuth (YouTube channel scope)
- DB: PostgreSQL
- Local Runner: Windows Service (Task Scheduler) — poller transkryptów
- Hosting: oracle-crimson (Oracle ARM 4CPU/24GB)

---

## ⚙️ Zasady operacyjne — Local Runner

> Wprowadzone: 2026-06-16 | Supervisor 03

### 🔒 ZASADA: Runner musi być standalone

**Local Runner (Windows Service) MUSI działać bez doinstalowywania jakichkolwiek zewnętrznych komponentów na maszynie użytkownika.**

- ✅ Wszystkie zależności bundlowane w paczce instalacyjnej (`runner.exe` lub folder z `requirements.txt` + venv bootstrapped)
- ✅ Instalacja = rozpakuj + uruchom install script — zero manualnych kroków
- ✅ Aktualizacje przez `git fetch + git checkout` konkretnego pliku — nie `git pull` (risk: untracked conflicts)
- ❌ Zakaz: wymagania instalacji Python osobno przez użytkownika
- ❌ Zakaz: wymagania ręcznego pip install przed startem
- ❌ Zakaz: zależność od globalnego środowiska systemowego

**Powód:** Każda dodatkowa zależność to bloker wdrożenia. Celem jest instalacja w 5 minut na dowolnym Windows 10+ bez wiedzy technicznej.

**Target architecture (Faza 4+):** Self-contained `.exe` (PyInstaller) lub skrypt z embedded venv bootstrapem.

---

## Plany i Ceny

| Plan | Cena | Procesy/mies. | Portale WP | YouTube Channel | API |
|---|---|---|---|---|---|
| **Free** | 0 PLN | 5 | 0 | ❌ | ❌ |
| **Starter** | 29 PLN/mies. | 50 | 1 | ❌ | ❌ |
| **Pro** | 99 PLN/mies. | 300 | 5 | ✅ 1 kanał | ✅ |
| **Agency** | 299 PLN/mies. | ∞ | 999 | ✅ bez limitu | ✅ |

---

## ✅ Faza 1 — Infrastruktura Core DONE

| Commit | Co | Kiedy |
|--------|----|-------|
| `2c0c31e` | FastAPI + pipeline | 2026-06-14 |
| `7eb5288`–`54fb5d9` | Local Runner (Windows Service) | 2026-06-16 |
| `9fb1f85` | nginx fix /v1/ → FastAPI | 2026-06-16 |
| `2cb7889` | URL routing fix dashboard | 2026-06-16 |

**Działające:**
- ✅ Pipeline: YouTube URL → transkrypt → LLM → JSON-LD schema
- ✅ Local Runner jako Windows Service (Task Scheduler)
- ✅ Nginx routing (`vse.impresjapr.pl`)
- ✅ Google OAuth — logowanie do VSE
- ✅ Konto `tobroz@gmail.com` plan Agency

---

## ✅ Faza 2 — VTT Timestamps DONE (DEV-06, 16.06.2026)

**Commity:** `827e5b0`, `81ac779`, `6612d36`

**Co zostało naprawione:** Runner wysyłał plain text bez timestampów → rozdziały miały `time=0`. Teraz:
- `runner.py` → format `__VTT__\n[MM:SS] tekst`
- `jobs.py` → VTT-aware sanitize (zachowuje newlines)
- `pipeline.py` → konwersja `__VTT__` → WebVTT dla generatora

**⚠️ Wymagane działanie użytkownika** (jednorazowe):
```bat
# Na Windows PC — zaktualizuj Local Runner:
git pull origin main
nssm restart VSELocalRunner
```
Po tym rozdziały na `vse.impresjapr.pl` będą mieć czasy (02:15, 07:43).

---

## ✅ Faza 3 — Admin Panel DONE (DEV-07, 16.06.2026)

**Commity:** `e13651e`, `f73e8a9`, `bd36dee`, `b151371`

**Co zostało wdrożone:**
- `/admin` panel — lista użytkowników + zmiana planu
- `api/routers/admin.py` — 4 endpointy (users, user/{id}, plan, stats)
- Middleware `/admin` → redirect do /login bez sesji
- Ochrona API: 401 bez tokenu

**⚠️ Wymagane działanie jednorazowe** (SQL na VPS):
```sql
-- Aktywacja konta admin:
UPDATE users SET is_admin = true WHERE email = 'tobroz@gmail.com';
```
Bez tego panel wyświetli 403 nawet z planem Agency.

---

## 🟡 Faza 4 — Dashboard UI Artykułu + Inject Flow (D2 + D3) — NEXT

**Zależy od:** Faza 2 (VTT) ✅ GOTOWE — można startować  
**Cel:** Użytkownik widzi pełen artykuł (nie suchy JSON) i może go wstrzyknąć do WP jednym kliknięciem.

### D2 — Dashboard UI: Zakładka Artykuł

Aktualnie dashboard pokazuje JSON-LD schema. Cel: zakładki z treścią.

```
/dashboard — po generowaniu:
├── Zakładka: Schemat (obecny JSON-LD) ← ZOSTAJE
├── Zakładka: Artykuł [NOWE]
│   ├── Lead / wstęp (pole pipeline: lead)
│   ├── Treść artykułu (pole: article_body)
│   ├── Cytaty (pole: quotes[])
│   └── FAQ (pole: faq[])
├── Zakładka: Rozdziały [NOWE]
│   └── Lista: [02:15] Tytuł rozdziału — z rzeczywistymi czasami
└── Akcje:
    ├── [Kopiuj JSON-LD]
    ├── [Kopiuj artykuł]
    └── [Wstrzyknij do portalu] → D3
```

**Scope:** `web/src/app/dashboard/page.tsx` — rozszerzenie o zakładki i renderowanie pól z API response

### D3 — Inject Flow: Generate → Podgląd → Inject

Aktualnie inject wymaga ręcznego POST. Cel: pełen flow w UI.

```
Użytkownik klika [Wstrzyknij do portalu]
    ↓
Modal: Wybierz portal WP
(dropdown z listy /v1/portals lub ręczne wpisanie URL+credentials — MVP)
    ↓
Podgląd co zostanie wysłane:
  - Tytuł artykułu
  - Lead
  - Schema JSON-LD
  - Rozdziały w opisie WP
    ↓
[Potwierdź] → POST /v1/inject
    ↓
Potwierdzenie: link do posta WP
```

**Scope:** `web/src/app/dashboard/` + `api/routers/inject.py` (weryfikacja)  
**Priorytet:** P1. Dispatch D2+D3 gotowy do wysłania.

---

## 🔵 Faza 5 — Zarządzanie Portalami WordPress — PLANNED

**Cel:** Użytkownik zapisuje portale WP w ustawieniach zamiast wpisywać credentials przy każdym injeccie.

```
DB: tabela user_portals
  id, user_id, wp_base_url, wp_user,
  wp_app_password_encrypted (AES-256),
  display_name, is_active, created_at

Endpointy:
  GET  /v1/portals          ← lista portali usera
  POST /v1/portals          ← dodaj portal (limit per plan)
  DELETE /v1/portals/{id}   ← usuń portal
  POST /v1/portals/{id}/test ← test połączenia WP

/settings → zakładka "Portale WordPress"
  - Lista z nazwą, URL, statusem
  - Formularz: URL + WP username + Application Password
  - Info o limicie: "1/1 portali — Starter | Upgrade dla więcej"
  - Test połączenia przed zapisem
```

**Limity per plan:** Free=0, Starter=1, Pro=5, Agency=999  
**Security:** Application Password (nie główne hasło WP), szyfrowane w DB

---

## 🔵 Faza 6 — Billing + Monetyzacja — PLANNED

**Cel:** Samodzielny upgrade planu przez użytkownika, płatności online.

- Stripe Checkout — upgrade Starter/Pro/Agency
- Stripe Tax — automatyczny VAT PL/UE
- Webhooks Stripe: `payment_succeeded`, `subscription_cancelled`
- `/pricing` — strona z porównaniem planów
- Billing portal (Stripe Customer Portal)
- Faktury PDF
- Trial 14 dni Pro bez karty

---

## 🔵 Faza 7 — YouTube Channel Manager (Use Case B) — PLANNED

**Cel:** Użytkownik z planem Pro+ łączy swoje konto YouTube i masowo optymalizuje filmy na swoim kanale — bez wychodzenia z VSE.

### 7.1 — Połączenie konta YouTube (OAuth)

```
/settings → zakładka "Konta YouTube"

Flow:
  1. Kliknij [Połącz konto YouTube]
  2. Google OAuth 2.0 — scope: youtube.readonly + youtube
     (NextAuth.js drugi provider z youtube-specific scope)
  3. Token zapisany w DB: user_oauth_tokens
     {user_id, provider: 'youtube', access_token (encrypted),
      refresh_token (encrypted), expires_at, channel_id, channel_name}
  4. Zakładka pokazuje połączony kanał (avatar, nazwa, liczba filmów)
  5. Przycisk [Rozłącz] — revokes token + usuwa z DB
```

**Uwaga techniczna:** Google OAuth dla logowania do VSE to osobny flow niż OAuth dla YouTube Data API. Logowanie do VSE = Google Sign-In (openid, email, profile). YouTube Channel Manager = youtube scope (read+write). Oba mogą być w jednym koncie Google ale wymagają osobnych tokenów z różnymi zakresami.

### 7.2 — Przeglądarka kanału

```
/channels
├── Wybierz kanał (jeśli kilka połączonych)
├── Lista filmów (paginated)
│   ├── Miniatura, tytuł, data publikacji
│   ├── Liczba wyświetleń, polubień
│   ├── Status SEO: ✅ / ⚠️ / ❌ (czy ma rozdziały, opis > 300 znaków)
│   └── [Optymalizuj] → pipeline VSE
├── Filtr: bez rozdziałów / najstarsze / największy ruch
└── Batch: [Zaznacz wszystkie] → [Optymalizuj zaznaczone]
```

### 7.3 — Optymalizacja i publikacja na YouTube

```
Po generowaniu schema:

[Wstrzyknij do YouTube]
    ↓
Podgląd zmian:
  - Nowy tytuł (SEO-optymalizowany)
  - Nowy opis (z rozdziałami w formacie YT:
      00:00 Wstęp
      02:15 Główny temat
      07:43 Podsumowanie)
  - Tagi (z analizy LLM)
    ↓
[Zatwierdź] → YouTube Data API v3:
  videos.update() — title, description, tags
    ↓
Potwierdzenie: link do wideo na YouTube
```

**API:** YouTube Data API v3 — `videos.update`, `playlistItems.list`  
**Scope OAuth:** `https://www.googleapis.com/auth/youtube`  
**Koszty API:** YouTube Data API — 10 000 units/dzień free tier. `videos.update` = 50 units, `videos.list` = 1 unit.

### 7.4 — Monitoring kanału (opcjonalnie, Faza 8)

- Alerty o nowych filmach na kanale (YouTube push notifications / polling)
- Auto-generowanie schema dla nowych filmów
- Dashboard: ranking filmów po SEO score

---

## 🔵 Faza 8 — WordPress Plugin + Enterprise — FUTURE

- Plugin WordPress `pressai-video-seo` (PHP) — one-click inject z panelu WP
- Integracja z press.impresjapr.pl (SaaS crimson-void)
- Batch processing: skanuj cały portal WP, znajdź filmy, processuj
- White-label (Agency) — własna domena klienta
- GSC integration (Search Console API)
- Reseller program

---

## Mapa zależności

```
Faza 1 (Core) ✅
    ↓
Faza 2 (VTT) ✅ → Faza 4 (Dashboard UI) 🟡 NEXT
    ↓                          ↓
Faza 3 (Admin) ✅         Faza 5 (Portale WP)
                               ↓
                          Faza 6 (Billing)
                               ↓
                          Faza 7 (YouTube Channel Manager)
                               ↓
                          Faza 8 (Plugin WP + Enterprise)
```

---

## Stan produkcji (16.06.2026)

| Komponent | Status | URL |
|-----------|--------|-----|
| Landing page | ✅ Live | vse.impresjapr.pl |
| Dashboard (pipeline) | ✅ Live | /dashboard |
| Admin panel | ✅ Live | /admin (wymaga SQL — patrz Faza 3) |
| Google OAuth (logowanie) | ✅ Live | /login |
| Local Runner (Windows) | ✅ Działa | nssm + Task Scheduler |
| VTT timestamps | ✅ (wymaga git pull+restart Runnera) | — |
| Portale WP (UI) | ❌ Nie ma | Faza 5 |
| YouTube Channel Manager | ❌ Nie ma | Faza 7 |

---

## Linki

- **App:** https://vse.impresjapr.pl
- **API Health:** https://vse.impresjapr.pl/health
- **Repo:** https://github.com/gitomwtyczka/video-seo-engine
- **VPS:** oracle-crimson (`ubuntu@147.224.162.100`)
- **Supervisor inbox:** sonic-void/.agents/reports/inbox/
