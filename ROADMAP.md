# VSE — Video SEO Engine | Roadmap Produktowy

> Ostatnia aktualizacja: 2026-06-15 | sup-analyst-01  
> Status: 🟢 Faza 1 w toku

---

## Architektura Produktu

```
vse.impresjapr.pl
│
├── / (Next.js frontend — port 3001)
│   ├── Landing page (SSR, SEO)
│   ├── /login, /register
│   ├── /dashboard — pipeline UI
│   ├── /settings — portale WP, API keys
│   ├── /admin — panel administracyjny
│   └── /pricing
│
└── /api/* (FastAPI backend — port 8085)
    ├── /v1/process  ← core pipeline (LIVE)
    ├── /v1/generate ← generowanie schematu
    ├── /v1/inject   ← wstrzykiwanie do WP
    ├── /v1/auth/*   ← JWT auth
    ├── /v1/users/*  ← konta, plany, quotas
    ├── /v1/portals/* ← zarządzanie portalami WP
    └── /v1/admin/*  ← admin endpoints
```

**Stack:**
- Frontend: Next.js (SSR, NextAuth.js)
- Backend: FastAPI (Python 3.11)
- Auth: NextAuth.js — email+password + Google OAuth
- Billing: Stripe + Stripe Tax (VAT EU auto)
- DB: PostgreSQL
- Hosting: oracle-crimson (Oracle ARM 4CPU/24GB)

---

## Plany i Ceny

| Plan | Cena | Procesy/mies. | Portale WP | API |
|---|---|---|---|---|
| **Free** | 0 PLN | 5 | 0 — brak inject | ❌ |
| **Starter** | 29 PLN/mies. | 50 | 1 | ❌ |
| **Pro** | 99 PLN/mies. | 300 | 5 | ✅ |
| **Agency** | 299 PLN/mies. | ∞ | 999 (white-label) | ✅ |

> Limity portali kontrolowane przez pole `wp_sites_limit` w tabeli `plans` (DB seed: 1/3/10/999).

---

## Faza 0 — Infrastruktura API ✅ DONE

**Commit:** `2c0c31eb` | Data: 2026-06-14

- [x] Core pipeline: YouTube → transkrypt → Gemini → JSON-LD schema
- [x] FastAPI API server (`api/`) na porcie 8085
- [x] Docker container (`vse-api`) na oracle-crimson
- [x] Nginx reverse proxy → `vse.impresjapr.pl`
- [x] SSL Let's Encrypt (certbot-dns-cloudflare, auto-renewal)
- [x] Endpoint `/v1/process` i `/health` działające
- [x] Benchmark SEO: prawy.pl 8/10 vs konkurencja 2-3/10

---

## Faza 1 — Auth + Konta + Dashboard MVP 🟡 W TOKU

**Target:** 2026-06-28 (2 tygodnie)

### Backend (FastAPI)
- [x] PostgreSQL schema: `users`, `plans`, `usage_logs`, `api_keys`
- [x] `/v1/auth/register` — rejestracja email+password
- [x] `/v1/auth/login` — JWT access + refresh token
- [ ] `/v1/auth/google` — Google OAuth flow
- [ ] Quota middleware — sprawdza limit przed pipeline
- [x] `/v1/users/me` — profil, plan, usage
- [ ] Rate limiting per plan
- [ ] **BLOKER: `api/core/fetcher.py` + `api/core/generator.py`** — brak plików, pipeline pada na ImportError

### Frontend (Next.js)
- [x] Landing page
- [x] `/login` — email+password + Google OAuth button
- [x] `/register`
- [x] `/dashboard` — formularz pipeline + wynik
- [ ] Historia wygenerowanych schematów

### DevOps
- [x] Dockerfile dla Next.js frontend
- [x] docker-compose dla VSE
- [x] Deploy na oracle-crimson (port 3001)
- [x] Nginx routing

---

## Faza 2 — Zarządzanie Portalami WP + Admin + UX 🔵 NEXT

**Target:** 2026-07-12

### 🔑 Zarządzanie portalami WordPress [FEATURE PRIORYTETOWY]

Użytkownik musi móc skonfigurować swoje portale WordPress (URL + credentials) żeby
VSE mogło wstrzykiwać schematy. Bez tego `/v1/inject` wymaga podawania credentiali w każdym requescie — model nie do przyjęcia w SaaS.

