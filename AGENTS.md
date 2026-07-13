# Video SEO Engine — Workspace Rules

> Ten plik uzupełnia `RULE[user_global]` — jest auto-injected w kontekście workspace.
> Zawiera reguły specyficzne dla projektu `video-seo-engine`.

---

## ⚡ KROK 0 — OBOWIĄZKOWY START KAŻDEJ SESJI

**Pierwsza i ostatnia linia każdej wiadomości** = callsign + vitals w jednej linii:

```
[CALLSIGN | video-seo-engine YYYY-MM-DD HH:MM] 📊 V1:0/40 🟢 V2:1str 🟢 V3:0pl 🟢 V4:stabilny V5:ok — online
```

Vitals co 3-5 kroków. Skróty: `V1:X/40` kroki | `V2:Xstr` strumienie | `V3:Xpl` pliki | `V4` pewność | `V5` recovery.

Heartbeat przy starcie (GitHub MCP):
```
mcp_github_create_or_update_file:
  owner: gitomwtyczka / repo: video-seo-engine / branch: main
  path: .agents/heartbeat.json
  content: {"callsign": "[CALLSIGN]", "status": "working", "current_task": "[OPIS]", "timestamp": "[ISO]"}
```

Pełny protokół bloku systemowego — czytaj przez GitHub MCP:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka / repo: sonic-void / branch: master
  path: .agents/protocols/dispatch-system-block.md
```

---

## ⚠️ PUŁAPKA CZYTANIA DUŻYCH PLIKÓW — OBOWIĄZKOWA PROCEDURA

> Dodane: 2026-07-13 [Supervisor 01] — na podstawie analizy architektonicznej vse-analyst

**Problem:** `dashboard-inner.tsx` ma 7865 linii (101 KB). GitHub MCP `get_file_contents` przy dużym pliku zapisuje wynik do bufora `output.txt`, a domyślny odczyt przez `view_file` bez parametrów zwraca tylko **pierwsze 800 linii**. Agent NIE dostaje błędu — widzi fragment i myśli że ma całość. To jest źródło wszystkich błędnych edycji.

### Obowiązkowy flow dla pliku > 800 linii (zwłaszcza `dashboard-inner.tsx`)

**KROK 1 — Mapowanie (grep przez SSH):**
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "grep -n 'szukana_funkcja\|szukany_komponent' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```
To da numery linii bez ładowania całego pliku.

**KROK 2 — Czytanie bloku (sed przez SSH):**
```powershell
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "sed -n '1200,1260p' /home/ubuntu/video-seo-engine/web/src/app/dashboard/dashboard-inner.tsx"
```
Czytaj tylko potrzebny fragment (±30 linii wokół celu).

**KROK 3 — Weryfikacja przed edycją:**
Przed każdą edycją potwierdź przez grep że szukany fragment istnieje i jest w oczekiwanym miejscu. Jeśli nie znajdziesz — STOP, raport do Supervisora.

### Mapa komponentów `dashboard-inner.tsx` (stan 2026-07-13)

| Komponent | Linia startowa |
|---|---|
| `CopyButton` | ~881 |
| `ResultSection` | ~1013 |
| `TabBar` (zawiera tablicę `tabs`) | ~1173 |
| `InjectModal` | ~1381 |
| `AddPortalModal` | ~3017 |
| `ManageSubscriptionLink` | ~4385 |
| `DashboardInner` (główny komponent) | ~4579 |
| `NavItem` | ~7574 |
| `WpQuickPanel` | ~7714 |

> ⚠️ Linie są przybliżone — zawsze weryfikuj przez grep przed edycją.

### Plan refactoru (średnioterminowy)
Wyciągnąć wszystkie komponenty z listy powyżej do `web/src/app/dashboard/components/`. Priorytet: `InjectModal` (~1600 linii) i `TabBar` (~200 linii). Każde wydzielenie jako osobny dispatch.

---

## 🚀 DOSTĘP DO VPS — REGUŁY PER ROLA

**Zasada generalna:** SSH via `run_command` to standardowy sposób dostępu do VPS (zgodnie z `RULE[user_global]`).

### Agenci analityczni (`vse-analyst`, `vse-strateg`) — NIE deployują

Rola analityczna = diagnoza, raportowanie, planowanie. **Nie implementuj, nie deployuj.**
- ❌ docker compose up/build
- ✅ Curl do publicznych endpointów (weryfikacja)
- ✅ GitHub MCP (odczyt kodu)
- ✅ SSH grep/sed (czytanie plików na VPS)
- ✅ Raport → Supervisor

