# Architektura Video SEO Engine

> **CO:** Ten dokument opisuje pełną architekturę techniczną VSE — infrastrukturę VPS, stack kontenerów, przepływ autentykacji, pipeline SEO i schemę bazy danych.
>
> **PO CO:** Każdy agent wchodzący do projektu zaczyna od tego pliku. Bez niego traci czas na rekonstrukcję architektury z kodu. Ten dokument eliminuje tę potrzebę.
>
> **JAK:** Czytaj od góry — najpierw diagram ogólny, potem warstwy szczegółowe. Zanim cokolwiek zmienisz w infrastrukturze, sprawdź sekcję GOTCHA w `docs/deployment.md`.

---

## 1. Diagram ogólny — co jest gdzie

```
INTERNET
    │
    ▼
Cloudflare DNS → vse.impresjapr.pl
    │
    ▼
VPS Oracle ARM (147.224.162.100)
    │
    ├── crimson-nginx (współdzielony reverse proxy, docker crimson-void)
    │       ├── vse.impresjapr.pl:443 → /api/auth/* → 172.17.0.1:3001 (NextAuth)
    │       ├── vse.impresjapr.pl:443 → /api/*      → 172.17.0.1:8085 (FastAPI)
    │       └── vse.impresjapr.pl:443 → /*          → 172.17.0.1:3001 (Next.js)
    │
    └── docker-compose.vse.yml (sieć: vse-net)
            ├── vse-postgres  : PostgreSQL 16 (port 5434 localhost)
            ├── vse-api       : FastAPI (port 8085, 0.0.0.0)
            └── vse-web       : Next.js 14 (port 3001, 0.0.0.0)

LOKALNY PC UŻYTKOWNIKA
    └── VSELocalRunner (Windows Service)
            ├── Polling: GET /v1/jobs/pending (co 10s)
            ├── youtube-transcript-api (lokalne IP — YouTube OK)
            └── POST /v1/jobs/{id}/result → transkrypt do API
```

**Dlaczego ten układ?** VSE współdzieli VPS z crimson-void (inny projekt). Nginx od crimson-void pełni rolę globalnego proxy — obsługuje SSL termination i routing po domenach. VSE nie ma własnego nginx — dociera do niego przez `172.17.0.1` (bridge host IP widoczny z sieci dockera crimson-void).

**Dlaczego Local Runner?** Oracle Cloud IPs są blokowane przez YouTube dla requestów transkryptów (IP ban data center). Local Runner pobiera transkrypty z IP domowego/biurowego użytkownika i przekazuje do API. Wzorzec: GitHub Actions self-hosted runner.

---

## 2. Docker Compose — stos VSE

```yaml
# docker-compose.vse.yml (produkcja)

services:
  vse-postgres:
    image: postgres:16
    ports:
      - "5434:5432"    # 5434 bo 5432 zajęty przez crimson-postgres
    volumes:
      - vse-postgres-data:/var/lib/postgresql/data

  vse-api:
    build: .
    ports:
      - "8085:8000"    # FastAPI dostępny z hosta na 8085
    depends_on:
      - vse-postgres
    env_file: .env

  vse-web:
    build:
      context: web/
      dockerfile: Dockerfile.web
    ports:
      - "3001:3000"    # Next.js dostępny na 3001
                       # ⚠️ MUSI być "3001:3000" NIE "127.0.0.1:3001:3000"
    depends_on:
      - vse-api

networks:
  default:
    name: vse-net
```

> ⚠️ **KRYTYCZNE:** Port `vse-web` musi być `"3001:3000"` (binding na 0.0.0.0). Jeśli ustawisz `127.0.0.1:3001:3000`, crimson-nginx nie będzie widział kontenera i zwróci 502. Szczegóły: `docs/deployment.md` — GOTCHA #1.

---

## 3. Routing Nginx (crimson-nginx)

```nginx
# /home/ubuntu/crimson-void/nginx/default.conf — fragment dla vse.impresjapr.pl

server {
    listen 443 ssl;
    server_name vse.impresjapr.pl;

    # ⚠️ KOLEJNOŚĆ BLOKÓW MA ZNACZENIE!
    # NextAuth MUSI być przed /api/* — inaczej trafi do FastAPI i login przestanie działać

    location /api/auth/ {
        proxy_pass http://172.17.0.1:3001;   # NextAuth obsługiwany przez Next.js
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        rewrite ^/api/(.*) /v1/$1 break;     # Strip /api prefix
        proxy_pass http://172.17.0.1:8085;   # FastAPI
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://172.17.0.1:3001;   # Next.js frontend
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
}
```

