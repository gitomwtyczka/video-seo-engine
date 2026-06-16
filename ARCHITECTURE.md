# ARCHITECTURE.md — Video SEO Engine

> **KROK 0 dla każdego workera.** Przeczytaj ten dokument przed pierwszym commitem.
> Autor: `vse-architect-01` | Aktualizacja: 2026-06-16

---

## 1. Stack i Wersje

### Backend (FastAPI)
| Pakiet | Wersja |
|--------|--------|
| Python | 3.10+ |
| FastAPI | ≥0.111.0 |
| Uvicorn | ≥0.30.0 (standard) |
| SQLAlchemy | ≥2.0.0 (async) |
| asyncpg | ≥0.29.0 |
| Pydantic | ≥2.0.0 |
| python-jose | ≥3.3.0 (JWT) |
| passlib[bcrypt] | ≥1.7.4 |
| anthropic | ≥0.28.0 |
| youtube-transcript-api | ≥1.2.4 |
| yt-dlp | ≥2024.1.0 |
| PostgreSQL | 16 (Docker image: postgres:16-alpine) |

### Frontend (Next.js)
| Pakiet | Wersja |
|--------|--------|
| Next.js | 14.2.29 |
| React | 18.3.x |
| next-auth | 4.24.7 |
| Tailwind CSS | 3.4.x (devDep) |
| TypeScript | 5.4.x |
| axios | 1.7.x |
| framer-motion | 11.x |

### Infrastruktura
| Komponent | Wartość |
|-----------|--------|
| VPS | Oracle ARM — 147.224.162.100 |
| User SSH | ubuntu@147.224.162.100 |
| Klucz SSH | ~/.ssh/oracle-crimson.key |
| Nginx | Crimson-void (osobny serwis, `/home/ubuntu/crimson-void/nginx/default.conf`) |
| Cloudflare | Reverse proxy przed VPS |
| Domain | vse.impresjapr.pl |

---

## 2. Struktura Folderów

