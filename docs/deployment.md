# Deployment Runbook — Video SEO Engine

> **CO:** Kompletna instrukcja deploymentu VSE na VPS Oracle ARM — od zera do produkcji.
>
> **PO CO:** Bez tego dokumentu każdy deploy wymaga rekonstrukcji procedury z kodu i historii sesji. Ten runbook eliminuje guessing i chroni przed pułapkami, które już nas kosztowały czas.
>
> **JAK:** Czytaj GOTCHA sekcję PRZED każdym deployem. Postępuj krok po kroku.

---

## ⚠️ GOTCHA — Pułapki Operacyjne (czytaj PRZED deployem)

Zanotowane po sesjach 2026-06-14/15. Każda z tych pułapek kosztowała sesję debugowania.

### GOTCHA #1: Port binding `127.0.0.1:3001` → nginx 502

**Problem:** `docker-compose.vse.yml` z `"127.0.0.1:3001:3000"` powoduje 502 z crimson-nginx.
Nginx kontener sięga do hosta przez `172.17.0.1` — loopback binding jest dla niego niewidoczny.

**Fix:** Port `vse-web` MUSI być bindowany na `0.0.0.0`:
```yaml
# ❌ NIE:
ports:
  - "127.0.0.1:3001:3000"

# ✅ TAK:
ports:
  - "3001:3000"
```

---

### GOTCHA #2: `next.config.ts` nie działa w Next.js 14

**Problem:** Next.js 14.x nie obsługuje `next.config.ts` — crash przy starcie kontenera.

**Fix:** Zawsze używaj `next.config.mjs` (lub `.js`). Nigdy `.ts`.

---

### GOTCHA #3: Brak `postcss.config.js` → brak CSS

**Problem:** Bez `web/postcss.config.js` dyrektywy `@tailwind` w `globals.css` nie są przetwarzane.
Efekt: strona ładuje się jako surowy HTML bez żadnych stylów.

**Fix:** Plik MUSI istnieć:
```js
// web/postcss.config.js
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

---

### GOTCHA #4: `npm ci` bez `package-lock.json` → build fail

**Problem:** `Dockerfile.web` z `RUN npm ci` failuje gdy brak `package-lock.json` w repo.

**Fix:** Używaj `RUN npm install` w Dockerfile, lub wcommituj `package-lock.json`.

---

### GOTCHA #5: `COPY ... 2>/dev/null || true` w Dockerfile → checksum error

**Problem:** Docker `COPY` nie obsługuje shell syntax (`2>/dev/null || true`). Powoduje błąd checksum przy buildzie.

**Fix:** Utwórz puste katalogi z `.gitkeep` i używaj prostego `COPY src dst`:
```dockerfile
# ❌ NIE:
COPY public/ /app/public/ 2>/dev/null || true

