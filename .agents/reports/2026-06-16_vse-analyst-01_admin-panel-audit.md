# Diagnoza Admin Panel

**Analityk:** vse-analyst-01  
**Data:** 2026-06-16  
**Dispatch:** Supervisor 03 — Admin Panel Audit

---

## Status

| Element | Status | Szczegóły |
|---|---|---|
| Kod w repo | ✅ TAK | `web/src/app/admin/page.tsx` (24.6 KB), `api/routers/admin.py` (8.1 KB), `web/src/middleware.ts`, `api/main.py` (admin_router zarejestrowany) |
| Kod w kontenerze VPS | ✅ TAK | `/app/.next/server/app/admin/page.js` (18.9 KB) w `vse-web` |
| Endpoint /v1/admin/users (bezpośredni) | ✅ 401 | Poprawna odpowiedź bez tokenu |
| Endpoint /api/v1/admin/users (przez NEXT_PUBLIC_API_URL) | ❌ 404 | **To jest root cause** |
| Strona /admin (HTML) | ✅ 307→login | Middleware działa, redirect do /login poprawny |
| is_admin w DB | ✅ TAK | `tobroz@gmail.com`: plan=agency, is_admin=true, is_active=true |
| is_admin w JWT/session | ✅ TAK | route.ts: fetchUserProfile() pobiera is_admin, session callback eksponuje do klienta |
| get_current_admin dependency | ✅ OK | auth.py: sprawdza `current_user.is_admin`, zwraca 403 jeśli false |
| Nginx routing | ✅ OK | `/admin` → Next.js (3001), `/v1/` → FastAPI (8085), `/api/` → FastAPI (8085) |

---

## Root Cause

### Zła ścieżka API w client-side fetch (NEXT_PUBLIC_API_URL mismatch)

**CO się dzieje:**
- Admin page (`page.tsx`) robi fetch: `${NEXT_PUBLIC_API_URL}/v1/admin/users`
- `NEXT_PUBLIC_API_URL` w kontenerze = `https://vse.impresjapr.pl/api`
- Wynikowa ścieżka: `https://vse.impresjapr.pl/api/v1/admin/users`
- FastAPI NIE ma routingu na `/api/v1/admin/users` — ma tylko `/v1/admin/users`
- Nginx `location /api/` proxy do FastAPI ale **nie stripuje** prefixu `/api/`
- **Wynik: 404 Not Found**

**PO CO to ważne:**
Strona `/admin` ładuje się poprawnie (HTML z Next.js), middleware działa (redirect niezalogowanych do /login). Ale po zalogowaniu panel pokazuje spinner/error bo JavaScript fetch leci na nieistniejącą ścieżkę `/api/v1/admin/users` zamiast `/v1/admin/users`.

**Dowód:**
```bash
# Poprawna ścieżka — działa:
curl https://vse.impresjapr.pl/v1/admin/users → 401 ✅

# Ścieżka z admin page — nie działa:
curl https://vse.impresjapr.pl/api/v1/admin/users → 404 ❌
```

### Ten sam bug potencjalnie dotyczy WSZYSTKICH client-side fetch

Każdy komponent który robi `fetch(${NEXT_PUBLIC_API_URL}/v1/...)` ma ten sam problem.
Dashboard (`/dashboard`) prawdopodobnie też jest dotknięty — jeśli działa, to dlatego że używa innego wzorca fetch lub server-side `BACKEND_URL` zamiast `NEXT_PUBLIC_API_URL`.

---

## Wymagane działania

### Fix 1: NEXT_PUBLIC_API_URL (KRYTYCZNY)

**Opcja A (rekomendowana):** Zmień `NEXT_PUBLIC_API_URL` na pustego stringa `""` lub `https://vse.impresjapr.pl`
→ fetch pójdzie na `/v1/admin/users` (relative lub bez `/api` prefix)
→ Nginx `location /v1/` poprawnie proxy do FastAPI

**Opcja B:** Dodaj rewrite w nginx strip `/api` prefix:
```nginx
location /api/ {
    rewrite ^/api(/.*)$ $1 break;
    proxy_pass http://172.17.0.1:8085;
    ...
}
```
→ Bardziej inwazyjne, może złamać inne endpointy

### Fix 2: Rebuild vse-web po zmianie env (WYMAGANY)

UWAGA: `NEXT_PUBLIC_*` zmienne są **wbudowane w build** (baked at build time w Next.js).
Zmiana env w docker-compose NIE wystarczy — trzeba `docker compose up -d --build vse-web`.

### Fix 3: Weryfikacja dashboard

Po fixie NEXT_PUBLIC_API_URL sprawdzić czy dashboard page.tsx też używa tego env.
Jeśli tak — ten sam bug dotyczy dashboardu.

---

## Podsumowanie

Admin panel NIE zniknął z kodu ani z VPS. Wszystkie pliki są w repo i w kontenerze.
Problem jest w runtime: JavaScript wywołuje API na złej ścieżce przez niepoprawny `NEXT_PUBLIC_API_URL`.
Fix to zmiana jednej zmiennej env + rebuild kontenera web.

---

*vse-analyst-01 | video-seo-engine | 2026-06-16 19:36*