```
video-seo-engine/
├── .agents/                    # Pliki operacyjne agentów (heartbeat, raporty, taski)
│   ├── heartbeat.json          # Status aktywnej sesji agenta
│   ├── tasks/                  # Dispatche robocze
│   └── reports/                # Raporty sesji
├── .env.example                # Template zmiennych środowiskowych (API + DB)
├── .env.api.example            # Alternatywny template (tylko API)
├── .env.production.example     # Template produkcyjny
│
├── api/                        # FastAPI backend — serwis REST
│   ├── __init__.py
│   ├── main.py                 # Entrypoint, montowanie routerów, startup
│   ├── auth.py                 # JWT helper: get_current_user, decode_token
│   ├── db.py                   # SQLAlchemy async engine, get_db, Base
│   ├── migrate.py              # Narzędzie migracji (Base.metadata.create_all)
│   ├── quota.py                # Sprawdzenie i zapis quoty użytkownika
│   ├── core/                   # API-internal helpers
│   ├── models/
│   │   ├── user.py             # ORM: User, Plan, UsageLog, ApiKey
│   │   ├── job.py              # ORM: TranscriptJob
│   │   ├── request.py          # Pydantic: modele wejścia (GenerateRequest, InjectRequest...)
│   │   └── response.py         # Pydantic: modele odpowiedzi (GenerateResponse, InjectResponse...)
│   ├── routers/
│   │   ├── auth.py             # POST /v1/auth/* (register, login, refresh, Google OAuth)
│   │   ├── users.py            # GET /v1/users/me
│   │   ├── generate.py         # POST /v1/generate
│   │   ├── inject.py           # POST /v1/inject
│   │   ├── process.py          # POST /v1/process (full pipeline)
│   │   ├── jobs.py             # POST/GET /v1/jobs/* (Local Runner queue)
│   │   ├── admin.py            # GET/PATCH /v1/admin/* (wymaga is_admin=True)
│   │   ├── monitor.py          # POST /v1/monitor/start
│   │   └── sitemap.py          # POST /v1/sitemap
│   └── services/
│       └── pipeline.py         # Główna logika pipeline: fetch→generate→inject
│
├── core/                       # Python core — logika biznesowa niezależna od API
│   ├── fetcher.py              # YouTube: transkrypt + metadane (bez klucza API)
│   ├── generator.py            # AI: generowanie VideoObject/Clip/FAQ schema
│   ├── injector.py             # WordPress REST API: wstrzykiwanie SEO
│   ├── matcher.py              # Matchowanie postów WP ↔ YouTube ID
│   ├── monitor.py              # YouTube Channel Monitor (Mode A)
│   ├── profile.py              # Obsługa profili konfiguracyjnych
│   ├── sitemap.py              # Video sitemap XML
│   └── yt_admin.py             # YouTube admin (OAuth, zarządzanie kanałem)
│
├── web/                        # Next.js frontend — dashboard SaaS
│   ├── Dockerfile.web          # Multi-stage build (node:20-alpine)
│   ├── next.config.mjs         # AKTYWNY config (NIE .ts!)
│   ├── next.config.ts          # LEGACY — nie używany, zostawiony w repo
│   ├── package.json            # Zależności npm
│   ├── postcss.config.js       # Tailwind CSS processing (WYMAGANY)
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── .env.example            # Template dla web (NEXTAUTH_URL, BACKEND_URL...)
│   ├── public/                 # Static assets
│   └── src/
│       ├── middleware.ts        # NextAuth route protection
│       └── app/                # Next.js App Router
│           ├── layout.tsx
│           ├── page.tsx         # Landing page
│           ├── providers.tsx    # SessionProvider wrapper
│           ├── globals.css
│           ├── login/           # Strona logowania
│           ├── register/        # Rejestracja
│           ├── dashboard/
│           │   └── page.tsx     # Główny dashboard (generate + inject)
│           ├── admin/           # Panel admina (is_admin=True lub agency plan)
│           └── api/
│               └── auth/
│                   └── [...nextauth]/
│                       └── route.ts  # NextAuth handler (Credentials + Google)
│
├── local-runner/               # Windows Service — lokalny fetchor transkryptów
│   ├── runner.py               # Główny pętlownik: polluj API → pobieraj transkrypt → zwracaj
│   ├── service.py              # Windows Service wrapper (instalacja jako usługa)
│   ├── install.bat             # Instalacja jednym klikiem
│   ├── uninstall.bat           # Dezinstalacja
│   ├── requirements.txt        # yt-dlp, youtube-transcript-api, requests, dotenv
│   └── .env.example            # LOCAL_RUNNER_TOKEN, VSE_API_BASE
│
├── cli/                        # CLI tools (batch operacje)
├── scripts/                    # Skrypty pomocnicze
├── tests/                      # pytest — unit + integration
├── profiles/                   # Profile konfiguracyjne portali WP
├── registry/                   # Rejestr portali
├── knowledge/                  # Baza wiedzy SEO projektu
├── docs/                       # Dokumentacja techniczna
│
├── docker-compose.vse.yml      # Główny compose: vse-postgres + vse-api + vse-web
├── Dockerfile.api              # FastAPI image (python:3.11-slim)
├── Dockerfile                  # Legacy/alternatywny Dockerfile
├── requirements.txt            # Python dependencies (core + API)
├── batch_inject.py             # Batch injection script (shadow-perihelion heritage)
├── batch_seo_generate.py       # Batch generation script
├── inject_rest_v5.py           # Legacy standalone inject script
├── test_full_seo_v4.py         # Legacy test script
├── match_prawy_tv.py           # Legacy matcher script
├── AGENTS.md                   # Workspace rules dla agentów
├── ARCHITECTURE.md             # Ten plik
├── ROADMAP.md                  # Roadmapa produktu
└── README.md                   # Ogólne README
```

---

## 3. Kontenery Docker

### Plik: `docker-compose.vse.yml`

| Serwis | Container name | Image | Port (host:container) | Opis |
|--------|---------------|-------|-----------------------|------|
| `vse-postgres` | `vse-postgres` | `postgres:16-alpine` | `127.0.0.1:5434:5432` | Baza danych — dostępna TYLKO localhost VPS |
| `vse-api` | `vse-api` | build `Dockerfile.api` | `8085:8085` | FastAPI backend |
| `vse-web` | `vse-web` | build `web/Dockerfile.web` | `3001:3001` | Next.js frontend |

