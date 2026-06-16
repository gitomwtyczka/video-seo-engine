# Raport: ARCHITECTURE.md — Audyt i Master Dokument Architektury

**Agent:** vse-architect-01  
**Data:** 2026-06-16  
**Commit:** 90b21fe  
**Status:** DONE ✅

---

## Zadanie

Stworzenie `ARCHITECTURE.md` — master dokumentu architektury projektu `video-seo-engine`.
Dokument ma być obowiązkowym KROK 0 dla każdego workera, który dołącza do projektu.

## Co zostało zaudytowane

- `docker-compose.vse.yml` — serwisy, porty, env vars, zależności
- `api/main.py` — pełna lista endpointów, startup, plan seed
- `api/models/user.py` — ORM: User, Plan, UsageLog, ApiKey
- `api/models/job.py` — ORM: TranscriptJob
- `api/models/request.py` — Pydantic input models
- `api/models/response.py` — Pydantic response models
- `api/routers/` — wszystkie routery (9 plików)
- `api/services/pipeline.py` — logika pipeline
- `web/src/app/api/auth/[...nextauth]/route.ts` — auth flow
- `web/src/middleware.ts` — route protection
- `web/next.config.mjs` — konfiguracja Next.js
- `web/package.json` — wersje zależności
- `local-runner/` — Windows Service, konfiguracja, flow
- `.env.example` + `web/.env.example` — pełna lista zmiennych

## ARCHITECTURE.md — zawartość (14 sekcji)

1. **Stack i Wersje** — Python/FastAPI/PostgreSQL/Next.js z dokładnymi wersjami
2. **Struktura Folderów** — pełne drzewo z opisami każdego pliku
3. **Kontenery Docker** — nazwy kanoniczne, porty, kolejność startu
4. **URL Conventions** — routing nginx, co idzie gdzie, env vars
5. **Auth Flow** — Credentials i Google OAuth krok po kroku
6. **Baza Danych** — pełna schema wszystkich tabel + typy + quota defaults
7. **API Response Shapes** — GET /v1/users/me, POST /v1/generate, POST /v1/inject
8. **API Endpoints Map** — pełna tabela wszystkich endpointów
9. **Local Runner** — instalacja, konfiguracja, flow komunikacji
10. **Deployment** — od commit do live (SSH komendy)
11. **Zmienne Środowiskowe** — pełna lista z oznaczeniem wymaganych
12. **Known Gotchas** — G1-G10 (wszystkie pułapki z poprzednich sesji)
13. **Pipeline Diagram** — /v1/generate krok po kroku
14. **Instrukcja dla Workera** — 10-punktowy quick start

## Kluczowe odkrycia

- Dwa pliki next.config: `.mjs` (aktywny) i `.ts` (legacy, pozostawiony w repo)
- Nginx routing: kolejność bloków ma ZNACZENIE (auth musi być przed api)
- Local Runner: YouTube blokuje Oracle VPS IP — stąd architektura job queue
- Dashboard `NEXT_PUBLIC_API_URL` = `https://vse.impresjapr.pl/api` (z /api)
  ale wywołania: `${NEXT_PUBLIC_API_URL}/v1/*` (nie `/api/v1/*`)
- BACKEND_URL (server-side): `http://vse-api:8085` (bez /api, Docker network)

## Commit

- `90b21fe` — docs: ARCHITECTURE.md — master dokument architektury projektu
