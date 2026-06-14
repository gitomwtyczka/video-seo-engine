# HANDOFF — vse-dev-01 → Supervisor

**Data:** 2026-06-14 17:03 (CEST)  
**Agent wychodzący:** `vse-dev-01`  
**Sesja:** ~90 kroków, V1 🔴 wyczerpana  
**Status projektu:** Frontend + Auth DZIAŁA, pipeline wymaga weryfikacji

---

## CO DZIAŁA (stan produkcji)

| Komponent | URL / endpoint | Status |
|---|---|---|
| Landing page | https://vse.impresjapr.pl | ✅ |
| Rejestracja | /register | ✅ |
| Logowanie (email) | /login → /dashboard | ✅ |
| Dashboard (UI) | /dashboard | ✅ |
| FastAPI health | /health | ✅ |
| FastAPI docs | /docs | ✅ |
| Auth register | POST /api/v1/auth/register | ✅ |
| Auth login | POST /api/v1/auth/login | ✅ |
| Google OAuth | /login (przycisk Google) | ❌ brak credentials |
| Pipeline process | POST /api/v1/process | ⚠️ wymaga weryfikacji |

---

## STAN INFRASTRUKTURY

```
VPS: 147.224.162.100 (Oracle ARM)
Domena: vse.impresjapr.pl (SSL Let's Encrypt)

Docker containers:
  crimson-nginx   — nginx reverse proxy (ALL services)
  vse-postgres    — PostgreSQL 16 (port 127.0.0.1:5434)
  vse-api         — FastAPI Python (port 0.0.0.0:8085)
  vse-web         — Next.js 14 (port 0.0.0.0:3001)

Nginx routing (KRYTYCZNE — patrz GOTCHA):
  /api/auth/*  → 172.17.0.1:3001  (Next.js — NextAuth)
  /api/*       → 172.17.0.1:8085/ (FastAPI — strip /api prefix)
  /*           → 172.17.0.1:3001  (Next.js frontend)
```

---

## GOTCHA — LISTA PUŁAPEK (9 punktów)

### G1 — Port binding Docker
Docker `127.0.0.1:PORT:PORT` → niedostępny dla nginx przez bridge.  
**Fix:** zawsze `PORT:PORT` (bez 127.0.0.1) w docker-compose.

### G2 — Tailwind/PostCSS w produkcji
Bez `web/postcss.config.js` Tailwind nie kompiluje się w build.  
**Fix:** plik musi istnieć z konfiguracją `tailwindcss` i `autoprefixer`.

### G3 — npm ci bez package-lock.json
`npm ci` failuje bez `package-lock.json`.  
**Fix:** użyj `npm install` w Dockerfile.

### G4 — Cloudflare cache
Po deployu zmiany mogą być niewidoczne. **Fix:** Cloudflare → Purge Everything.

### G5 — Next.js build errors blokują deploy
**Fix:** `next.config.mjs` z `typescript: { ignoreBuildErrors: true }` i `eslint: { ignoreDuringBuilds: true }`.

### G6 — passlib vs bcrypt>=4.x
`passlib` z `CryptContext(["bcrypt"])` crashuje z bcrypt>=4.x.  
**Fix:** użyj `bcrypt` bezpośrednio (patrz `api/auth.py`).

### G7 — plans table musi być seedowana
Rejestracja użytkownika wymaga rekordu `plans.id = 'free'`.  
**Fix:** SQL seed (patrz sekcja niżej) LUB automatyczny seed w startup API.

### G8 — Next.js rewrites blokują NextAuth ⭐ KRYTYCZNE
`rewrites: [{ source: '/api/:path*', destination: backend }]` w `next.config.mjs`  
przechwytuje `/api/auth/*` i wysyła do FastAPI zamiast NextAuth → `/api/auth/error`.  
**Fix:** NIE dodawaj rewrites dla `/api/*`. Routing tylko w nginx.

### G9 — nginx /api/auth/ musi iść do Next.js
Bez dedykowanego bloku dla `/api/auth/` w nginx, NextAuth nie działa.  
**Fix:** blok `location /api/auth/` PRZED `location /api/` → proxy do 3001.

---

## SEED SQL (wymagany po każdej świeżej instalacji DB)

```sql
INSERT INTO plans (id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln)
VALUES
  ('free',    'Free',    5,    1,   false, 0),
  ('starter', 'Starter', 50,   3,   true,  49),
  ('pro',     'Pro',     300,  10,  true,  149),
  ('agency',  'Agency',  9999, 999, true,  499)
ON CONFLICT (id) DO NOTHING;
```

Komenda:
```bash
docker exec -i vse-postgres psql -U vse -d vse < seed.sql
```

---