**Dlaczego `/api/auth/` przed `/api/`?** NextAuth obsługuje `/api/auth/*` przez Next.js. Gdyby `/api/*` był pierwszy, żądania logowania trafiałyby do FastAPI i zwracałyby 404. Nginx matchuje bloki od najdłuższego/pierwszego — kolejność jest krytyczna.

---

## 4. Mapa modułów FastAPI

```
api/
├── main.py              # Entry point FastAPI. Montuje routery, CORS, lifespan (DB init).
├── db.py                # SQLAlchemy async engine + session factory. Łączy się z vse-postgres.
├── auth.py              # bcrypt hashing (NIE passlib!) + JWT encode/decode.
│                        # ⚠️ Używamy bezpośrednio bcrypt, nie passlib — był konflikt zależności.
├── models/
│   ├── user.py          # SQLAlchemy model: User (UUID PK, email, hashed_password, plan_id, ...)
│   ├── plan.py          # SQLAlchemy model: Plan (id string, display_name, monthly_quota, ...)
│   ├── job.py           # SQLAlchemy model: TranscriptJob (dla Local Runner)
│   ├── request.py       # Pydantic: ProcessRequest, GenerateRequest, InjectRequest
│   └── response.py      # Pydantic: ProcessResponse, GenerateResponse, ErrorResponse
├── routers/
│   ├── auth.py          # POST /v1/auth/register, POST /v1/auth/login
│   ├── users.py         # GET /v1/users/me (profil zalogowanego)
│   ├── process.py       # POST /v1/process (full pipeline)
│   ├── generate.py      # POST /v1/generate (tylko generowanie SEO)
│   ├── inject.py        # POST /v1/inject (tylko publikacja do WP)
│   ├── jobs.py          # GET /v1/jobs/pending, POST /v1/jobs/{id}/result (Local Runner)
│   ├── monitor.py       # POST /v1/monitor/start (YouTube Channel Monitor)
│   └── sitemap.py       # GET /v1/sitemap
└── services/
    └── pipeline.py      # Orkiestracja: fetch → generate → inject
                         # LOCAL_RUNNER_MODE: deleguje fetch do TranscriptJob queue
```

### Jak działa lifespan?

`main.py` używa FastAPI `lifespan` context manager — przy starcie kontenera automatycznie:
1. Tworzy tabele (jeśli nie istnieją)
2. Seeduje plany (`free`, `starter`, `pro`, `agency`) z `ON CONFLICT DO NOTHING`

Dzięki temu nie trzeba ręcznie inicjalizować bazy po deploymencie.

---

## 5. Auth Flow — od rejestracji do dashboardu

```
USER                    Next.js Frontend         FastAPI /v1/auth/      PostgreSQL
 │                             │                        │                    │
 │── wpisuje email+hasło ──►   │                        │                    │
 │                             │── POST /api/auth/register ──────────────►  │
 │                             │   (trafia przez NextAuth do FastAPI)        │
 │                             │                        │── bcrypt hash ──►  │
 │                             │                        │── INSERT user ──►  │
 │                             │◄── 200 {user_id} ──────│                    │
 │                             │                        │                    │
 │── wpisuje login+hasło ──►   │                        │                    │
 │                             │── POST /api/auth/login ───────────────────► │
 │                             │                        │── bcrypt verify ─► │
 │                             │                        │── SELECT user ──►  │
 │                             │                        │◄── user record ─── │
 │                             │◄── 200 {access_token} ─│                    │
 │                             │                        │                    │
 │                             │  (NextAuth zapisuje JWT w session cookie)   │
 │                             │                        │                    │
 │── otwiera /dashboard ──►    │                        │                    │
 │                             │  (middleware.ts sprawdza session cookie)     │
 │                             │  jeśli brak → redirect /login               │
 │◄── renderuje dashboard ──── │                        │                    │
```

**Gdzie żyje token?** NextAuth v4 przechowuje JWT w zaszyfrowanym session cookie (NEXTAUTH_SECRET). Frontend nie widzi surowego tokena — Next.js middleware weryfikuje session po stronie serwera.

**Jak API rozpoznaje usera?** Endpointy FastAPI wymagające auth (np. `/v1/process`) przyjmują `Authorization: Bearer <jwt_token>`. Frontend przekazuje token z `session.accessToken` (NextAuth custom callback).