# ✅ TAK:
COPY public/ /app/public/
# (i upewnij się że public/.gitkeep istnieje w repo)
```

---

### GOTCHA #6: `git reset --hard` niszczy lokalne zmiany na VPS

**Problem:** `git reset --hard origin/main` przywraca `docker-compose.vse.yml` z GitHub,
niszcząc ręczne poprawki zrobione bezpośrednio na VPS.

**Fix:** Zawsze commituj ostateczną wersję konfiguracji do GitHub PRZED deployem.
Nigdy nie rób ręcznych zmian na VPS bez commita.

---

### GOTCHA #7: Cloudflare cache serwuje stary 502

**Problem:** Po naprawie routingu nginx, Cloudflare może dalej serwować stary błąd 502 przez cache.

**Fix:** Po każdej zmianie nginx:
Cloudflare Dashboard → `vse.impresjapr.pl` → Caching → **Purge Everything**.

---

### GOTCHA #8: `next-auth` v4 + Next.js 14 — TypeScript type error w build

**Problem:** Route `src/app/api/auth/[...nextauth]/route.ts` nie pasuje do typów Next.js 14 App Router — build fail.

**Fix:** W `next.config.mjs` MUSZĄ być:
```js
typescript: { ignoreBuildErrors: true },
eslint: { ignoreDuringBuilds: true },
```

---

### GOTCHA #9: Next.js rewrites przechwytują NextAuth (krytyczne!)

**Problem:** Dodanie `rewrites: [{ source: '/api/:path*', destination: backend }]` w `next.config.mjs`
przechwytuje `/api/auth/*` → wysyła do FastAPI zamiast NextAuth → login przestaje działać.

**Fix:** NIE dodawaj rewrites dla `/api/*` w Next.js. Cały routing obsługuje nginx.
nginx MUSI mieć blok `location /api/auth/` PRZED `location /api/`.

---

## Deployment Runbook — krok po kroku

### Wymagania wstępne

- VPS: Oracle ARM 147.224.162.100 (Ubuntu)
- crimson-nginx jest uruchomiony (docker ps | grep crimson-nginx)
- `.env` jest na VPS w `/home/ubuntu/vse/.env`
- Docker i docker-compose zainstalowane

### Krok 1 — Przygotowanie środowiska na VPS

```bash
# Połącz się z VPS przez Wetty lub SSH
# https://95-179-201-157.sslip.io/ (auth: impresja/ImpresjaWetty2026, login: root/Ku56Pa78)

# Sprawdź czy crimson-nginx działa
docker ps | grep crimson-nginx
# Musi być "Up"

# Przejdź do katalogu VSE
cd /home/ubuntu/vse

# Sprawdź .env
cat .env | grep -E 'ANTHROPIC|JWT_SECRET|NEXTAUTH_SECRET|DATABASE_URL'
# Wszystkie muszą być ustawione
```

### Krok 2 — Pull kodu z GitHub

```bash
cd /home/ubuntu/vse
git fetch origin
git reset --hard origin/main
# ⚠️ UWAGA: niszczy lokalne zmiany! Upewnij się że wszystko jest w GitHub.
```

### Krok 3 — Build i restart kontenerów

```bash
# Zatrzymaj stare kontenery
docker-compose -f docker-compose.vse.yml down

# Zbuduj nowe obrazy (--no-cache przy problemach z cache)
docker-compose -f docker-compose.vse.yml build

# Uruchom w tle
docker-compose -f docker-compose.vse.yml up -d

# Sprawdź logi przez ~30s (inicjalizacja bazy, seed planów)
docker-compose -f docker-compose.vse.yml logs -f --tail=50
```

### Krok 4 — Weryfikacja

```bash
# Health check FastAPI
curl http://localhost:8085/health
# Oczekiwany output: {"status":"ok","version":"...","llm_default":"claude"}

# Sprawdź Next.js
curl -I http://localhost:3001
# Oczekiwany: HTTP 200

# Sprawdź przez domenę (Cloudflare)
curl -I https://vse.impresjapr.pl
# Oczekiwany: HTTP 200
curl https://vse.impresjapr.pl/api/health
# Oczekiwany: {"status":"ok"}
```

### Krok 5 — Jeśli jest błąd 502

```bash
# 1. Sprawdź czy kontenery działają
docker ps | grep vse

# 2. Sprawdź logi kontenerów
docker-compose -f docker-compose.vse.yml logs vse-web
docker-compose -f docker-compose.vse.yml logs vse-api

# 3. Sprawdź port binding (musi być 0.0.0.0)
docker ps --format "{{.Names}} {{.Ports}}"
# vse-web musi pokazać: 0.0.0.0:3001->3000/tcp

# 4. Jeśli cloudflare — puść cache:
# Cloudflare Dashboard → vse.impresjapr.pl → Caching → Purge Everything
```

---

## Konfiguracja Nginx — routing VSE

Plik: `/home/ubuntu/crimson-void/nginx/default.conf`

Dodaj/weryfikuj blok dla `vse.impresjapr.pl` (szczegóły w `docs/architecture.md` sekcja 3).

Po każdej zmianie nginx:
```bash
# Zrestartuj crimson-nginx
docker exec crimson-nginx nginx -s reload

# Lub pełny restart
docker restart crimson-nginx
```

---

## Seed Plans SQL — ręczne odtworzenie

W normalnych warunkach seed jest automatyczny (lifespan FastAPI). Jeśli baza jest czysta i seed nie zadziałał:

```bash
# Połącz z bazą
docker exec -it vse-postgres psql -U postgres -d vse

# Wstaw plany (idempotentne)
INSERT INTO plans (id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln)
VALUES
  ('free',    'Free',    10,  1, false, 0),
  ('starter', 'Starter', 50,  1, false, 49),
  ('pro',     'Pro',     200, 3, true,  149),
  ('agency',  'Agency',  0,   0, true,  399)
ON CONFLICT (id) DO NOTHING;

-- Weryfikacja
SELECT id, display_name, monthly_quota, price_pln FROM plans;
```

---

## OCI Security List — otwarte porty

WPS Oracle VM wymaga reguł w OCI Security List (nie tylko iptables):

| Port | Protokół | Opis |
|---|---|---|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (Cloudflare) |
| 443 | TCP | HTTPS (Cloudflare SSL) |
| 8085 | TCP | FastAPI — tylko dla debugu (można zamknąć po stabilizacji) |

> ⚠️ Port 3001 (Next.js) i 5434 (Postgres) nie muszą być otwarte na zewnątrz — nginx obsługuje ruch.

```bash
# Weryfikacja iptables na VPS
sudo iptables -L INPUT -n | grep -E '80|443|8085'
```

---

## Rollback

```bash
# Wróć do poprzedniego commita
git log --oneline -5  # Znajdź SHA
git reset --hard <SHA>
docker-compose -f docker-compose.vse.yml down
docker-compose -f docker-compose.vse.yml up -d --build
```

---

## Monitoring i logi

```bash
# Logi wszystkich kontenerów VSE
docker-compose -f docker-compose.vse.yml logs -f

# Logi samego API
docker-compose -f docker-compose.vse.yml logs -f vse-api

# Sprawdź użycie zasobów
docker stats

# Sprawdź dysk
df -h
```

---

*vse-architect-01 | video-seo-engine | 2026-06-15 — v1.0*
*Aktualizuj ten plik po każdym deploju — nowe gotcha dopisuj na górze listy.*
