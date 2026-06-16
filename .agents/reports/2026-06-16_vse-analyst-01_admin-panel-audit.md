# Diagnoza Admin Panel — vse-analyst-01

**Data:** 2026-06-16  
**Callsign:** vse-analyst-01  
**Dispatch from:** Supervisor 03

---

## Status

| Element | Status | Szczegóły |
|---------|--------|-----------|
| `web/src/app/admin/page.tsx` | ✅ W REPO | 24.7 KB, pełny UI z tabelą użytkowników, modalem zmiany planu, statystykami |
| `api/routers/admin.py` | ✅ W REPO | 4 endpointy: GET /users, GET /users/{id}, PATCH /users/{id}/plan, GET /stats |
| `web/src/middleware.ts` | ✅ W REPO | Chroni /admin, wymaga is_admin=true lub plan=agency |
| `api/main.py` | ✅ ROUTER ZAREJESTROWANY | `app.include_router(admin_router)` — obecny |
| `api/auth.py` | ✅ `get_current_admin` | Dependency sprawdza `user.is_admin`, rzuca 403 jeśli false |
| NextAuth `route.ts` | ✅ `is_admin` W TOKEN | `fetchUserProfile` pobiera is_admin, session callback eksponuje do klienta |
| Admin w Docker build | ✅ ZBUDOWANY | `/app/.next/server/app/admin/page.js` + chunk w static |
| `is_admin` w DB | ✅ `tobroz@gmail.com` = TRUE | plan_id=agency, is_admin=t |
| `/admin` (GET, no cookie) | ✅ **307** → /login | Middleware działa poprawnie |
| `/admin` (GET, follow redirects) | ✅ **200** | Strona się renderuje |
| `/v1/admin/users` (direct) | ✅ **401** | Endpoint istnieje, wymaga auth |
| `/api/v1/admin/users` (via nginx) | ❌ **404** | **ROOT CAUSE** — nginx nie stripuje /api/ prefix |

---

## Root Cause

### 🔴 Problem #1: Nginx `/api/` nie stripuje prefixu → wszystkie frontend API calls zwracają 404

**CO:** Frontend (`admin/page.tsx`) konstruuje URL-e jako:
```
${NEXT_PUBLIC_API_URL}/v1/admin/users
= https://vse.impresjapr.pl/api/v1/admin/users
```

**PO CO to problem:** Nginx blok `location /api/` proxuje do `http://172.17.0.1:8085` **bez trailing slash**, więc pełny URI jest przekazywany do FastAPI jako `/api/v1/admin/users`. FastAPI rejestruje endpointy pod `/v1/admin/*`, NIE pod `/api/v1/admin/*` — stąd 404.

**JAK zweryfikowano:**
```
Direct call:  curl http://172.17.0.1:8085/v1/admin/users   → 401 (endpoint istnieje)
Via nginx:    curl http://172.17.0.1:8085/api/v1/admin/users → 404 (nie istnieje)
```

**UWAGA:** Ten problem dotyczy WSZYSTKICH API calls z frontendu, nie tylko admina!
```
https://vse.impresjapr.pl/api/v1/users/me    → 404
https://vse.impresjapr.pl/api/v1/generate     → 404
```

Przypadkowo działa login i sesje, bo:
- NextAuth `fetchUserProfile` używa `BACKEND_URL=http://vse-api:8085` (wewnętrzny Docker, bez /api/)
- NextAuth `authorize` też używa `BACKEND_URL` bezpośrednio
- Dashboard/admin page.tsx używa `NEXT_PUBLIC_API_URL` (kliencki, przez nginx) → 404

**Konfiguracja nginx:**
```nginx
location /api/ {
    proxy_pass http://172.17.0.1:8085;    # ← BEZ trailing slash!
    # ...
}
```
Powinno być:
```nginx
location /api/ {
    proxy_pass http://172.17.0.1:8085/;   # ← Z trailing slash (stripuje /api/)
    # ...
}
```

### ⚠️ Problem #2: Potencjalny — dashboard page.tsx może NIE używać NEXT_PUBLIC_API_URL

Dashboard (`dashboard/page.tsx`) może mieć inny pattern wywoływania API niż admin panel. Jeśli dashboard działa mimo 404 na /api/v1/*, to prawdopodobnie robi fetch przez Next.js API route (server-side), a nie bezpośrednio do backendu.

Admin panel natomiast jawnie wywołuje:
```typescript
const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
fetch(`${apiUrl}/v1/admin/users?limit=500`, { headers })
fetch(`${apiUrl}/v1/admin/stats`, { headers })
```

---

## Wymagane Działania

### Fix #1 (KRYTYCZNY): Nginx — dodaj trailing slash do proxy_pass

**Plik:** `/home/ubuntu/crimson-void/nginx/default.conf`  
**Zmiana:** W bloku `location /api/` dla `vse.impresjapr.pl`:
```diff
 location /api/ {
-    proxy_pass http://172.17.0.1:8085;
+    proxy_pass http://172.17.0.1:8085/;
     # reszta bez zmian
 }
```

Trailing slash w `proxy_pass` powoduje że nginx stripuje pasujący prefix (`/api/`) z URI przed przekazaniem do upstream. Więc `/api/v1/admin/users` staje się `/v1/admin/users`.

Po zmianie: `docker exec crimson-nginx nginx -s reload`

### Fix #2 (ALTERNATYWNY): Zmień NEXT_PUBLIC_API_URL

Jeśli Fix #1 jest zbyt ryzykowny (dotknie wszystkie /api/* ścieżki), alternatywnie zmień env w docker-compose:
```diff
- NEXT_PUBLIC_API_URL=https://vse.impresjapr.pl/api
+ NEXT_PUBLIC_API_URL=https://vse.impresjapr.pl
```

Then admin page calls `https://vse.impresjapr.pl/v1/admin/users` → nginx location `/v1/` → FastAPI → 401 (poprawne).

**⚠️ UWAGA:** Ta zmiana wymaga przebudowy `vse-web` kontenera (NEXT_PUBLIC env vars są bake'd at build time w Next.js).

### Fix #3 (OPCJONALNY): Dashboard verification

Po naprawieniu #1 lub #2, zweryfikuj że dashboard `/dashboard` poprawnie wyświetla plan, usage, i generate form. Jeśli dashboard nie używa NEXT_PUBLIC_API_URL lecz ma inny mechanizm — może on nie być dotknięty tym bugiem, ale też może nie korzystać z naprawy.

---

## Podsumowanie Root Cause (jedna linia)

**Admin panel działa na poziomie kodu, ale nginx nie stripuje `/api/` prefixu z URL-i, przez co wszystkie client-side fetch-e do backendu (w tym admin panel) trafiają na ścieżkę `/api/v1/*` której FastAPI nie rozpoznaje → 404.**

---

## Weryfikacja Środowiskowa

| Element | Wartość |
|---------|---------|
| Docker containers | vse-api (Up 7s), vse-web (Up ~1h), vse-postgres (healthy) |
| DB user tobroz@gmail.com | plan_id=agency, is_admin=true |
| NEXT_PUBLIC_API_URL | `https://vse.impresjapr.pl/api` |
| BACKEND_URL (internal) | `http://vse-api:8085` |
| NEXTAUTH_URL | `https://vse.impresjapr.pl` |
| Google OAuth | Aktywny — token-exchange 200 OK |

---

*vse-analyst-01 | video-seo-engine | 2026-06-16 19:28 — raport kompletny*