### Agenci implementacyjni (`vse-dev-*`) — deployują jako część deliverable

Dispatch dla `vse-dev` **zawsze kończy się deployem**, chyba że dispatch jawnie mówi inaczej.

```powershell
# Standardowy deploy backend:
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api"

# Standardowy deploy frontend:
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 `
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-web && docker compose -f docker-compose.vse.yml up -d vse-web"
```

**Przeciwwskazania do deploy** (jedyne sytuacje gdy `vse-dev` NIE deployuje):
- Dispatch jawnie zabrania (`# BEZ DEPLOY`)
- Agent ma V1 🔴 (kontekst wyczerpany) — handoff zamiast deploy
- Zmiana wymaga migracji DB z downtime — zgłoś Supervisorowi

---

## ⛔ MANDATORY PRE-DEPLOY BACKUP
Każdy deploy na VPS MUSI zacząć się od:
```bash
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"
```
Agent NIE MOŻE pominąć tego kroku. Jeśli backup fail → STOP deploy.

---

## 📖 STANDARD DOKUMENTACJI — HUMAN-FIRST

**Reguła wprowadzona: 2026-06-15 przez Supervisora 01**

Każdy dokument w projekcie (docs/, AGENTS.md, komentarze w kodzie, raporty) musi odpowiadać na trzy pytania:

| Pytanie | Co opisuje |
|---|---|
| **CO** | Co to jest, jak się nazywa, co robi |
| **PO CO** | Dlaczego istnieje, jaki problem rozwiązuje, jaki jest cel biznesowy |
| **JAK** | Jak działa technicznie, jakie są zależności, jak uruchomić |

**Dlaczego to ważne:** Kolejny agent wczytujący projekt NIE MA kontekstu poprzednich sesji. Jeśli dokumentacja zawiera tylko specyfikację techniczną ("endpoint przyjmuje pole X typu Y"), agent musi rekonstruować intencję przez badania kodu — to kosztuje kroki i prowadzi do błędnych decyzji.

---

## 🎯 WIZJA PRODUKTU — Dashboard (2 ścieżki)

**Decyzja podjęta: 2026-06-15 przez Właściciela projektu**

### Ścieżka A — Free / Starter
**Co:** Po wklejeniu URL YouTube dashboard pokazuje gotowe snippety HTML.
**Po co:** Klient bez dostępu do API WordPressa może skopiować gotowy kod i wkleić go ręcznie.
**Endpoint:** `POST /v1/generate`

### Ścieżka B — Pro / Agency
**Co:** Po wygenerowaniu SEO pojawia się sekcja "Publikuj do WordPress" z wyborem portalu.
**Po co:** Agencja obsługuje wiele portali. Jeden klik = artykuł na portalu.
**Endpointy:** `POST /v1/generate` → `POST /v1/inject`

### Mapowanie planów
| Plan | Ścieżka |
|---|---|
| `free` | A — snippety HTML, kopiuj |
| `starter` | A — snippety HTML, kopiuj |
| `pro` | A + B — generate + inject |
| `agency` | A + B — generate + inject, wiele portali |

---

## 🚨 GOTCHA — Pułapki Operacyjne (Faza 1 Deploy)

Zanotowane po sesji 2026-06-14. CZYTAJ PRZED KAŻDYM DEPLOYEM.

### 1. Port binding `127.0.0.1:3001` → nginx 502
**Fix:** Port `vse-web` MUSI być `"3001:3001"` (0.0.0.0), nie `"127.0.0.1:3001:3001"`.

### 2. `next.config.ts` nie działa w Next.js 14
**Fix:** Zawsze używaj `next.config.mjs` (lub `.js`).

### 3. Brak `postcss.config.js` → Tailwind CSS nie procesowany
**Fix:** `web/postcss.config.js` MUSI istnieć z `tailwindcss` i `autoprefixer`.

### 4. `npm ci` bez `package-lock.json` → build fail
**Fix:** Użyj `RUN npm install` lub wcommituj `package-lock.json`.

### 5. `COPY ... 2>/dev/null || true` w Dockerfile → checksum error
**Fix:** Utwórz puste katalogi (`public/.gitkeep`) i używaj prostego `COPY src dst`.

### 6. `git reset --hard` nadpisuje lokalne zmiany docker-compose na VPS
**Fix:** Zawsze commituj ostateczną wersję docker-compose do GitHub przed deployem.

### 7. Cloudflare cache może serwować stary 502
**Fix:** Cloudflare Dashboard → Caching → **Purge Everything**.

