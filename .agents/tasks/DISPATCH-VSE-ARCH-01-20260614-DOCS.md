# DISPATCH: Dokumentacja Architektoniczna VSE

**Dla:** `vse-architect-01`  
**Od:** `vse-dev-01` via Supervisor  
**Data:** 2026-06-14  
**Priorytet:** WYSOKI  

---

## ⛔ ZAKRES NARZĘDZI TEJ SESJI

Ta sesja: TYLKO GitHub MCP + publiczne endpointy.  
**Nie używaj:** file bridge, stellar-relay, Wetty, SSH, bash na VPS.  
Weryfikacja: `curl https://vse.impresjapr.pl/...` lub Swagger `/docs`.  
Deploy: zgłoś Supervisorowi po sesji.

---

## Cel

Utworzyć i utrzymywać żyjącą dokumentację architektoniczną projektu VSE w GitHub.
Dokumentacja ma być źródłem prawdy dla wszystkich agentów i developerów.

## Co działa (stan po sesji 2026-06-14)

### Stack produkcyjny na VPS (147.224.162.100)

```
nginx (crimson-nginx) ──┬── vse.impresjapr.pl:443
                      ├── /api/* → 172.17.0.1:8085 (vse-api FastAPI)
                      └── /*    → 172.17.0.1:3001 (vse-web Next.js)

docker-compose.vse.yml:
  - vse-postgres   : PostgreSQL 16 (port 5434 localhost)
  - vse-api        : FastAPI (port 8085, 0.0.0.0)
  - vse-web        : Next.js 14 (port 3001, 0.0.0.0)
  - sieć: vse-net (bridge)
```

### Schemat bazy danych (PostgreSQL)

Tabele:
- `plans` (id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln)
- `users` (id UUID, email, hashed_password, plan_id FK, is_active, is_admin, ...)
- `jobs` / `sites` (TODO: sprawdzić aktualny schemat w models/)

Seed plans:
- `free` / `starter` / `pro` / `agency`

### FastAPI routes (/api/* → strip /api → /v1/*)

```
GET  /health
POST /v1/auth/register
POST /v1/auth/login
POST /v1/process         # główny pipeline YouTube→SEO
POST /v1/generate        # AI generation only
POST /v1/inject          # WordPress injection
POST /v1/monitor/start   # YouTube Monitor
GET  /v1/sitemap
GET  /docs               # Swagger UI
```

### Next.js frontend (web/)

```
src/app/
  page.tsx              # Landing page
  layout.tsx
  globals.css
  providers.tsx         # SessionProvider
  login/page.tsx        # Login form (email+password)
  register/page.tsx     # Register form
  dashboard/page.tsx    # Dashboard (URL input → process → wyniki)
  api/auth/[...nextauth]/route.ts  # NextAuth v4
src/middleware.ts       # withAuth → chroni /dashboard/*
```

### Pliki konfiguracyjne kluczowe

- `docker-compose.vse.yml` — stack VSE
- `web/Dockerfile.web` — multi-stage Next.js
- `web/next.config.mjs` — standalone, ignoreBuildErrors
- `web/postcss.config.js` — Tailwind CSS
- `web/tailwind.config.ts` — Tailwind config
- `Dockerfile.api` — FastAPI
- `api/main.py` — FastAPI app entry
- `api/auth.py` — bcrypt (NIE passlib!), JWT
- `api/db.py` — SQLAlchemy async
- `api/models/user.py` — User model
- `api/models/request.py` / `response.py`
- `api/routers/auth.py` / `users.py` / `process.py` itd.

### Zmienne środowiskowe (.env na VPS — NIE w repo)

```
GEMINI_API_KEY
JWT_SECRET_KEY
NEXTAUTH_SECRET
POSTGRES_PASSWORD
WP_USER / WP_APP_PASSWORD / WP_BASE_URL
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  # opcjonalne
```

---

## Zadania do wykonania

### 1. Utwórz `docs/architecture.md` w repo

Zawierać ma:
- Diagram ASCII stacków (nginx, docker, sieci)
- Mapę modułów FastAPI
- Schemat auth flow (register → login → JWT → dashboard)
- Schemat pipeline (URL → fetch → AI → inject)
- Tabele bazy danych
- Deployment checklist (gotcha z AGENTS.md)

### 2. Utwórz `docs/api-reference.md`

Zawierać ma:
- Wszystkie endpointy z przykładami request/response
- Auth flow (Bearer token)
- Error codes

### 3. Utwórz `docs/deployment.md`

Zawierać ma:
- Pełny deployment runbook (krok po kroku)
- Lista gotcha z AGENTS.md (8 punktów)
- Seed plans SQL
- Nginx routing config
- VPS firewall / OCI security list

### 4. README.md — zaktualizuj

Dodać sekcję:
- Quick start (local dev)
- Production deployment
- Link do docs/

---

## Standard dokumentacji

- Język: **polski** (projekt polskijęzyczny)
- Format: Markdown z diagramami ASCII
- Lokalizacja: `docs/` w repo `video-seo-engine`
- Aktualizacja: przy każdej zmianie architektury (jako część commitu)
- GitHub = jedyne źródło prawdy (nie lokalne pliki)

---

## Priorytety

1. `docs/architecture.md` — PILNE (agenci następnej sesji tego potrzebują)
2. `docs/deployment.md` — PILNE (runbook)
3. `docs/api-reference.md` — śRednio pilne
4. README.md update — przy okazji

---

*Dispatch: vse-dev-01 | 2026-06-14*  
*Zaktualizowano: 2026-06-15 [sup-worker-01] — dodano sekcję blokady VPS access*
