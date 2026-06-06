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
- **AI-generated chapters** — Gemini API creates timestamped `Clip` entries from transcript
- **AI-generated FAQ** — `FAQPage` schema from transcript content
- **VTT transcript fetching** — no YouTube API key required (`youtube-transcript-api` + `yt-dlp`)
- **Video Sitemap generation** — supplementary XML covering all portal videos (beyond RankMath's auto-detection)
- **WordPress REST API injection** — atomic, safe post updates with rollback capability
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
  [generator.py] ←── Gemini API → VideoObject + Clip + FAQ schema
        │
        ▼
  [injector.py]  ←── WordPress REST API → inject JSON-LD to post
        │
        ▼
  [sitemap.py]   ←── generate video-sitemap-*.xml
```

### Distribution Layers

| Layer | Description | Status |
|-------|-------------|--------|
| **Standalone CLI** | Direct Python CLI for power-users & agencies | ✅ Active |
| **SaaS Module** | Integration with press.impresjapr.pl via REST API | 🔵 Planned |
| **WordPress Plugin** | `pressai-video-seo` freemium plugin | 🔵 Planned |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Core pipeline | Python 3.10+ |
| AI generation | Google Gemini API |
| YouTube data | `youtube-transcript-api` 1.2.4+ + `yt-dlp` |
| WordPress | REST API v2 (Application Passwords) |
| Schema | JSON-LD, Schema.org VideoObject / Clip / FAQPage |
| Sitemap | Custom XML (Google Video Sitemap 1.1) |
| Web App (future) | FastAPI |

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
```

---

## 📁 Project Structure

```
video-seo-engine/
├── core/
│   ├── fetcher.py      # YouTube data: transcripts + metadata (no API key)
│   ├── matcher.py      # Match WP posts to YouTube IDs
│   ├── generator.py    # AI schema generation (VideoObject, Clip, FAQ)
│   ├── injector.py     # WordPress REST API injection
│   ├── sitemap.py      # Video sitemap XML generation
│   ├── monitor.py      # Channel Monitor [Phase 2]
│   └── yt_admin.py     # YouTube admin ops [Phase 2]
├── cli/
│   └── main.py         # Unified CLI entry point
├── docs/
│   ├── ARCHITECTURE.md
│   ├── USAGE.md
│   └── CHANGELOG.md
├── .agents/            # Agent workspace (heartbeat, tasks, reports)
├── .env.example        # Credential template
├── requirements.txt
└── README.md
```

---

## 🔐 Security

- **Credentials NEVER in repo** — `.env` is gitignored
- WordPress access via Application Passwords (not master password)
- YouTube data fetched without API key (public data only)
- Optional OAuth2 for YouTube admin operations (update descriptions, chapters)

---

## 📊 Current Status

| Metric | Value |
|--------|-------|
| Pipeline version | v5.3 |
| Live posts (prawy.pl) | 6 |
| Queue (archive) | 213+ |
| Schema compliance | 8/10 (Google 2026) |
| Active portals | prawy.pl |

---

## 🗺️ Roadmap

- [x] Core pipeline v5.3 (VideoObject + Clip + FAQ + interactionStatistic)
- [x] VTT fetching without API key
- [x] Video sitemap generation
- [ ] Channel Monitor (automated new-video detection)
- [ ] Portal Scanner (bulk portal audit)
- [ ] FastAPI web interface
- [ ] SaaS module integration
- [ ] WordPress plugin (pressai-video-seo)

---

*Part of the [ImpresjaAI](https://impresjapr.pl) ecosystem — PressAI platform.*
