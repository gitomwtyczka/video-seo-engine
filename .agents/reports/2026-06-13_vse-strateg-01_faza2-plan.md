# VSE Faza 2 — Architektura multi-tenant FastAPI
# vse-strateg-01 | video-seo-engine | 2026-06-13

---

## 📊 Stan oracle-crimson (recon 2026-06-13 23:19)

### Kontenery aktywne
```
NAMES                  STATUS        PORTS
crimson-nginx          Up 2w         :80, :443
crimson-frontend       Up 2w         :3000
crimson-backend        Up 2w         :8001
crawler-daemon         Up 7w         :8000 (wewnętrzny)
crawler-web            Up 7w         :8002
crawler-db             Up 7w         :5433
crimson-postgres       Up 7w         :5432
prawy-wordpress        Up 3w         :8081
prawy-mysql            Up 7w         :3306
app-muzeum-browser-1   Up 3d         :8082
academy-app            Up 4d         :8083
lekki-szlak-web        Up 10d        :8084
```

### Zasoby
- Dysk: 156G/194G (81%) — 38G wolne ✔️ wystarczy
- ANTHROPIC_API_KEY: dostępny w /home/ubuntu/crimson-void/backend/.env.production

### Wybrany port dla VSE API: **:8085**

---

## 🏗️ Architektura VSE Faza 2

### Koncepcja: VSE jako samodzielny serwis multi-tenant

VSE nie jest dedykowany prawy.pl. Jest platformą — obsługuje wiele portali.
Każde zapytanie niesie własny context (site_url, wp_user, wp_password).
Opcjonalnie: OAuth YouTube per-site.

```
┌─────────────────────────────────┐
│   CLIENT (SaaS/CLI/Plugin)      │
└─────────┬──────────────────────┘
         │
         ▼  REST JSON
┌─────────────────────────────────┐
│   vse-api (FastAPI :8085)       │
│   +--------------------------+  │
│   | /v1/process              |  │
│   | /v1/generate             |  │
│   | /v1/inject               |  │
│   | /v1/monitor/start        |  │
│   | /v1/sitemap              |  │
│   | /health                  |  │
│   +--------------------------+  │
│   core/ (istniejące moduły)   │
└─────────┬──────────────────────┘
         │
    ┌────┼──────┐
    │         │
    ▼         ▼
Gemini/Claude  WordPress REST API
    API        (per-site, multi-tenant)
```

---

## 📌 Endpoints (priorytety)

### Priorytet 1 — MVP

#### POST /v1/process
```json
// Wejście
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "site_config": {
    "wp_base_url": "https://prawy.pl",
    "wp_user": "admin",
    "wp_app_password": "xxxx xxxx xxxx"
  },
  "options": {
    "auto_inject": true,
    "update_youtube": false,
    "llm_provider": "claude"  // "claude" | "gemini"
  }
}

// Wyjście
{
  "status": "success",
  "video_id": "VIDEO_ID",
  "wp_post_id": 12345,
  "schema_generated": true,
  "injected": true,
  "youtube_updated": false,
  "processing_time_s": 8.4
}
```

#### POST /v1/generate
```json
// Tylko generacja schema — bez inject
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "llm_provider": "claude"
}
// Wyjście: pełny JSON-LD schema
```

#### POST /v1/inject
```json
// Inject gotowego schema do WP
{
  "wp_post_id": 12345,
  "schema_json": { /* VideoObject JSON-LD */ },
  "site_config": { ... }
}
```

#### GET /health
```json
{"status": "ok", "version": "2.0.0", "llm": "claude"}
```

### Priorytet 2 — Monitor

#### POST /v1/monitor/start
```json
{
  "channel_id": "UCxxxxxx",
  "site_config": { ... },
  "options": { "check_interval_min": 60 }
}
// Uruchamia background task — zwraca monitor_id
```

#### GET /v1/monitor/{monitor_id}/status

### Priorytet 3 — Bulk + Sitemap

#### POST /v1/sitemap
#### POST /v1/scan  // Portal Scanner (MODE B)

---

## 📦 Struktura projektów

```
video-seo-engine/
├── api/                      # NOWE
│   ├── main.py               # FastAPI app entry
│   ├── routers/
│   │   ├── process.py        # /v1/process
│   │   ├── generate.py       # /v1/generate
│   │   ├── inject.py         # /v1/inject
│   │   ├── monitor.py        # /v1/monitor
│   │   └── sitemap.py        # /v1/sitemap
│   ├── models/
│   │   ├── request.py        # Pydantic schemas
│   │   └── response.py
│   └── services/
│       └── pipeline.py       # Orchestration warstwy core/
├── core/                     # ISTNIEJE — bez zmian
├── Dockerfile.api            # NOWE
├── docker-compose.vse.yml    # NOWE — standalone compose
└── .env.api.example          # NOWE — template
```

---

## 🐳 Docker compose snippet

```yaml
# docker-compose.vse.yml
version: '3.8'

services:
  vse-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: vse-api
    ports:
      - "8085:8085"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DEFAULT_LLM_PROVIDER=claude
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data          # cache transkryptów
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 🔑 Multi-tenant: jak obsługujemy kilka portali

Każde zapytanie API zawiera `site_config` in-request (stateless).
**Nie ma bazy danych per-tenant na MVP.**

Powód tej decyzji:
- Prostota deployu — jeden kontener, brak migracji
- SaaS auth (API key per-site) — Faza 3, nie Faza 2
- Credentials wp_user/wp_app_password per-request — passe przez HTTPS, bezpieczne

Faza 3 (SaaS): połączymy z crimson-backend auth lub osobną bazą.

---

## 🔐 ANTHROPIC_API_KEY — mount strategy

NIE kopiujemy `.env.production` z crimson-backend.
Tworzymy dedykowane `/home/ubuntu/vse-api/.env`:

```bash
# /home/ubuntu/vse-api/.env
ANTHROPIC_API_KEY=sk-ant-api03-xxxx  # kopiujemy value ręcznie raz
GEMINI_API_KEY=AIza...               # opcjonalny
DEFAULT_LLM_PROVIDER=claude
LOG_LEVEL=INFO
```

Powód izolacji: crimson-backend ma inne sekrety (Postgres, itp).
VSE API ma minimalny .env — łatwiejsza rotacja kluczy.

---

## ✅ Decyzje strategiczne

| Decyzja | Wartość | Uzasadnienie |
|---------|--------|--------------|
| Port | :8085 | wszystkie porty do :8084 zajęte |
| Auth MVP | brak (per-request site_config) | prostota, Faza 2 to internal tool |
| DB | brak na MVP | stateless, per-request |
| LLM default | claude | ANTHROPIC_API_KEY już aktywny na VPS |
| Build | Docker multi-stage | spójne z resztą ekosystemu |
| nginx | dodge — brak proxy dla :8085 | internal use; SaaS → Faza 3 doda route |

---

*vse-strateg-01 | video-seo-engine | 2026-06-13*