---

## 6. Pipeline SEO — od URL do WordPressa

```
USER wkleja URL YouTube
         │
         ▼
   POST /api/process lub /api/generate
         │
         ▼
    ┌─────────────────────────────────────────────┐
    │  fetcher                                     │
    │  (LOCAL_RUNNER_MODE=true → via job queue)    │
    │                                             │
    │  ┌─ LOCAL_RUNNER_MODE=false (direct) ──────┐│
    │  │  youtube-transcript-api + yt-dlp        ││
    │  │  ⚠️ Zablokowane z Oracle Cloud IPs!     ││
    │  └──────────────────────────────────────────┘│
    │                                             │
    │  ┌─ LOCAL_RUNNER_MODE=true (via queue) ────┐│
    │  │  1. Utwórz TranscriptJob (status=pending)││
    │  │  2. Poll job co 2s max 120s             ││
    │  │  3. VSELocalRunner (Windows Service)    ││
    │  │     pobiera transkrypt lokalnie (OK IP) ││
    │  │  4. Runner: POST /v1/jobs/{id}/result   ││
    │  │  5. status=fetched → pobierz transcript ││
    │  └──────────────────────────────────────────┘│
    └─────────────┬───────────────────────────────┘
          │ transcript + metadata JSON
          ▼
    ┌────────────┐
    │ generator  │  → Claude API (Anthropic) — domyślny LLM
    │            │    Prompt → generuje:
    │            │    - VideoObject JSON-LD (v5.3, Google 2026)
    │            │    - Clip[] (rozdziały z timestampami)
    │            │    - FAQPage (pytania z transkryptu)
    │            │    - meta_description, article_title
    │            │    Czas: ~50s per wideo
    └─────┬──────┘
          │ schema JSON
          ▼
    ┌────────────┐
    │  injector  │  → WordPress REST API v2 (Application Passwords)
    │  (opcja)   │    PUT /wp-json/wp/v2/posts/{id}
    │            │    Atomically: dodaje JSON-LD do <head>, aktualizuje
    │            │    RankMath meta, chapters, video sitemap entry
    └────────────┘

OUTPUT (Free/Starter): JSON z polami schema, FAQ, chapters — do ręcznego wklejenia
OUTPUT (Pro/Agency):   Automatyczna publikacja do wybranego portalu WP
```

**Dlaczego Claude, nie Gemini?** ANTHROPIC_API_KEY jest aktywny na VPS. GEMINI_API_KEY jest opcjonalny (jeszcze nie skonfigurowany). Generator obsługuje oba — wybór przez env var `LLM_PROVIDER`.

---

## 7. Schemat bazy danych (PostgreSQL 16)

### Tabela: `plans`

| Kolumna | Typ | Opis |
|---|---|---|
| `id` | VARCHAR PK | `free` / `starter` / `pro` / `agency` |
| `display_name` | VARCHAR | Nazwa wyświetlana np. "Free", "Pro" |
| `monthly_quota` | INTEGER | Limit requestów/mies. (0 = unlimited) |
| `wp_sites_limit` | INTEGER | Max portali WordPress (1 dla free/starter) |
| `api_access` | BOOLEAN | Czy może używać API bezpośrednio |
| `price_pln` | DECIMAL | Cena miesięczna PLN (0 dla free) |

Seed (automatyczny przy starcie):
```sql
INSERT INTO plans (id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln)
VALUES
  ('free',    'Free',    10,  1, false, 0),
  ('starter', 'Starter', 50,  1, false, 49),
  ('pro',     'Pro',     200, 3, true,  149),
  ('agency',  'Agency',  0,   0, true,  399)
ON CONFLICT (id) DO NOTHING;
```

### Tabela: `users`

| Kolumna | Typ | Opis |
|---|---|---|
| `id` | UUID PK | Auto-generated |
| `email` | VARCHAR UNIQUE | Login użytkownika |
| `hashed_password` | VARCHAR | bcrypt hash |
| `plan_id` | VARCHAR FK | Referencja do `plans.id` |
| `is_active` | BOOLEAN | Blokada konta |
| `is_admin` | BOOLEAN | Uprawnienia admin |
| `created_at` | TIMESTAMP | Data rejestracji |

### Tabela: `transcript_jobs` *(dodana w Faza 3)*