**Sieć Docker:** `vse-net` (bridge) — wszystkie trzy serwisy w tej samej sieci.

**Volumes:** `vse-pgdata` — persystentne dane PostgreSQL.

> ⚠️ **KRYTYCZNE:** Port `vse-web` MUSI być `"3001:3001"` (0.0.0.0 binding).
> `"127.0.0.1:3001:3001"` powoduje 502 z nginx — crimson-nginx nie widzi loopbacku.

### Zależności startu:
```
vse-postgres (healthcheck: pg_isready)
    └── vse-api (depends_on: vse-postgres healthy)
            └── vse-web (depends_on: vse-api started)
```

### Uruchomienie:
```bash
# Na VPS:
docker compose -f docker-compose.vse.yml up -d

# Rebuild tylko API:
docker compose -f docker-compose.vse.yml up -d --build vse-api

# Rebuild frontend:
docker compose -f docker-compose.vse.yml up -d --build vse-web

# Logi:
docker compose -f docker-compose.vse.yml logs -f vse-api
docker compose -f docker-compose.vse.yml logs -f vse-web
```

---

## 4. URL Conventions

### Routing Nginx (crimson-void — `/home/ubuntu/crimson-void/nginx/default.conf`)

```
Klient (przeglądarka)
    │
    ▼
Cloudflare CDN (vse.impresjapr.pl)
    │
    ▼
nginx (port 80/443 na VPS)
    ├─ /api/auth/*  → proxy → vse-web:3001   (NextAuth — MUSI być PRZED /api/)
    ├─ /api/v1/*    → proxy → vse-api:8085   (strip /api prefix → /v1/*)
    ├─ /docs        → proxy → vse-api:8085
    └─ /*           → proxy → vse-web:3001   (Next.js SSR)
```

> ⚠️ **KRYTYCZNE GOTCHA G9:** Kolejność bloków nginx MA znaczenie.
> Blok `location /api/auth/` MUSI być PRZED `location /api/`.
> Inaczej NextAuth jest proxowane do FastAPI → login nie działa.

### URL Conventions — podsumowanie

| Kontekst | URL | Do czego trafia |
|----------|-----|-----------------|
| Przeglądarka → API | `https://vse.impresjapr.pl/api/v1/generate` | nginx strip `/api` → `vse-api:8085/v1/generate` |
| Przeglądarka → Auth | `https://vse.impresjapr.pl/api/auth/session` | nginx → `vse-web:3001/api/auth/session` (NextAuth) |
| Server-side (SSR/NextAuth) → API | `http://vse-api:8085/v1/users/me` | Bezpośrednio Docker network — omija nginx |
| Local Runner → API | `https://vse.impresjapr.pl/v1/jobs/pending` | nginx → `vse-api:8085/v1/jobs/pending` |

### Env vars URL (w docker-compose.vse.yml dla vse-web):
```yaml
- NEXTAUTH_URL=https://vse.impresjapr.pl        # NextAuth canonical URL
- NEXT_PUBLIC_API_URL=https://vse.impresjapr.pl/api  # Klient-side (przeglądarka)
- BACKEND_URL=http://vse-api:8085               # Server-side (Docker network, bez /api)
```