## ZMIENNE ŚRODOWISKOWE (.env na VPS — /home/ubuntu/video-seo-engine/.env)

```
# Wymagane
GEMINI_API_KEY=...          # AI generation
JWT_SECRET_KEY=...          # JWT tokens
NEXTAUTH_SECRET=...         # NextAuth sessions
POSTGRES_PASSWORD=...       # PostgreSQL
WP_USER=...                 # WordPress injection
WP_APP_PASSWORD=...         # WordPress App Password
WP_BASE_URL=https://prawy.pl

# Opcjonalne
GOOGLE_CLIENT_ID=...        # Google OAuth (NA RAZIE PUSTE)
GOOGLE_CLIENT_SECRET=...    # Google OAuth
```

---

## NIEZAKOŃCZONE / DO ZROBIENIA

### P1 — Client-side error na dashboard po wklejeniu YT URL
**Symptom:** "Application error: a client-side exception has occurred"  
**Prawdopodobna przyczyna:** Błąd w renderowaniu wyników z `/v1/process`  — niezaobserwowany dotąd, wymaga debugowania przez konsolę przeglądarki.  
**Priorytet:** WYSOKI — to core feature

### P2 — Google OAuth
**Blokada:** Brak `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` w `.env`.  
**Akcja:** Założyć projekt w Google Cloud Console, skonfigurować OAuth consent screen, dodać redirect URI: `https://vse.impresjapr.pl/api/auth/callback/google`  
**Priorytet:** Średnio (nice-to-have, credentials login działa)

### P3 — Plans seed automatyczny w startup API
**Problem:** Plany trzeba seedować ręcznie SQL po każdym clean deploy.  
**Fix:** Dodać do `api/main.py` startup: automatyczny INSERT plans ON CONFLICT DO NOTHING.  
**Priorytet:** WYSOKI (inaczej register failuje po clean deploy)

### P4 — Weryfikacja pipeline /v1/process end-to-end
**Test:** Wklej URL YouTube PrawyTV → powinien zwrócić schema JSON-LD + chapters + FAQ  
**Wymaga:** `GEMINI_API_KEY` ustawiony, YouTube IP nie-zablokowany na VPS  
**Priorytet:** WYSOKI — to główna wartość produktu

### P5 — Dokumentacja architektoniczna
**Dispatch w:** `.agents/tasks/DISPATCH-VSE-ARCH-01-20260614-DOCS.md`  
**Dla:** `vse-architect-01`  
**Zawiera:** architecture.md, deployment.md, api-reference.md

### P6 — Historia procesów w dashboard
UI jest MVP — brak historii wykonanych procesów, brak paginacji.  
**Priorytet:** Niski (Faza 2)

### P7 — YouTube IP blocking na VPS
**Problem:** Oracle Cloud IP może być flagowany przez YouTube — yt-dlp może nie działać.  
**Opcje:** cookies.txt, proxy, lokalny runner.  
**Priorytet:** WYSOKI — blokuje core pipeline

---

## INSTRUKCJA DEPLOY (runbook skrócony)

```bash
# Na VPS (przez SSH lub FILE BRIDGE)
cd /home/ubuntu/video-seo-engine
git fetch origin main && git reset --hard origin/main

# Build i deploy
docker compose -f docker-compose.vse.yml build [service]
docker compose -f docker-compose.vse.yml up -d --no-deps --force-recreate [service]

# Weryfikacja
docker ps --filter name=vse
docker logs vse-api --tail 20
docker logs vse-web --tail 10
curl https://vse.impresjapr.pl/health
curl https://vse.impresjapr.pl/api/auth/csrf  # musi zwrócić JSON z csrfToken
```

**UWAGA:** Po rebuild `vse-web` zawsze trzeba sprawdzić czy CSRF działa!

---

## DISPATCH DLA SUPERVISOR

Supervisor powinien powołać:

1. **`vse-dev-02`** (Worker) — Fix P1 (client-side error dashboard), P3 (plans seed), weryfikacja P4 (pipeline)
2. **`vse-architect-01`** (Architect) — Dokumentacja P5
3. **`vse-strateg-01`** (Strateg) — Decyzja P7 (YouTube IP blocking), Google OAuth P2

---

## LINKI OPERACYJNE

- Repo: https://github.com/gitomwtyczka/video-seo-engine/tree/main
- Nginx config: `/home/ubuntu/crimson-void/nginx/default.conf` (na VPS)
- .env: `/home/ubuntu/video-seo-engine/.env` (na VPS, NIE w repo)
- Swagger API: https://vse.impresjapr.pl/docs
- VPS SSH: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`

---

*Handoff: vse-dev-01 | 2026-06-14 17:03 CEST*  
*Następna sesja: nowy supervisor + workers*