| Kolumna | Typ | Opis |
|---|---|---|
| `id` | UUID PK | Auto-generated |
| `video_url` | VARCHAR | YouTube URL do pobrania |
| `status` | VARCHAR | `pending` / `fetched` / `processing` / `done` / `failed` |
| `transcript` | TEXT | NULL do czasu zwrotu przez Local Runner |
| `error` | TEXT | NULL jeśli OK |
| `created_at` | TIMESTAMP | Data utworzenia jobu |
| `updated_at` | TIMESTAMP | Data ostatniej aktualizacji |
| `user_id` | UUID FK | Kto zlecił |

**Po co ta tabela?** Kolejka komunikacji między VPS API a Local Runner. API tworzy job (pending), Local Runner pobiera transkrypt lokalnie i zwraca wynik (fetched). Bez tej tabeli Oracle Cloud IP ban blokuje cały pipeline.

### Tabele w trakcie implementacji

- `sites` — skonfigurowane portale WP per user (dla pro/agency)

---

## 8. Frontend — Mapa Next.js

```
web/src/
├── app/
│   ├── layout.tsx               # Root layout. SessionProvider wrapper.
│   ├── page.tsx                 # Landing page — publiczna, prezentacja produktu
│   ├── globals.css              # Tailwind base styles
│   ├── providers.tsx            # SessionProvider (NextAuth)
│   ├── login/
│   │   └── page.tsx             # Formularz: email + hasło. Client component.
│   ├── register/
│   │   └── page.tsx             # Formularz rejestracji.
│   ├── dashboard/
│   │   └── page.tsx             # Główna strona produktu:
│   │                            # - Input: URL YouTube
│   │                            # - POST /api/generate
│   │                            # - Wyniki: JSON-LD, FAQ, chapters, meta_desc
│   │                            # - Przyciski Kopiuj per sekcja
│   │                            # - (Pro/Agency) Sekcja Publikuj do WP
│   └── api/
│       └── auth/
│           └── [...nextauth]/
│               └── route.ts     # NextAuth handler — credentials + Google OAuth
└── middleware.ts                # Ochrona /dashboard/* — redirect do /login jeśli brak session
```

**Stack frontendu:**
- **Next.js 14** z App Router (nie Pages Router)
- **Tailwind CSS v3** — wymaga `web/postcss.config.js` (bez niego CSS się nie kompiluje)
- **NextAuth v4** — email+password + Google OAuth (aktywny od 2026-06-15)
- **`next.config.mjs`** — NIE `.ts` (Next.js 14 nie obsługuje `.ts` konfiguracji)

---

## 9. Zmienne środowiskowe

> ⚠️ Nigdy nie commituj `.env` do repo. Żyje tylko na VPS w `/home/ubuntu/vse/`.

| Zmienna | Wymagana | Opis |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude API — aktywny na VPS |
| `JWT_SECRET_KEY` | ✅ | Podpis tokenów JWT (min. 32 znaki) |
| `NEXTAUTH_SECRET` | ✅ | Szyfrowanie sesji NextAuth |
| `NEXTAUTH_URL` | ✅ | `https://vse.impresjapr.pl` |
| `POSTGRES_PASSWORD` | ✅ | Hasło PostgreSQL |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@vse-postgres:5432/vse` |
| `LOCAL_RUNNER_MODE` | ✅ | `true` gdy Local Runner aktywny (Oracle IP ban workaround) |
| `LOCAL_RUNNER_TOKEN` | ✅ gdy LOCAL | Bearer token dla Local Runner (min. 32 znaki) |
| `WP_USER` | Dla inject | WordPress username |
| `WP_APP_PASSWORD` | Dla inject | WordPress Application Password |
| `WP_BASE_URL` | Dla inject | np. `https://prawy.pl` |
| `GEMINI_API_KEY` | Opcjonalna | Alternatywny LLM |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth (aktywny od 2026-06-15) |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth (aktywny od 2026-06-15) |

---

## 10. Pliki konfiguracyjne — mapa

| Plik | Rola |
|---|---|
| `docker-compose.vse.yml` | Definicja stacku VSE (postgres, api, web) |
| `Dockerfile.api` | Build FastAPI — Python 3.10, instaluje yt-dlp |
| `web/Dockerfile.web` | Multi-stage Next.js — `npm install` (NIE `npm ci`) |
| `web/next.config.mjs` | standalone output, ignoreBuildErrors, ignoreDuringBuilds |
| `web/postcss.config.js` | Tailwind CSS processing — MUSI istnieć |
| `web/tailwind.config.ts` | Tailwind konfiguracja |
| `api/main.py` | FastAPI entry, lifespan (auto-seed plans) |
| `api/auth.py` | bcrypt + JWT (NIE passlib) |
| `api/db.py` | SQLAlchemy async session |
| `local-runner/runner.py` | Local Transcript Runner — polling + youtube-transcript-api |
| `local-runner/install.bat` | Instalator Windows Service (NSSM) |