### Jak dashboard woła API (web/src/app/dashboard/page.tsx):
```typescript
// Używa NEXT_PUBLIC_API_URL z env
// Poprawnie: /v1/generate (NIE /api/v1/generate — nginx dodaje strip)
fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/generate`, ...)
// = fetch('https://vse.impresjapr.pl/api/v1/generate', ...)
// nginx przetwarza: strip /api → GET vse-api:8085/v1/generate ✅
```

> ⚠️ **BUG który nas ugryził (G8):** Stary kod używał `/api/v1/*` bezpośrednio
> zamiast `${NEXT_PUBLIC_API_URL}/v1/*`. Fix: commit 2cb7889.

---

## 5. Auth Flow — krok po kroku

### 5A. Logowanie Email/Hasło (Credentials)

```
1. Użytkownik wypełnia formularz na /login
2. NextAuth CredentialsProvider.authorize() wywoływana server-side
3. NextAuth → BACKEND_URL (http://vse-api:8085) POST /v1/auth/login
   Body: { email, password }
4. FastAPI: weryfikuje hash bcrypt, zwraca:
   { access_token: "...", refresh_token: "...", user_id: "...", token_type: "bearer" }
5. NextAuth jwt callback: zapisuje accessToken + refreshToken do JWT cookie
6. NextAuth fetchUserProfile() → GET http://vse-api:8085/v1/users/me
   Header: Authorization: Bearer <access_token>
7. FastAPI zwraca plan.id i is_admin
8. JWT token rozszerzony: { plan: "free"|"starter"|"pro"|"agency", is_admin: bool }
9. Session cookie zapisana w przeglądarce
10. Middleware.ts sprawdza: token istnieje → redirect na /dashboard
```

### 5B. Google OAuth

```
1. Użytkownik klika "Zaloguj przez Google"
2. NextAuth redirect → Google OAuth consent
3. Google callback → NextAuth GoogleProvider
4. account.provider === 'google' w jwt callback
5. Uwaga: plan/is_admin dla Google OAuth pobierany przy następnym odświeżeniu (5 min)
6. Backend: GET /v1/auth/google → redirect → GET /v1/auth/google/callback
   (Google OAuth działa przez FastAPI, nie tylko NextAuth)
```

### 5C. Plan refresh (każde 5 minut)

```typescript
// W jwt callback:
const now = Math.floor(Date.now() / 1000)
const lastPlanFetch = token.planFetchedAt ?? 0
if (token.accessToken && !user && (now - lastPlanFetch > 300)) {
  // fetchUserProfile() → GET /v1/users/me
  // Aktualizuje token.plan i token.is_admin
}
```

### 5D. Ochrona tras (middleware.ts)

```typescript
// Chronione: /dashboard/*, /settings/*, /admin/*
// → requires valid NextAuth session
// /admin/* wymaga dodatkowo: is_admin=true lub plan="agency"
export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*', '/admin/:path*'],
}
```

### FastAPI JWT (api/auth.py)

```python
# Bearer token z nagłówka Authorization
# Dekoduje przez python-jose (RS256/HS256)
# Zależność: Depends(get_current_user)
# Weryfikuje user.is_active == True
```

---

## 6. Baza Danych — Schema

### Połączenie:
```
DATABASE_URL=postgresql+asyncpg://vse:${POSTGRES_PASSWORD}@vse-postgres:5432/vse
# Wewnątrz Docker: host = vse-postgres (nazwa serwisu)
# Z zewnątrz VPS (debug): postgresql://vse:pass@127.0.0.1:5434/vse
```

### Auto-migration:
```python
# api/main.py → startup_event()
# Base.metadata.create_all — bezpieczne (CREATE TABLE IF NOT EXISTS)
# Bez Alembic na produkcji — uproszczone podejście
```

### Tabela: `plans`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | String(50) PK | `"free"` \| `"starter"` \| `"pro"` \| `"agency"` |
| `display_name` | String(100) | Wyświetlana nazwa |
| `monthly_quota` | Integer | Liczba requestów/miesiąc (-1 = unlimited) |
| `wp_sites_limit` | Integer | Maks. portali WP (0 = żaden, copy-only) |
| `api_access` | Boolean | Dostęp przez API key |
| `price_pln` | Integer | Cena w groszach (PLN * 100) |
| `stripe_price_id` | String(200) nullable | Stripe integration (future) |

### Quota domyślne (seed przy starcie):

| plan_id | monthly_quota | wp_sites_limit | api_access | price_pln |
|---------|--------------|----------------|------------|----------|
| `free` | 5 | 1 | False | 0 |
| `starter` | 50 | 3 | True | 4900 |
| `pro` | 300 | 10 | True | 14900 |
| `agency` | 9999 | 999 | True | 49900 |

### Tabela: `users`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | UUID PK | Auto-generated uuid4 |
| `email` | String(255) UNIQUE | Email adres |
| `hashed_password` | String(255) nullable | bcrypt hash; NULL = OAuth-only |
| `full_name` | String(255) nullable | |
| `is_active` | Boolean | Konto aktywne |
| `is_verified` | Boolean | Email zweryfikowany |
| `is_admin` | Boolean | Dostęp do /v1/admin/* |
| `google_id` | String(255) nullable unique | Google OAuth sub |
| `plan_id` | String(50) FK→plans.id | Default: `"free"` |
| `stripe_customer_id` | String(255) nullable | |
| `stripe_subscription_id` | String(255) nullable | |
| `verification_token` | String(255) nullable | |
| `reset_token` | String(255) nullable | |
| `reset_token_expires` | DateTime nullable | |
| `created_at` | DateTime TZ | server_default=now() |
| `updated_at` | DateTime TZ | onupdate=now() |

### Tabela: `usage_logs`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | Integer PK autoincrement | |
| `user_id` | UUID FK→users.id | |
| `endpoint` | String(100) | Np. `"/v1/generate"` |
| `youtube_id` | String(50) nullable | YT video ID |
| `success` | Boolean | True = request zaliczony do quoty |
| `error_msg` | Text nullable | |
| `created_at` | DateTime TZ | |

### Tabela: `api_keys`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | UUID PK | |
| `user_id` | UUID FK→users.id | |
| `key_hash` | String(255) unique | bcrypt hash klucza |
| `name` | String(100) | Etykieta klucza |
| `is_active` | Boolean | |
| `last_used_at` | DateTime nullable | |
| `created_at` | DateTime TZ | |

### Tabela: `transcript_jobs`

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | UUID PK | |
| `video_url` | String(500) | URL YouTube video |
| `status` | String(20) indexed | `pending`\|`fetched`\|`processing`\|`done`\|`failed` |
| `transcript` | Text nullable | VTT transkrypt — NULL do czasu zwrotu przez runner |
| `error` | Text nullable | Opis błędu |
| `created_at` | DateTime TZ | |
| `updated_at` | DateTime TZ nullable | |
| `user_id` | UUID FK→users.id nullable | Opcjonalne — None dla internal calls |

---

## 7. API — Response Shapes

### GET /health
```json
{
  "status": "ok",
  "version": "2.0.0",
  "llm_default": "claude"
}
```

### GET /v1/users/me
**Wymaga:** `Authorization: Bearer <access_token>`
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "full_name": "Jan Kowalski",       // nullable
  "is_verified": true,
  "is_admin": false,
  "plan": {
    "id": "pro",
    "display_name": "Pro",
    "monthly_quota": 300,
    "wp_sites_limit": 10,
    "api_access": true
  },
  "usage": {
    "used_this_month": 12,
    "quota": 300,
    "percent": 4.0
  },
  "created_at": "2026-06-15T10:00:00+00:00"
}
```

### POST /v1/generate
**Request:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "llm_provider": "claude",           // "claude" | "gemini"
  "lang": "pl",
  "post_title": null                   // optional override
}
```
**Response:**
```json
{
  "status": "ok",
  "video_id": "VIDEO_ID",
  "processing_time_s": 47.3,
  "schema_data": {
    "video_object": { /* JSON-LD VideoObject */ },
    "clips": [ /* Clip[] z rozdziałami */ ],
    "faq": { /* FAQPage JSON-LD */ },
    "meta_description": "...",
    "title": "...",
    "focus_keyphrase": "...",
    "chapters_text": "00:00 Intro\n01:23 ..."
  },
  "error": null
}
```

### POST /v1/inject
**Request:**
```json
{
  "wp_post_id": 12345,               // Optional[int]: null = nowy post, int = aktualizacja
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "schema_data": { /* wynik z /v1/generate */ },
  "site_config": {
    "wp_base_url": "https://prawy.pl",
    "wp_user": "api_user",
    "wp_app_password": "xxxx xxxx xxxx"
  },
  "post_status": "draft"             // "draft" | "publish"
}
```
**Response:**
```json
{
  "status": "ok",
  "wp_post_id": 12345,               // ID posta (lub ID nowego gdy tworzono)
  "video_id": "VIDEO_ID",
  "rankmath_ok": true,
  "youtube_updated": false,
  "created": false,                  // true = nowy post utworzony
  "post_url": "https://prawy.pl/artykul",
  "error": null
}
```

### POST /v1/auth/login
**Request:**
```json
{ "email": "user@example.com", "password": "secret" }
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "uuid-string"
}
```

### GET /v1/jobs/pending (Local Runner)
**Wymaga:** `Authorization: Bearer <LOCAL_RUNNER_TOKEN>`
```json
[
  {
    "id": "uuid-string",
    "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "status": "pending"
  }
]
```

### POST /v1/jobs/{id}/result (Local Runner)
**Request:**
```json
{
  "transcript": "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nTreść transkryptu..."
}
```

---

## 8. API Endpoints — pełna mapa

| Metoda | Ścieżka | Auth | Opis |
|--------|---------|------|------|
| GET | `/health` | Brak | Health check |
| POST | `/v1/auth/register` | Brak | Rejestracja nowego użytkownika |
| POST | `/v1/auth/login` | Brak | Login → JWT pair |
| POST | `/v1/auth/refresh` | Brak | Refresh access token |
| GET | `/v1/auth/google` | Brak | Redirect do Google OAuth |
| GET | `/v1/auth/google/callback` | Brak | Google OAuth callback |
| GET | `/v1/users/me` | JWT | Profil + plan + użycie |
| POST | `/v1/generate` | JWT | Fetch YT + generuj SEO schema |
| POST | `/v1/inject` | JWT | Wstrzyknij schema do WP |
| POST | `/v1/process` | JWT | Pełny pipeline (generate + inject) |
| POST | `/v1/jobs/` | JWT | Utwórz job dla Local Runner |
| GET | `/v1/jobs/pending` | LocalRunner token | Lista pending jobów |
| POST | `/v1/jobs/{id}/result` | LocalRunner token | Zwróć transkrypt |
| GET | `/v1/jobs/{id}` | JWT | Status joba |
| POST | `/v1/monitor/start` | JWT | Uruchom monitor kanału YT |
| POST | `/v1/sitemap` | JWT | Generuj video sitemap XML |
| GET | `/v1/admin/users` | JWT + is_admin | Lista wszystkich userów |
| GET | `/v1/admin/users/{id}` | JWT + is_admin | Szczegóły usera |
| PATCH | `/v1/admin/users/{id}/plan` | JWT + is_admin | Zmień plan usera |
| GET | `/v1/admin/stats` | JWT + is_admin | Statystyki systemu |
| GET | `/docs` | Brak | Swagger UI |
| GET | `/redoc` | Brak | ReDoc UI |

---

## 9. Local Runner — Windows Service

### CO:
Windows Service na lokalnym PC użytkownika. Pobiera transkrypty YouTube i wysyła je do API na VPS.

### PO CO:
YouTube blokuje requests z Oracle Cloud VPS IP. Lokalne PC (domowe/biurowe IP) nie jest blokowane.
Local Runner to szyna komunikacji: VPS tworzy job → Runner pobiera transkrypt → zwraca przez REST API.

### JAK — instalacja:
```batch
:: Windows (jako Administrator)
cd local-runner
install.bat

