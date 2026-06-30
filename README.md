# PressAI Video SEO Engine

> **Automated video content optimization pipeline** — from YouTube channel to SEO-ready WordPress article in minutes.

[![Status](https://img.shields.io/badge/status-active%20pipeline-brightgreen)](https://vse.impresjapr.pl)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-proprietary-red)](LICENSE)

**CO:** VSE to SaaS freemium do automatycznego generowania SEO dla treści wideo. Pipeline: YouTube URL → transkrypt VTT → AI (Claude/Gemini) → schema VideoObject/FAQ/chapters → WordPress REST API.

**PO CO:** Klienci free dostają gotowe fragmenty HTML do wklejenia. Klienci pro dostają pełną automatyzację. Benchmark: prawy.pl 8/10 vs TVP Info 3/10 (schema.org, Google 2026).

---

## 📚 Dokumentacja

| Dokument | Zawartość |
|---|---|
| **[docs/architecture.md](docs/architecture.md)** | Architektura VPS, docker, nginx, auth flow, pipeline, schemat DB |
| **[docs/deployment.md](docs/deployment.md)** | Runbook deploy + **9 krytycznych GOTCHA** (czytaj przed każdym deployem) |
| **[docs/api-reference.md](docs/api-reference.md)** | Wszystkie endpointy z przykładami request/response |
| **[AGENTS.md](AGENTS.md)** | Reguły workspace dla agentów AI |

> ⚠️ **PRZED pierwszym deployem:** Przeczytaj `docs/deployment.md` — sekcja GOTCHA zawiera 9 pułapek, każda z nich kosztowała sesję debugowania.

---

## 🎯 Co to robi

Dwie ścieżki operacyjne:

- **Channel Monitor (MODE A)** — obserwuje kanał YouTube; nowy film = automatyczny draft na WordPress
- **Portal Scanner (MODE B)** — skanuje istniejący portal WP, znajduje osadzone filmy i wzbogaca je o schema, chapters, FAQ, sitemap

**Live benchmark (prawy.pl, maj 2026):**
- Score: **8/10** vs TVP Info **3/10**, wPolityce **2/10**
- 6 postów przetworzonych, **213+ w kolejce**

---

## ✨ Kluczowe funkcje

- **VideoObject Schema (JSON-LD)** — pełna zgodność ze specyfikacją Google 2026
- **AI-generated chapters** — Claude/Gemini tworzy timestampowane wpisy `Clip` z transkryptu
- **AI-generated FAQ** — `FAQPage` schema z treści transkryptu
- **VTT transcript fetching** — bez klucza YouTube API (`youtube-transcript-api` + `yt-dlp`)
- **Video Sitemap generation** — XML dla Google (uzupełnienie auto-detekcji RankMath)
- **WordPress REST API injection** — atomowe aktualizacje postów z rollback
- **Multi-tenant API** — jeden serwis VSE obsługuje wiele portali ✅ LIVE

---

## 🚀 Quick Start (lokalny dev)

```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Skonfiguruj credentials
cp .env.example .env
# Edytuj .env — wymagane: ANTHROPIC_API_KEY, WP_USER, WP_APP_PASSWORD, WP_BASE_URL

# 3. CLI — podstawowy przepływ
python -m cli.main fetch --video https://youtube.com/watch?v=VIDEO_ID
python -m cli.main generate --video VIDEO_ID
python -m cli.main inject --post-id WP_POST_ID --video VIDEO_ID

# 4. Generowanie sitemap
python -m cli.main sitemap --output video-sitemap.xml
```

## 🐳 Quick Start (Docker — pełny stack)

```bash
# Wymagania: Docker + .env z wartościami produkcyjnymi
cp .env.api.example .env

# Uruchom stack (postgres + api + web)
docker-compose -f docker-compose.vse.yml up -d

# Sprawdź czy działa
curl http://localhost:8085/health
# → {"status":"ok","version":"2.0.0","llm_default":"claude"}

# Frontend
open http://localhost:3001
```

**Pełny runbook produkcyjny:** [docs/deployment.md](docs/deployment.md)

---

## 🏗️ Architektura

```
INTERNET → Cloudflare DNS → vse.impresjapr.pl
                                    │
                             crimson-nginx (VPS)
                              ├── /api/auth/* → Next.js :3001
                              ├── /api/*      → FastAPI :8085
                              └── /*          → Next.js :3001

docker-compose.vse.yml:
  vse-postgres  (PostgreSQL 16, port 5434)
  vse-api       (FastAPI, port 8085)
  vse-web       (Next.js 14, port 3001)
```

Szczełowy opis z diagramami: [docs/architecture.md](docs/architecture.md)

### Pipeline SEO

```
URL YouTube → [fetcher] → VTT + metadata
            → [generator] Claude/Gemini → VideoObject + FAQ + chapters (~50s)
            → [injector] WordPress REST API → published post
```

---

## 🛠️ Tech Stack

| Komponent | Technologia |
|-----------|------------|
| Core pipeline | Python 3.10+ |
| AI generation | Claude (Anthropic) — aktywny / Gemini — opcjonalny |
| YouTube data | `youtube-transcript-api` 1.2.4+ + `yt-dlp` |
| WordPress | REST API v2 (Application Passwords) |
| Schema | JSON-LD, Schema.org VideoObject / Clip / FAQPage |
| Backend API | FastAPI + uvicorn |
| Frontend | Next.js 14 + Tailwind CSS v3 + NextAuth v4 |
| Baza danych | PostgreSQL 16 |
| Infrastructure | Oracle ARM VPS + Docker + nginx |

---

## 📁 Struktura projektu

```
video-seo-engine/
├── api/                    # FastAPI multi-tenant service ✅
│   ├── main.py             # Entry point, lifespan (auto-seed plans)
│   ├── auth.py             # bcrypt + JWT (NIE passlib!)
│   ├── db.py               # SQLAlchemy async
│   ├── routers/            # /v1/process, /v1/generate, /v1/inject, ...
│   ├── models/             # Pydantic + SQLAlchemy models
│   └── services/           # Pipeline orchestration
├── core/
│   ├── fetcher.py          # YouTube: transcripts + metadata (bez API key)
│   ├── matcher.py          # Match WP posts ↔ YouTube IDs
│   ├── generator.py        # AI schema generation (VideoObject, Clip, FAQ)
│   ├── injector.py         # WordPress REST API injection
│   ├── sitemap.py          # Video sitemap XML
│   ├── monitor.py          # Channel Monitor [Faza 2]
│   └── yt_admin.py         # YouTube admin ops [Faza 2]
├── web/                    # Next.js 14 frontend
│   ├── src/app/
│   │   ├── page.tsx        # Landing page
│   │   ├── dashboard/      # Dashboard (2 ścieżki: Free/Pro)
│   │   ├── login/          # Logowanie
│   │   └── register/       # Rejestracja
│   ├── Dockerfile.web
│   └── next.config.mjs     # MUSI być .mjs (nie .ts!)
├── cli/
│   └── main.py             # CLI entry point
├── docs/                   # ⭐ Dokumentacja — START TUTAJ
│   ├── architecture.md     # Architektura systemu
│   ├── deployment.md       # Runbook deploy + GOTCHA
│   └── api-reference.md    # API dokumentacja
├── .agents/                # Agent workspace
├── docker-compose.vse.yml  # Stack VSE
├── Dockerfile.api          # FastAPI build
├── .env.example            # Template credentials (CLI)
├── .env.api.example        # Template credentials (API/Docker)
└── requirements.txt
```

---

## 🔐 Bezpieczeństwo

- **Credentials NIGDY w repo** — `.env` w `.gitignore`
- WordPress dostęp przez Application Passwords (nie master password)
- YouTube data pobierane bez API key (dane publiczne)
- OAuth2 opcjonalnie dla operacji admin YouTube
- Multi-tenant: credentials per-request przez HTTPS (stateless)
- `cookies/` katalog w gitignore — nie commituj cookies YouTube

---

## 📊 Aktualny Status

| Metryka | Wartość |
|---------|-------|
| Pipeline version | v5.4 |
| VSE API | v2.0.0 ✅ LIVE |
| Site produkcyjny | https://vse.impresjapr.pl |
| Swagger UI | https://vse.impresjapr.pl/docs |
| Dashboard | ✅ Działa (2 ścieżki: Free/Pro) |
| Live posts (prawy.pl) | 6 |
| Kolejka archiwum | 213+ |
| Schema compliance | 8/10 (Google 2026) |
| LLM | Claude Sonnet (~50s/wideo) |

---

## 🗺️ Roadmap

### ✅ Faza 1 — CLI Pipeline (DONE)
- [x] Core pipeline v5.4 (VideoObject + Clip + FAQ + interactionStatistic)
- [x] VTT fetching bez API key
- [x] Video sitemap generation
- [x] Claude (Anthropic) LLM provider
- [x] inject_video + YouTube description update (OAuth)
- [x] RankMath integration

### ✅ Faza 2A — VSE API Service (DONE)
- [x] FastAPI app (api/ moduł)
- [x] PostgreSQL + plans seed (auto przy starcie)
- [x] Auth: register, login, JWT
- [x] POST /v1/generate — **OPERACYJNY**
- [x] POST /v1/inject, /v1/process, /v1/monitor/start
- [x] Next.js 14 dashboard (2 ścieżki: Free/Pro)
- [x] Deployment oracle-crimson — **LIVE**

### 🟡 Faza 2B — YouTube Unblock + E2E (IN PROGRESS)
- [ ] cookies.txt strategy — fetcher.py + docker volume
- [ ] End-to-end test z realnym video PrawyTV
- [ ] POST /v1/monitor/start — testy E2E
- [ ] deno JS runtime w api/Dockerfile (eliminuje WARNING yt-dlp)

### 🔴 Faza 3 — VSE Komercjalizacja MVP (BLOCKER)
- [ ] 🔴 Stripe checkout flow (Products + Prices + Webhooks)
- [ ] 🔴 Terms of Service + Privacy Policy (EU/RODO)
- [ ] 🟡 Email verification flow (token exists, flow TBD)
- [ ] 🟡 Google OAuth login (google_id exists, flow TBD)
- [ ] 🟡 Landing page visual polish + pricing page
- [ ] ✅ Pre-deploy backup system (VPS cron + deploy gate)
- [ ] ✅ `org_id` nullable column prep (future org layer)

### 🔵 Faza 4 — VSE Growth (po PMF validation)
- [ ] Batch processing (wiele wideo naraz)
- [ ] SEO Scoring dashboard
- [ ] Channel Monitor E2E
- [ ] API keys for Pro/Agency (model exists)

### 🟣 Faza 5 — Integracja z ekosystemem PressAI (po komercjalizacji PressAI)
- [ ] Opcjonalna user federation VSE↔PressAI
- [ ] S2S user-scoped izolacja (competing tenants scenario)
- [ ] Organization/Tenant layer
- [ ] WordPress plugin (pressai-video-seo) freemium
- [ ] Bundle pricing VSE+PressAI

---

*Część ekosystemu [ImpresjaAI](https://impresjapr.pl) — platforma PressAI.*
*Roadmap zaktualizowany: 30.06.2026 [arch-analyst-01]*