**Logika subskrypcji:**
- `Free` — brak możliwości dodania portalu (inject niedostępny)
- `Starter` — max **1** portal (pole `wp_sites_limit = 1` w DB)
- `Pro` — max **5** portali (`wp_sites_limit = 10` per DB, realny limit 5 w UI)
- `Agency` — bez limitu (`wp_sites_limit = 999`)

**Co zaimplementować:**

```
BEKENDOWO:
  Tabela DB: user_portals
    id, user_id, wp_base_url, wp_user,
    wp_app_password_encrypted,  ← szyfrowane AES-256
    display_name, is_active, created_at

  Endpointy:
    GET  /v1/portals        ← lista portali usera
    POST /v1/portals        ← dodaj portal (walidacja limitu)
    DELETE /v1/portals/{id} ← usuń portal
    POST /v1/portals/{id}/test ← test połączenia WP

  Walidacja:
    - Przed dodaniem: COUNT portali <= wp_sites_limit planu
    - Jeśli limit osiągnięty: HTTP 402 z info o upgrade
    - Test połączenia: GET /wp-json/wp/v2/users/me z credentialami

FRONTENDOWO:
  /settings → zakładka "Portale WordPress"
    Lista portali (nazwa, URL, status, akcje)
    Formularz: URL portalu + WP username + Application Password
    Info o limicie (np. "1/1 portali — Starter")
    Przycisk 'Test połączenia' przed zapisem
    CTA upgrade gdy limit osiągnięty

  /dashboard:
    Dropdown 'Wybierz portal' zamiast ręcznego wpisywania
    Site_config pobierany z /v1/portals/{id} po stronie API
```

**Security:**
- `wp_app_password` szyfrowane w DB (AES-256 lub Fernet), NIE w plaintext
- Klucz szyfrowania w env var `PORTAL_ENCRYPTION_KEY`
- WP Application Password — nie hasło główne! Użytkownik tworzy w WP Admin → Users → Application Passwords
- Instrukcja w UI jak wygenerować Application Password w WP

### Admin Panel
- [ ] `/admin` — lista użytkowników, plany, usage stats
- [ ] Ręczna zmiana planu przez admina
- [ ] Quota override per user
- [ ] Logi błędów pipeline per user

### UX
- [ ] Zarządzanie kluczami API (plan Pro)
- [ ] Email powiadomienia (Resend): welcome, limit warning, upgrade
- [ ] `/dashboard` — eksport schematów (JSON, clipboard)
- [ ] Podgląd rozdziałów i FAQ generowanych przez AI

---

## Faza 3 — Billing + Monetyzacja 🔵 PLANNED

**Target:** 2026-07-26

- [ ] Stripe Checkout — upgrade do Starter/Pro/Agency
- [ ] Stripe Tax — automatyczny VAT PL/UE
- [ ] Webhooks Stripe: `payment_succeeded`, `subscription_cancelled`
- [ ] `/pricing` — porównanie planów z Stripe Checkout
- [ ] Billing portal (Stripe Customer Portal)
- [ ] Faktury PDF (Stripe)
- [ ] Trial 14 dni dla Pro (bez karty)

---

## Faza 4 — WordPress Plugin + SaaS Integration 🔵 PLANNED

**Target:** 2026-08-16

- [ ] Plugin WordPress `pressai-video-seo` (PHP)
- [ ] Wtyczka łączy się z VSE API przez klucz API (plan Pro+)
- [ ] One-click inject schema z panelu WP
- [ ] Integracja z press.impresjapr.pl (SaaS module)
- [ ] Batch processing: skanuj cały portal WP, znajdź filmy, processuj

---

## Faza 5 — Skalowalność + B2B 🔵 FUTURE

- [ ] White-label (plan Agency) — własna domena klienta
- [ ] Multi-tenant WordPress (N portali per konto) — baza pod Fazę 2
- [ ] GSC integration (Search Console API)
- [ ] Monitoring: alerty o nowych filmach na kanale YouTube
- [ ] Reseller program

---

## Linki

- **API Live:** https://vse.impresjapr.pl/health
- **Repo:** https://github.com/gitomwtyczka/video-seo-engine
- **VPS:** oracle-crimson (147.224.162.100)
- **Supervisor inbox:** sonic-void/.agents/reports/inbox/