### 8. `next-auth` v4 + Next.js 14 App Router: TypeScript type error
**Fix:** W `next.config.mjs` dodaj `typescript: { ignoreBuildErrors: true }` i `eslint: { ignoreDuringBuilds: true }`.

### 9. Next.js rewrites przechwytują NextAuth (G8/G9)
**Fix:** NIE dodawaj rewrites dla `/api/*`. nginx MUSI mieć blok `location /api/auth/` PRZED `location /api/`.

---

## 🎯 Misja Projektu

PressAI Video SEO Engine automatyzuje optymalizację SEO treści wideo.
Pipeline: YouTube → VTT transkrypty → AI (Claude/Gemini) → schema/chapters/FAQ → WordPress REST API.
Cel: najlepsze video SEO na rynku — potwierdzone benchmarkiem (8/10 vs konkurencja 2-3/10).

---

## 🏗️ Architektura

### Mapa modułów core/

| Plik | Rola |
|------|------|
| `core/fetcher.py` | YouTube data (transcript + metadata) |
| `core/generator.py` | AI schema generation (VideoObject + Clip + FAQ) |
| `core/injector.py` | WordPress REST API injection |
| `core/sitemap.py` | Video sitemap XML |
| `core/monitor.py` | YouTube Channel Monitor |
| `core/yt_admin.py` | YouTube admin operations (OAuth) |

### Stack frontendu
- **Next.js 14** — `web/` katalog, port `3001`
- **Tailwind CSS v3** — wymaga `postcss.config.js`!
- **NextAuth.js v4** — Email + Google OAuth
- **next.config.mjs** — NIE `.ts`!
- **docker-compose.vse.yml** — port `"3001:3001"` (NIE `127.0.0.1:3001:3001`)

---

## 👥 Roster Agentów

| Callsign | Rola | Deploy? |
|----------|------|--------|
| `vse-architect-01` | Architect — architektura, setup | ✅ tak |
| `vse-dev-01` | Worker/Dev — implementacja, testy | ✅ tak |
| `vse-dev-02` | Worker/Dev — Dashboard UI | ✅ tak |
| `vse-analyst-01` | Analyst — research, raporty | ❌ nie |
| `vse-strateg-01` | Strateg — roadmapa, dispatche | ❌ nie |

---

## 🔑 Stack Technologiczny

- **Python 3.10+** — core pipeline
- **Anthropic Claude** — domyślny LLM
- **FastAPI** — backend web app
- **PostgreSQL** — baza danych
- **WordPress REST API v2** — injection layer
- **pytest** — testy

---

## 🔗 Linki operacyjne

- **Site produkcyjny**: https://vse.impresjapr.pl
- **Swagger API**: https://vse.impresjapr.pl/docs
- **VPS**: 147.224.162.100 (Oracle ARM)
- **SSH**: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **Docker compose**: `docker-compose.vse.yml`
- **Heartbeat**: `.agents/heartbeat.json`
- **Raporty**: `.agents/reports/YYYY-MM-DD_[callsign]_[temat].md`
- **sonic-void inbox**: `.agents/reports/inbox/` (repo sonic-void)

---

*vse-architect-01 | video-seo-engine | 2026-05-13 — v1.0*
*Zaktualizowano: 2026-06-14 [vse-dev-01] — GOTCHA deploy*
*Zaktualizowano: 2026-06-15 [Supervisor 01] — standard dokumentacji, wizja produktu*
*Zaktualizowano: 2026-06-15 [sup-worker-01] — sekcja VPS access*
*Zaktualizowano: 2026-06-29 [Supervisor 01] — reguła VPS per rola (analityk vs worker), SSH jako standard*
*Zaktualizowano: 2026-06-30 [vse-dev-ops] — dodano mandatory pre-deploy backup*
*Zaktualizowano: 2026-07-13 [Supervisor 01] — pułapka czytania dużych plików (grep+sed standard), mapa komponentów dashboard-inner.tsx, plan refactoru*

## SSH z PowerShell — jeden wzorzec, zawsze ten sam

Tryb A (prosta, 1 linia): `ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 "komenda"`

Tryb B (złożona, domyślny): `write_to_file` → `scp pełna ścieżka` → `ssh bash /tmp/skrypt.sh`

Zasada kciuka: >1 cudzysłów lub $zmienna = Tryb B.
Dlaczego: PowerShell interpoluje zmienne i mangluje cudzysłowy zanim dotrą do SSH. Plik omija escapowanie.