:: Co robi install.bat:
:: 1. Tworzy venv w C:\ProgramData\VSELocalRunner\venv
:: 2. pip install -r requirements.txt
:: 3. Kopiuje .env do C:\ProgramData\VSELocalRunner\.env
:: 4. Rejestruje jako Windows Service (NSSM lub sc.exe)
:: 5. Uruchamia serwis
```

### Konfiguracja (`local-runner/.env`):
```bash
LOCAL_RUNNER_TOKEN=<token z VPS .env>
# Ten sam token musi być w .env API jako LOCAL_RUNNER_TOKEN

VSE_API_BASE=https://vse.impresjapr.pl
# POLL_INTERVAL=10          # sekundy między pollowaniem
# LOG_LEVEL=INFO
# LOG_DIR=C:\ProgramData\VSELocalRunner
```

### Flow komunikacji:
```
VPS API → tworzy job: status=pending (tabela transcript_jobs)
    ↑
Local Runner co 10s: GET /v1/jobs/pending
    ↓
    Local: yt-dlp / youtube-transcript-api → pobiera VTT
    ↓
Local Runner: POST /v1/jobs/{id}/result { transcript: "WEBVTT..." }
    ↓
VPS API: job.status = fetched → pipeline kontynuuje
```

### Aktualizacja:
```batch
:: Zatrzymaj serwis → git pull → restart
uninstall.bat
git pull origin main
install.bat
```

---

## 10. Deployment — od commit do live

### Standardowy deploy (SSH przez run_command):
```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-api"
```

### Deploy frontendu (po zmianie w web/):
```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
```

### Deploy pełny (rebuild wszystkiego):
```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build"
```

### Weryfikacja po deployu:
```bash
# Health check:
curl https://vse.impresjapr.pl/health
# Oczekiwany wynik: {"status":"ok","version":"2.0.0","llm_default":"claude"}

