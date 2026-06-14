# VSE — Video SEO Engine | Roadmap Produktowy

> Ostatnia aktualizacja: 2026-06-14 | vse-dev-01  
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
│   ├── /admin — panel administracyjny
│   └── /pricing
│
└── /api/* (FastAPI backend — port 8085)
    ├── /v1/process  ← core pipeline (LIVE)
    ├── /v1/auth/*   ← JWT auth
    ├── /v1/users/*  ← konta, plany, quotas
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

| Plan | Cena | Limity |
|---|---|---|
| **Free** | 0 PLN | 5 processów/mies., brak WP inject |
| **Starter** | 29 PLN/mies. | 50 processów/mies., 1 WP site |
| **Pro** | 99 PLN/mies. | ∞ processów, 5 WP sites, API access |
| **Agency** | 299 PLN/mies. | White-label, ∞ wszystko, SLA |

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
- [ ] PostgreSQL schema: `users`, `plans`, `usage_logs`, `api_keys`
- [ ] `/v1/auth/register` — rejestracja email+password
- [ ] `/v1/auth/login` — JWT access + refresh token
- [ ] `/v1/auth/google` — Google OAuth flow
- [ ] Quota middleware — sprawdza limit przed pipeline
- [ ] `/v1/users/me` — profil, plan, usage
- [ ] Rate limiting per plan (Free: 5/mies., Starter: 50, Pro: ∞)

### Frontend (Next.js)
- [ ] Inicjalizacja projektu `web/` w repo
- [ ] Landing page (hero, features, pricing, CTA)
- [ ] `/login` — email+password + Google OAuth button
- [ ] `/register` — formularz + email verification
- [ ] `/dashboard` — formularz pipeline + wynik JSON-LD
- [ ] Usage meter (ile z limitu zużyte)
- [ ] Historia wygenerowanych schematów

### DevOps
- [ ] Dockerfile dla Next.js frontend
- [ ] docker-compose dla VSE (frontend + backend)
- [ ] Deploy na oracle-crimson (port 3001)
- [ ] Nginx update: `/api/*` → 8085, `/*` → 3001

---

## Faza 2 — Admin Panel + Historia + UX 🔵 NEXT

**Target:** 2026-07-12

- [ ] `/admin` — lista użytkowników, plany, usage stats
- [ ] Ręczna zmiana planu przez admina
- [ ] Quota override per user
- [ ] Logi błędów pipeline per user
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
- [ ] Multi-tenant WordPress (N portali per konto)
- [ ] GSC integration (Search Console API)
- [ ] Monitoring: alerty o nowych filmach na kanale YouTube
- [ ] Reseller program

---

## Linki

- **API Live:** https://vse.impresjapr.pl/health
- **Repo:** https://github.com/gitomwtyczka/video-seo-engine
- **VPS:** oracle-crimson (147.224.162.100)
- **Supervisor inbox:** sonic-void/.agents/reports/inbox/
