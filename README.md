# PressAI Video SEO Engine

> **Automated video content optimization pipeline** — from YouTube channel to SEO-ready WordPress article in minutes.

[![Status](https://img.shields.io/badge/status-active%20pipeline-brightgreen)](https://prawy.pl)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-proprietary-red)](LICENSE)

---

## 🎯 What It Does

PressAI Video SEO Engine automatically transforms YouTube video content into fully optimized WordPress articles with structured data markup. The pipeline covers two core workflows:

- **Channel Monitor (MODE A)** — watches a YouTube channel; when a new video appears, automatically creates a draft WordPress post with full SEO markup
- **Portal Scanner (MODE B)** — scans an existing WordPress portal, finds all embedded YouTube videos, and enriches them with VideoObject schema, chapters, FAQ, and video sitemap entries

**Live performance benchmark (prawy.pl, May 2026):**
- Score: **8/10** vs TVP Info **3/10**, wPolityce **2/10**
- 6 posts fully processed, **213+ in queue**

---

## ✨ Key Features

- **VideoObject Schema (JSON-LD)** — full 2026 Google specification compliance (duration, interactionStatistic, viewCount, embedUrl)
- **AI-generated chapters** — Gemini/Claude API creates timestamped `Clip` entries from transcript
- **AI-generated FAQ** — `FAQPage` schema from transcript content
- **VTT transcript fetching** — no YouTube API key required (`youtube-transcript-api` + `yt-dlp`)
- **Video Sitemap generation** — supplementary XML covering all portal videos (beyond RankMath's auto-detection)
- **WordPress REST API injection** — atomic, safe post updates with rollback capability
- **Multi-tenant API** — single VSE service handles multiple portals (Phase 2)
- **Multi-portal support** — configurable via `.env` (prawy.pl, Kurier365, BiznesCiti, ...)

---

## 🏗️ Architecture

```
YouTube Channel / Portal
        │
        ▼
  [fetcher.py]  ←── youtube-transcript-api + yt-dlp (no API key)
  VTT + metadata JSON
        │
        ▼
  [matcher.py]  ←── WordPress REST API → match posts to YouTube IDs
        │
        ▼
  [generator.py] ←── Gemini/Claude API → VideoObject + Clip + FAQ schema
        │
        ▼
  [injector.py]  ←── WordPress REST API → inject JSON-LD to post
        │
        ▼
  [sitemap.py]   ←── generate video-sitemap-*.xml
        │
        ▼
  [vse-api]      ←── FastAPI :8085 (Phase 2 — multi-tenant service)
```

### Distribution Layers

| Layer | Description | Status |
|-------|-------------|--------|
| **Standalone CLI** | Direct Python CLI for power-users & agencies | ✅ Active |
| **VSE API (FastAPI)** | Multi-tenant REST service on oracle-crimson :8085 | 🟡 Phase 2 |
| **SaaS Module** | Integration with press.impresjapr.pl via REST API | 🔵 Planned |
| **WordPress Plugin** | `pressai-video-seo` freemium plugin | 🔵 Planned |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Core pipeline | Python 3.10+ |
| AI generation | Google Gemini API + Claude (Anthropic) |
| YouTube data | `youtube-transcript-api` 1.2.4+ + `yt-dlp` |
| WordPress | REST API v2 (Application Passwords) |
| Schema | JSON-LD, Schema.org VideoObject / Clip / FAQPage |
| Sitemap | Custom XML (Google Video Sitemap 1.1) |
| Web API | FastAPI + uvicorn (Phase 2) |

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your credentials

# Fetch video data
python -m cli.main fetch --video https://youtube.com/watch?v=VIDEO_ID

# Generate SEO schema
python -m cli.main generate --video VIDEO_ID

# Inject to WordPress
python -m cli.main inject --post-id WP_POST_ID --video VIDEO_ID

# Generate video sitemap
python -m cli.main sitemap --output video-sitemap.xml

# [Phase 2] Run VSE API
docker compose -f docker-compose.vse.yml up -d
curl http://localhost:8085/health
```

---

## 📁 Project Structure

```
video-seo-engine/
├── api/                    # [Phase 2] FastAPI multi-tenant service
│   ├── main.py             # FastAPI app entry
│   ├── routers/            # /v1/process, /v1/generate, /v1/inject, ...
│   ├── models/             # Pydantic request/response schemas
│   └── services/           # Pipeline orchestration
├── core/
│   ├── fetcher.py          # YouTube data: transcripts + metadata (no API key)
│   ├── matcher.py          # Match WP posts to YouTube IDs
│   ├── generator.py        # AI schema generation (VideoObject, Clip, FAQ)
│   ├── injector.py         # WordPress REST API injection
│   ├── sitemap.py          # Video sitemap XML generation
│   ├── monitor.py          # Channel Monitor [Phase 2]
│   └── yt_admin.py         # YouTube admin ops [Phase 2]
├── cli/
│   └── main.py             # Unified CLI entry point
├── Dockerfile.api          # [Phase 2] Docker build for VSE API
├── docker-compose.vse.yml  # [Phase 2] Standalone compose
├── docs/
│   ├── ARCHITECTURE.md
│   ├── USAGE.md
│   └── CHANGELOG.md
├── .agents/                # Agent workspace (heartbeat, tasks, reports)
├── .env.example            # Credential template (CLI)
├── .env.api.example        # [Phase 2] Credential template (API)
├── requirements.txt
└── README.md
```

---

## 🔐 Security

- **Credentials NEVER in repo** — `.env` is gitignored
- WordPress access via Application Passwords (not master password)
- YouTube data fetched without API key (public data only)
- Optional OAuth2 for YouTube admin operations (update descriptions, chapters)
- Multi-tenant: credentials passed per-request via HTTPS (stateless, no DB storage on MVP)

---

## 📊 Current Status

| Metric | Value |
|--------|-------|
| Pipeline version | v5.4 |
| Live posts (prawy.pl) | 6 |
| Queue (archive) | 213+ |
| Schema compliance | 8/10 (Google 2026) |
| Active portals | prawy.pl |
| LLM providers | Gemini + Claude (Sonnet) |

---

## 🗺️ Roadmap

### ✅ Faza 1 — CLI Pipeline (DONE)
- [x] Core pipeline v5.4 (VideoObject + Clip + FAQ + interactionStatistic)
- [x] VTT fetching without API key
- [x] Video sitemap generation
- [x] Claude (Anthropic) LLM provider
- [x] yt_title formats A/B/C/D (CTR optimization)
- [x] inject_video + YouTube description update (OAuth)
- [x] RankMath integration

### 🟡 Faza 2 — VSE API Service (IN PROGRESS)
- [ ] FastAPI app structure (api/ module)
- [ ] Pydantic models — ProcessRequest/Response, SiteConfig
- [ ] POST /v1/process — full pipeline endpoint
- [ ] POST /v1/generate — schema-only endpoint
- [ ] POST /v1/inject — inject-only endpoint
- [ ] GET /health — health check
- [ ] Dockerfile.api + docker-compose.vse.yml
- [ ] Deployment oracle-crimson :8085
- [ ] POST /v1/monitor/start — Channel Monitor background task
- [ ] POST /v1/sitemap

### 🔵 Faza 3 — SaaS & Plugin (PLANNED)
- [ ] SaaS auth (API key per-site, crimson-backend integration)
- [ ] nginx proxy route for vse-api
- [ ] press.impresjapr.pl integration
- [ ] WordPress plugin (pressai-video-seo) freemium
- [ ] Billing / usage tracking

---

*Part of the [ImpresjaAI](https://impresjapr.pl) ecosystem — PressAI platform.*