---

## 11. Tryby operacji (MODE A / MODE B)

### MODE A — YouTube Channel Monitor (push)

**CO:** Daemon monitoruje nowe filmy na kanale YT i automatycznie tworzy artykuły.
**PO CO:** Agencje chcą zero-touch — film się pojawia, artykuł na portalu sam się tworzy.
**JAK:** `POST /v1/monitor/start` → background task polling kanał co X minut → przy nowym filmie wywołuje wewnętrznie `/v1/process`.
**Zależność:** Wymaga działającego Local Runner (transkrypty przez lokalny PC).
**Status:** Zaimplementowany w `core/monitor.py`, endpoint w `api/routers/monitor.py`. Wymaga testów E2E.

### MODE B — Portal Scanner (pull)

**CO:** Skanuje istniejący portal WP, identyfikuje osadzone filmy YouTube, wzbogaca o SEO.
**PO CO:** Portale mają setki artykułów z filmami bez schema.org — jednorazowy bulk enrichment.
**JAK:** `core/matcher.py` pobiera posty z WP REST API, filtruje te z youtube.com w treści, uruchamia pipeline per film.
**Status:** Zaimplementowany w CLI (`cli/main.py`). Użyty produkcyjnie na prawy.pl (213+ postów w kolejce).

---

## 12. Local Transcript Runner (Windows Service) *(Faza 3)*

**CO:** Mały program w Python działający jako Windows Service na lokalnym PC użytkownika. Polling API VSE po joby do wykonania, pobieranie transkryptów z YouTube lokalnie (IP domowe = nie zablokowane), odsyłanie wyników do API.

**PO CO:** Oracle Cloud IPs są banowane przez YouTube dla requestów transkryptów. Bez tego Local Runnera pipeline VSE nie może pobrać transkryptu — a bez transkryptu generator (Claude) nie ma danych wejściowych.

**JAK działa:**
```
[Windows Service — VSELocalRunner]
  startuje z Windows (SCM)
  │
  └── co 10 sekund:
        GET https://vse.impresjapr.pl/v1/jobs/pending
        │   Bearer: LOCAL_RUNNER_TOKEN
        │
        └── dla każdego pending job:
              youtube-transcript-api.fetch(video_id)  ← lokalny IP, YouTube OK
              POST /v1/jobs/{id}/result {transcript, status: "fetched"}
```

**Lokalizacja w repo:** `local-runner/`

| Plik | Rola |
|---|---|
| `local-runner/runner.py` | Logika pollingu i fetchowania |
| `local-runner/.env.example` | `LOCAL_RUNNER_TOKEN=...` |
| `local-runner/install.bat` | Autoinstalacja (wymaga NSSM + Python) |
| `local-runner/uninstall.bat` | Deinstalacja |
| `local-runner/requirements.txt` | `youtube-transcript-api`, `requests`, `python-dotenv` |

**Warunek działania:** PC musi być włączony gdy pipeline jest wywoływany.
**Service name:** `VSELocalRunner` (widoczny w `services.msc`).
**Log:** `C:\ProgramData\VSELocalRunner\runner.log`.

---

## 13. Linki operacyjne

| Zasób | URL / Ścieżka |
|---|---|
| Site produkcyjny | https://vse.impresjapr.pl |
| Swagger API | https://vse.impresjapr.pl/docs |
| VPS | 147.224.162.100 (Oracle ARM) |
| Nginx config | `/home/ubuntu/crimson-void/nginx/default.conf` (VPS) |
| Docker compose | `docker-compose.vse.yml` |
| Deployment runbook | `docs/deployment.md` |
| API reference | `docs/api-reference.md` |

---

*vse-architect-01 | video-seo-engine | 2026-06-15 — v1.0*  
*Zaktualizowano: 2026-06-15 [Supervisor 01] — dodano sekcje Local Runner (12), transcript_jobs DB, LOCAL_RUNNER_MODE, zaktualizowano pipeline diagram (6)*  
*Aktualizuj ten plik przy każdej zmianie architektury (jako część commitu).*
