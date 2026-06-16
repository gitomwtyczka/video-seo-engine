# Raport: NOT-FOUND-FIX + Plan Upgrade

**Agent:** vse-dev-05  
**Data:** 2026-06-16  
**Dispatch:** DISPATCH-VSE-DEV-05-20260616-NOT-FOUND-FIX  
**Status:** ✅ DONE

---

## Zadanie 1 — Naprawa „Not Found” (P0) ✅

### Root Cause

Frontend (`dashboard/page.tsx`) używał `process.env.NEXT_PUBLIC_API_URL || '/api'` jako prefix URL.

**Przepływ błędu:**
```
Frontend → fetch('/api/v1/generate')
nginx location /api/ → proxy_pass http://172.17.0.1:8085 (zachowuje pełną ścieżkę!)
FastAPI widzi: GET /api/v1/generate → 404 (endpoint to /v1/generate)
```

**Poprawna ścieżka:**
```
Frontend → fetch('/v1/generate')
nginx location /v1/ → proxy_pass http://172.17.0.1:8085
FastAPI widzi: GET /v1/generate → 200 OK
```

### Fix

**Commit:** `2cb78891b812f782a0eb6aef7751378d256fc485`  
**Plik:** `web/src/app/dashboard/page.tsx`  
**Zmiana:** `|| '/api'` → `|| ''` w 3 miejscach:
- `handleGenerate`: `/v1/generate`
- `PublishSection.handlePublish`: `/v1/inject`
- `fetchProfile`: `/v1/users/me`

### Weryfikacja

- `nginx/default.conf` z crimson-void przeanalizowany — kolejność bloków poprawna (`/api/auth/` przed `/api/`)
- `location /v1/` istnieje i routuje do FastAPI 8085 ✅
- Frontend po rebuildie: Next.js 14 `Ready in 73ms` ✅
- `https://vse.impresjapr.pl/health` → `{"status":"ok","version":"2.0.0"}` ✅
- Dashboard: `/dashboard` → redirect do `/login` (auth guard) ✅

### Deploy wykonany

```bash
git pull origin main  # wciągnął commit 2cb7889
docker compose -f docker-compose.vse.yml up -d --no-deps --build vse-web
# Container vse-web Started ✅
```

---

## Zadanie 2 — Upgrade planu tobroz@gmail.com (P1) ✅

### Backup przed zmianą

```
id                                   | email            | plan_id
4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | tobroz@gmail.com | free
```

### Zmiana

```sql
UPDATE users SET plan_id = 'agency' WHERE email = 'tobroz@gmail.com';
```

### Weryfikacja

```
id                                   | email            | plan_id
4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | tobroz@gmail.com | agency
```

**Plan `agency`:** monthly_quota=9999, wp_sites_limit=999, api_access=true — najwyższy dostępny plan.

---

## Commity tej sesji

| SHA | Plik | Co |
|---|---|---|
| `2cb7889` | `web/src/app/dashboard/page.tsx` | Naprawa URL routing `/api/v1/*` → `/v1/*` |
| `acb3bd5` | `.agents/heartbeat.json` | Heartbeat onset |

## Uwagi dla następnego agenta

- nginx/default.conf jest poprawny — nie wymaga zmian
- DB credentials: user=`vse`, db=`vse`, container=`vse-postgres`
- `POSTGRES_USER=vse` (nie `postgres`!) — częsty gotcha
- Wszystkie 3 kontenery VSE (api, web, postgres) są UP

---

*vse-dev-05 | video-seo-engine | 2026-06-16 14:47*
