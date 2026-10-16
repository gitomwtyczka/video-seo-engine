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

## 🗺️ Roadmap (Master Roadmap v2.0 — 16.10.2026)

> Pełny dokument strategiczny i techniczny: **[ROADMAP.md](ROADMAP.md)**

### 📊 Zatwierdzone Pakiety i Twarde Limity (Brak strat na tokenach)
- **FREE:** 0 zł | 5 filmów/mies. | 0 Claude (tylko Gemini Flash 0,016 zł) | 1 portal WP | CAC = 0,08 zł
- **STARTER:** 49 zł brutto (38,10 zł netto) | 50 filmów/mies. | 0 Claude | 3 portale | Marża: **+37,30 zł (97,9% 🟢)**
- **PRO:** 149 zł brutto (117,90 zł netto) | 250 filmów/mies. | do 30 Claude Sonnet | 10 portali | Marża: **+91,88 zł (77,9% 🟢)**
- **AGENCY:** 499 zł brutto (397,20 zł netto) | 1 000 filmów/mies. | do 150 Claude Sonnet | 50 portali | Marża: **+271,10 zł (68,3% 🟢)**

---

### ✅ FAZA 1 & 2A — CLI Pipeline, API & Dashboard (ZREALIZOWANE)
- [x] Core pipeline v5.4 (`VideoObject` + `Clip` + `FAQPage` + artykuł HTML + integracja RankMath)
- [x] VTT fetching z fallbackiem (`youtube-transcript-api` → `yt-dlp` → Graceful Degradation bez napisów)
- [x] `VSELocalRunner` (usługa Windows omijająca blokady IP datacenter + fix ucinania transkrypcji)
- [x] FastAPI app + PostgreSQL + Auth JWT + Next.js 14 Dashboard + Admin Panel wdrożone na `vse.impresjapr.pl`
- [x] YouTube OAuth2: podpinanie kanałów, publikacja opisów M1-M8 (`build_yt_description`), tytuły `yt_title`, stopka `footer_text`

---

### 🟡 FAZA 2B — Stabilizacja Kodu, Naprawa Bomb P0 i Porządek w Git (W TOKU / PRZYGOTOWANE W ETAPIE 1)
- [x] **Modularność Dashboardu:** Podział monolitu `dashboard-inner.tsx` na komponenty (`types.ts`, `utils.ts`, `YouTubePublishModal` obsługa `overrideDescription`).
- [x] **Hotfix P0 #1 (White-Label):** Neutralizacja promptu w `core/generator.py` (usunięcie tożsamości `prawy.pl` na rzecz dynamicznej nazwy portalu).
- [x] **Hotfix P0 #2 (SaaS Transcript 403):** Przekazywanie `user_id` do `_create_transcript_job()` i poprawka uprawnień w `api/routers/jobs.py`.
- [x] **Hotfix P0 #3 (Twarde Limity & Model Tiering):** Wymuszenie Gemini Flash w planach Free/Starter, blokada `monthly_quota`, auto-fallback `Claude → Gemini` przy 429/529.
- [x] **Precyzyjne Logowanie Tokenów & Kosztów:** Rejestracja `input_tokens`, `output_tokens`, `estimated_cost_usd` w `UsageLog` + migracja bazy `ALTER TABLE`.
- [x] **Lokalny Punkt One-Click Revert:** Branch `backup/pre-v2-commercial-20261016` oraz `backup_pre_v2_commercial_diff.patch`.
- [ ] **Wdrożenie Produkcyjne Etapu 1:** Przegląd QA, merge do `main`, backup VPS (`backup_pre_deploy.sh`) i deploy na `vse.impresjapr.pl`.

---

### 💰 FAZA 3 — Domknięcie Komercjalizacji Portalu VSE i Płatności Stripe
- [x] Ujednolicenie cennika w Landing Page, `/cennik` oraz `_seed_plans()` z ID Stripe.
- [ ] Pełna integracja Stripe Checkout & Webhooków (`subscription_update`, proration, kupony promocyjne).
- [ ] Wymogi prawne: `/regulamin` (ToS) i `/polityka-prywatnosci` (RODO).
- [ ] Weryfikacja e-mail oraz logowanie Google OAuth.

---

### 🔌 FAZA 4 — Mikro-Wtyczka WordPress `vse-video-seo` (Lead Magnet → Portal)
- [ ] Backend VSE: Tabela `api_keys`, walidacja `X-VSE-Key` + `X-Site-URL` i endpointy `/v1/plugin/*`.
- [ ] Wtyczka WP (`vse-video-seo` na bazie 80% kodu `pressai-wp`):
  - Clean Head Injection: wstrzykiwanie JSON-LD w `wp_head` przez pole `_vse_schema_json` (zero konfliktów z `wp_kses_post`).
  - Uniwersalny adapter SEO dla RankMath, Yoast SEO i SEOPress.
  - Lekki asset `assets/js/player.js` do obsługi rozdziałów wideo.
- [ ] Gutenberg Sidebar UI: Wklejenie linku YT → podgląd Rich Result + Video SEO Score (Aha-moment) + upsell do planów Pro.

---

### 🎬 FAZA 5 — YouTube OAuth Captions & Zaawansowane SEO
- [ ] **5.1. YouTube Data API v3 OAuth Captions (`captions.download`):** Przekazywanie tokena kanału do `fetch_transcript_api_v3()` — pobieranie napisów na VPS bez blokad IP oraz obsługa filmów **Prywatnych i Zaplanowanych**.
- [ ] **5.2. Ręczny upload pliku `.vtt` / `.srt`** w dashboardzie (dla nagrań bez automatycznych napisów).
- [ ] **5.3. Moduł M4B:** Cytaty z klikalnymi deep-linkami czasowymi.
- [ ] **5.4. Przeglądarka kanału (`/channels`) i Channel Monitor E2E.**

---

### 🌐 FAZA 6 — Integracja Ekosystemu (VSE + PressAI + SocialPulse)
- [ ] Wspólny standard kluczy API (`X-VSE-Key` / `X-PressAI-Key`).
- [ ] Pakiet łączony (Bundle Pricing) oraz izolacja multi-tenant (`org_id`).

---

*Część ekosystemu [ImpresjaAI](https://impresjapr.pl) — platforma PressAI.*  
*Roadmap zaktualizowany: 16.10.2026 [Supervisor 01] — Master Roadmap v2.0*