# Test auth:
curl -X POST https://vse.impresjapr.pl/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"password"}'

# Swagger (przeglądarka):
https://vse.impresjapr.pl/docs
```

### Ścieżka pliku compose na VPS:
```
/home/ubuntu/video-seo-engine/docker-compose.vse.yml
```

### Logi:
```bash
docker compose -f docker-compose.vse.yml logs --tail=100 -f vse-api
docker compose -f docker-compose.vse.yml logs --tail=100 -f vse-web
```

---

## 11. Zmienne Środowiskowe — Pełna Lista

### API (`.env` w root repo — używany przez docker-compose):

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API |
| `GEMINI_API_KEY` | ❌ | Alternatywny LLM |
| `DEFAULT_LLM_PROVIDER` | ❌ (def: claude) | `"claude"` \| `"gemini"` |
| `POSTGRES_PASSWORD` | ✅ | Hasło PostgreSQL |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://vse:{POSTGRES_PASSWORD}@vse-postgres:5432/vse` |
| `JWT_SECRET_KEY` | ✅ | Klucz podpisywania JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ (def: 15) | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ❌ (def: 30) | |
| `GOOGLE_CLIENT_ID` | ❌ | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | ❌ | Google OAuth |
| `GOOGLE_REDIRECT_URI` | ❌ | `https://vse.impresjapr.pl/api/v1/auth/google/callback` |
| `FRONTEND_URL` | ❌ (def: https://vse.impresjapr.pl) | CORS allowlist |
| `LOCAL_RUNNER_TOKEN` | ❌ | Token dla Windows Service runnera |
| `LOCAL_RUNNER_MODE` | ❌ (def: false) | `"true"` = pipeline używa jobqueue |
| `WP_BASE_URL` | ❌ | Default WP portal (batch scripts) |
| `WP_USER` | ❌ | WP Application Password user |
| `WP_APP_PASSWORD` | ❌ | WP Application Password |
| `LOG_LEVEL` | ❌ (def: INFO) | Logging level |

### Frontend (zmienne dockerowe w docker-compose.vse.yml):

| Zmienna | Wartość | Opis |
|---------|---------|------|
| `NEXTAUTH_URL` | `https://vse.impresjapr.pl` | NextAuth canonical URL |
| `NEXT_PUBLIC_API_URL` | `https://vse.impresjapr.pl/api` | Client-side (przeglądarka) |
| `BACKEND_URL` | `http://vse-api:8085` | Server-side (Docker network) |
| `PORT` | `3001` | Port Next.js |
| `NEXTAUTH_SECRET` | *(z .env)* | Klucz sesji NextAuth |
| `GOOGLE_CLIENT_ID` | *(z .env)* | |
| `GOOGLE_CLIENT_SECRET` | *(z .env)* | |

---

## 12. Known Gotchas — Pułapki Operacyjne

### G1 — Port binding `127.0.0.1:3001:3001` → nginx 502
```yaml
# ❌ NIE:
ports:
  - "127.0.0.1:3001:3001"

# ✅ TAK:
ports:
  - "3001:3001"  # 0.0.0.0 binding — nginx kontener widzi
```

### G2 — `next.config.ts` nie działa w Next.js 14
```
# ❌ next.config.ts → crash przy starcie
# ✅ next.config.mjs — zawsze
# UWAGA: oba pliki istnieją w repo — .ts jest legacy, .mjs jest aktywny
```

### G3 — Brak `postcss.config.js` → Tailwind nie działa
```js
// web/postcss.config.js MUSI istnieć:
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

### G4 — `npm ci` bez `package-lock.json` → build fail
```dockerfile
# Dockerfile.web:
# ❌ RUN npm ci  (wymaga package-lock.json)
# ✅ RUN npm install
```

### G5 — `COPY ... 2>/dev/null || true` w Dockerfile → checksum error
```
# Docker COPY nie obsługuje shell syntax
# Rozwiązanie: twórz .gitkeep w pustych katalogach + zwykłe COPY
```

### G6 — `git reset --hard` niszczy lokalne zmiany docker-compose na VPS
```
# Zawsze commituj docker-compose do GitHub przed deployem
# Nie edytuj pliku bezpośrednio na VPS
```

### G7 — Cloudflare cache serwuje stary 502
```
# Po naprawie routingu: Cloudflare → Caching → Purge Everything
```

### G8 — Dashboard wywołuje `/api/v1/*` zamiast `${NEXT_PUBLIC_API_URL}/v1/*`
```typescript
// ❌ Źle (podwójne /api/ lub nieprawidłowa ścieżka):
fetch('/api/v1/generate', ...)
fetch(`${API_URL}/api/v1/generate`, ...)

// ✅ Poprawnie:
fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/generate`, ...)
// = https://vse.impresjapr.pl/api/v1/generate → nginx strip → FastAPI /v1/generate
```

### G9 — Next.js rewrites przechwytują NextAuth
```js
// ❌ NIE dodawaj w next.config.mjs:
rewrites: [{ source: '/api/:path*', destination: `${backend}/:path*` }]
// To przechwytuje /api/auth/* → wysyła do FastAPI → login nie działa

// ✅ Routing TYLKO w nginx:
// location /api/auth/ { proxy_pass http://vse-web:3001; }   (PRZED /api/)
// location /api/v1/  { proxy_pass http://vse-api:8085; }    (strip prefix)
```

### G10 — next-auth v4 + Next.js 14 App Router TypeScript error
```js
// W next.config.mjs (już skonfigurowane):
typescript: { ignoreBuildErrors: true },
eslint: { ignoreDuringBuilds: true },
```

---

## 13. Pipeline Diagram — jak działa /v1/generate

```
Klient POST /v1/generate
    { video_url, llm_provider, lang }
    │
    ▼
FastAPI: api/routers/generate.py
    │ sprawdza JWT + quota
    ▼
api/services/pipeline.py
    │
    ├─ (jeśli LOCAL_RUNNER_MODE=true)
    │     │ POST /v1/jobs/ → job.status=pending
    │     │ Polling co 2s: GET /v1/jobs/{id}
    │     │ Czekaj na status=fetched
    │     └── transcript = job.transcript (VTT)
    │
    └─ (jeśli LOCAL_RUNNER_MODE=false)
          │ core/fetcher.py
          │     youtube-transcript-api → VTT
          └── transcript = VTT text
    │
    ▼
core/generator.py
    │ Buduje prompt z transkryptu
    │ Wywołuje Anthropic Claude API (lub Gemini)
    │ Parsuje odpowiedź JSON
    └── schema_data = { video_object, clips, faq, meta_description, title, ... }
    │
    ▼
Zwraca GenerateResponse { status, video_id, processing_time_s, schema_data }
```

---

## 14. Instrukcja Szybkiego Startu dla Workera

```
1. Przeczytaj ten dokument (KROK 0)
2. Przeczytaj AGENTS.md (reguły workspace)
3. Sprawdź heartbeat.json — kto ostatnio pracował i co zrobił
4. Sprawdź .agents/tasks/ — swój dispatch task
5. NIE edytuj plików lokalnie — zawsze GitHub MCP
6. NIE używasz SSH/VPS — deploy przez Supervisora
7. Zmiana w api/ → zmiana w tym pliku (ARCHITECTURE.md) jeśli dotyczy kontraktu API
8. Zmiana w web/ → sprawdź G8 i G9 przed commitem
9. Zmiana docker-compose → sprawdź G1 i G6
10. Raport do .agents/reports/ i sonic-void inbox po zakończeniu sesji
```

---

*vse-architect-01 | video-seo-engine | 2026-06-16 — v1.0 — initial architecture audit*
