# Raport: vse-strateg-01 — Faza 2 Plan
# Data: 2026-06-14
# Autor: vse-strateg-01

---

## 📊 Stan po sesji (audit)

### oracle-crimson — stan faktyczny

| Kontener | Status | Port |
|----------|--------|------|
| `vse-api` | ✅ Up 11h (healthy) | :8085 |
| `crimson-backend` | ✅ Up 2 tyg | :8001 |
| `prawy-wordpress` | ✅ Up 3 tyg | :8081 |
| `crimson-nginx` | ✅ Up 10h | :80/443 |
| Disk | 156G/194G (81%) | — |

### VSE API v2.0.0 — LIVE
- Health: `{"status":"ok","version":"2.0.0","llm_default":"claude"}`
- Endpointy: `/v1/process`, `/v1/generate`, `/v1/inject`, `/v1/monitor/start`, `/v1/sitemap`
- Swagger: http://147.224.162.100:8085/docs
- Logi: healthcheck co ~30s z crimson-nginx (aktywny polling)

### Co zrobił vse-dev-01 (sesja 2026-06-13)
- FastAPI struktura 13 plików — commit `d7a86e79`
- requirements.txt fix — commit `deb1e6da`
- Dockerfile.api fix — commit `9b5cac74`
- Git clone + .env + docker up na VPS — health OK
- Dual-write report — commit `5eb06565` (repo) + `32892da0` (sonic-void)

---

## 🚨 Bloker: YouTube IP Blocking

Oracle Cloud IP flagowany przez YouTube. `yt-dlp` i `youtube-transcript-api` nie działają na VPS.
Pipeline lokalny (Windows) — OK. API na VPS — YT fetch = fail.

## ✅ Decyzja Strategiczna (zatwierdzona przez Usera 2026-06-14)

**Opcja A** (krótkoterm): `cookies.txt` pass-through via `yt-dlp --cookies`
- Docker volume mount: `/home/ubuntu/video-seo-engine/cookies:/app/cookies:ro`
- Env var: `YT_COOKIES_PATH=/app/cookies/youtube_cookies.txt`
- User eksportuje cookies z Chrome (rozszerzenie "Get cookies.txt LOCALLY")

**Opcja C** (longterm / SaaS-ready): architektura hybrydowa
- Lokalny klient fetchuje transcript → pushuje przez `POST /v1/generate` z `raw_transcript` + `raw_metadata`
- VSE API = orchestrator AI + injector
- Wymaga rozszerzenia `ProcessRequest` o opcjonalne pola pre-fetched data

---

## 📝 Co zrobiłem (strateg)

1. ✅ Heartbeat zaktualizowany — commit `d99acb1a`
2. ✅ Dispatch v2 dla vse-dev-01 — commit `2511fe62` (Opcja A+C)
3. ✅ README roadmap zaktualizowany — commit `b8513aee` (Faza 2A DONE, 2B IN PROGRESS)

---

## 📋 Pending (czeka na vse-dev-01)

- [ ] cookies.txt implementation w fetcher.py + docker-compose
- [ ] docs/YOUTUBE_COOKIES.md
- [ ] raw_transcript/raw_metadata w ProcessRequest (Opcja C)
- [ ] E2E test /v1/generate z realnym video
- [ ] E2E test /v1/process z prawy.pl post_id

---

*vse-strateg-01 | video-seo-engine | 2026-06-14 10:42*
