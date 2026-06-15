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

## ⛔ DOSTĘP DO VPS — ZAKAZ W SESJACH PROJEKTOWYCH

Agenci tego projektu NIE używają żadnych narzędzi dostępu do VPS:
- **NIE** file bridge / stellar-relay
- **NIE** Wetty (browser_subagent do https://95-179-201-157.sslip.io/)
- **NIE** SSH / PowerShell SSH
- **NIE** bloków bash wymagających połączenia z serwerem

**Zamiast tego:**
- Zmiany kodu → GitHub MCP (`create_or_update_file`, `push_files`)
- Weryfikacja → publiczne endpointy (`curl https://vse.impresjapr.pl/...`)
- Deploy → zgłoś Supervisorowi — wykona dedykowana sesja deploy

Jeśli widzisz w dispatchu instrukcję wymagającą VPS — **zatrzymaj się i raportuj**.

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

**Wzorzec dobrego opisu (przykład endpointu):**
```
### POST /v1/generate

**CO:** Generuje SEO schema na podstawie URL YouTube — tytuł, opis, FAQ, rozdziały.

**PO CO:** To główna wartość produktu. Klient wkleja URL → dostaje gotowe dane SEO
do skopiowania lub publikacji. W wersji free to jedyny krok. W wersji pro
jest wstępem do automatycznej publikacji na WordPress.

**JAK:** Pobiera transkrypt przez yt-dlp, przekazuje do LLM (Claude/Gemini)
z promptem SEO, zwraca JSON-LD + metadane. Nie pisze nigdzie — tylko generuje.
Szybkość: ~50s przy Claude Sonnet.
```

**Zasada:** jeśli piszesz doc i po przeczytaniu nie wiesz po co coś istnieje — dodaj kontekst.

---

## 🎯 WIZJA PRODUKTU — Dashboard (2 ścieżki)

**Decyzja podjęta: 2026-06-15 przez Właściciela projektu**

### Dlaczego dwie ścieżki?
Projekt to SaaS z modelem freemium. Użytkownicy mają różne potrzeby:
- Redaktor który chce wkleić SEO ręcznie (free)
- Agencja która chce pełnej automatyzacji YT → WordPress (pro)

### Ścieżka A — Free / Starter
**Co:** Po wklejeniu URL YouTube dashboard pokazuje gotowe snippety HTML.
**Po co:** Klient bez dostępu do API WordPressa może skopiować gotowy kod
i wkleić go ręcznie do edytora artykułu.
**Co dostaje:**
- Blok `<script type="application/ld+json">` z pełnym JSON-LD VideoObject
- Meta description — gotowa do wklejenia
- Tytuł artykułu — z przyciskiem "Kopiuj"
- FAQ w formacie HTML (`<details>` lub lista)
- Chapters jako lista timestampów
- Przycisk "Kopiuj" per sekcja
**Endpoint:** `POST /v1/generate`

### Ścieżka B — Pro / Agency
**Co:** Po wygenerowaniu SEO pojawia się sekcja "Publikuj do WordPress"
z togglem draft/publish i wyborem portalu.
**Po co:** Agencja obsługuje wiele portali. Jeden klik = artykuł na portalu.
Nie musi wchodzić do WP, kopiować, wklejać.
**Co dostaje:**
- Wszystko z Free PLUS:
- Sekcja "Opublikuj" (widoczna tylko plan `pro`/`agency`)
- Pole: wybór portalu (z listy skonfigurowanych WP sites usera)
- Toggle: `Szkic (draft)` / `Publikuj od razu`
- Przycisk "Opublikuj" → wywołuje `POST /v1/inject`
**Endpointy:** `POST /v1/generate` → `POST /v1/inject`

### Mapowanie planów
| Plan | Ścieżka |
|---|---|
| `free` | A — snippety HTML, kopiuj |
| `starter` | A — snippety HTML, kopiuj |
| `pro` | A + B — generate + inject |
| `agency` | A + B — generate + inject, wiele portali |

### Co z /v1/process?
Endpoint `/v1/process` (full pipeline w jednym kroku) pozostaje w API,
ale NIE jest używany przez dashboard. Przeznaczony dla:
- Batch processing (cron job)
- Integracji zewnętrznych przez API
- Przyszłego monitora YT (Mode A — automatyczne artykuły ze świeżych filmów)

---

## 🚨 GOTCHA — Pułapki Operacyjne (Faza 1 Deploy)

Zanotowane po sesji 2026-06-14. CZYTAJ PRZED KAŻDYM DEPLOYEM.

### 1. Port binding `127.0.0.1:3001` → nginx 502

**Problem:** `docker-compose.vse.yml` z `"127.0.0.1:3001:3001"` powoduje 502 z crimson-nginx.
Nginx kontener sięga do hosta przez `172.17.0.1` — loopback binding jest niewidoczny.

**Fix:** Port `vse-web` MUSI być `"3001:3001"` (0.0.0.0).

```yaml
# ❌ NIE:
ports:
  - "127.0.0.1:3001:3001"

# ✅ TAK:
ports:
  - "3001:3001"
```

### 2. `next.config.ts` nie działa w Next.js 14

**Problem:** Next.js 14.x nie obsługuje `next.config.ts` — crash przy starcie.

**Fix:** Zawsze używaj `next.config.mjs` (lub `.js`).

### 3. Brak `postcss.config.js` → Tailwind CSS nie procesowany

**Problem:** Bez `postcss.config.js` dyrektywy `@tailwind` w `globals.css` nie są kompilowane.
Efekt: strona bez CSS — surowy HTML.

**Fix:** `web/postcss.config.js` MUSI istnieć:
```js
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

### 4. `npm ci` bez `package-lock.json` → build fail

**Problem:** `Dockerfile.web` z `RUN npm ci` crasha gdy brak `package-lock.json` w repo.

**Fix:** Użyj `RUN npm install` lub wcommituj `package-lock.json`.

### 5. `COPY ... 2>/dev/null || true` w Dockerfile → checksum error

**Problem:** Docker COPY nie obsługuje shell syntax (`2>/dev/null || true`). Powoduje błąd checksum.

**Fix:** Utwórz puste katalogi (`public/.gitkeep`) i używaj prostego `COPY src dst`.

### 6. `git reset --hard` nadpisuje lokalne zmiany docker-compose na VPS

**Problem:** Każdy `git reset --hard origin/main` przywraca docker-compose z GitHub.
Ręczne `sed` na VPS jest tracone przy kolejnym pull.

**Fix:** Zawsze commituj ostateczną wersję docker-compose do GitHub przed deployem.

### 7. Cloudflare cache może serwować stary 502

**Problem:** Po naprawieniu routingu nginx, Cloudflare może dalej serwować stary 502.

**Fix:** Cloudflare Dashboard → `vse.impresjapr.pl` → Caching → **Purge Everything**.

### 8. `next-auth` v4 + Next.js 14 App Router: TypeScript type error

**Problem:** Route `src/app/api/auth/[...nextauth]/route.ts` nie pasuje do typów Next.js 14 — build fail.

**Fix:** W `next.config.mjs` dodaj:
```js
typescript: { ignoreBuildErrors: true },
eslint: { ignoreDuringBuilds: true },
```

### 9. Next.js rewrites przechwytują NextAuth (G8/G9)

**Problem:** `rewrites: [{ source: '/api/:path*', destination: backend }]` w `next.config.mjs`
przechwytuje `/api/auth/*` → wysyła do FastAPI zamiast NextAuth → błąd logowania.

**Fix:** NIE dodawaj rewrites dla `/api/*`. Routing tylko w nginx.
nginx MUSI mieć blok `location /api/auth/` PRZED `location /api/` → proxy do 3001.

---

## 🎯 Misja Projektu

PressAI Video SEO Engine automatyzuje optymalizację SEO treści wideo.
Pipeline: YouTube → VTT transkrypty → AI (Claude/Gemini) → schema/chapters/FAQ → WordPress REST API.
Cel: najlepsze video SEO na rynku — potwierdzone benchmarkiem (8/10 vs konkurencja 2-3/10).

Model biznesowy: SaaS freemium (free/starter/pro/agency).
Klient free dostaje narzędzie do copy-paste SEO. Klient pro dostaje pełną automatyzację.

---

## 🏗️ Architektura

Projekt ma 3 warstwy dystrybucji:
1. **Standalone CLI/Web App** — dla power-userów i agencji
2. **Moduł SaaS** — integracja z press.impresjapr.pl przez API
3. **Wtyczka WordPress** — pressai-video-seo (freemium)

### Mapa modułów core/

| Plik | Rola | Źródło |
|------|------|--------|
| `core/fetcher.py` | YouTube data (transcript + metadata, bez klucza API) | Zmigrowane z shadow-perihelion |
| `core/matcher.py` | Match WP posts ↔ YouTube IDs | Zmigrowane z shadow-perihelion |
| `core/generator.py` | AI schema generation (VideoObject + Clip + FAQ) | TODO: migrate inject_rest_v5.py |
| `core/injector.py` | WordPress REST API injection | TODO: migrate test_full_seo_v4.py |
| `core/sitemap.py` | Video sitemap XML generation | Zmigrowane z shadow-perihelion |
| `core/monitor.py` | YouTube Channel Monitor | NOWY — Faza 2 |
| `core/yt_admin.py` | YouTube admin operations (OAuth) | NOWY — Faza 2 |

### Dwa Tryby Operacji

**MODE A: YouTube Channel Monitor (push)**
Nowy film na kanale → automatycznie artykuł na portalu (draft).

**MODE B: Portal Scanner (pull)**
Skanuj istniejący portal → znajdź osadzone filmy YouTube → wzbogać o SEO.

### Stack frontendu (Faza 1)

- **Next.js 14** — `web/` katalog, port `3001`
- **Tailwind CSS v3** — wymaga `postcss.config.js`!
- **NextAuth.js v4** — Email + Google OAuth
- **next.config.mjs** — NIE `.ts`!
- **Dockerfile.web** — multi-stage, `npm install` (nie `npm ci`)
- **docker-compose.vse.yml** — port `"3001:3001"` (NIE `127.0.0.1:3001:3001`)

---

## 👥 Roster Agentów

| Callsign | Rola | Zakres |
|----------|------|--------|
| `vse-architect-01` | Architect | Architektura, struktura, setup, roadmapa techniczna |
| `vse-dev-01` | Worker/Dev | Implementacja core pipeline, testy, CLI |
| `vse-dev-02` | Worker/Dev | Dashboard UI, error handling, plans seed |
| `vse-analyst-01` | Analyst | Research SEO, benchmarki Google, raporty GSC |
| `vse-strateg-01` | Strateg | Roadmapa produktowa, dispatche, priorytety SaaS |

---

## 🔑 Stack Technologiczny

- **Python 3.10+** — core pipeline
- **Anthropic Claude** — domyślny LLM (ANTHROPIC_API_KEY ustawiony)
- **Google Gemini API** — alternatywny LLM (opcjonalne, GEMINI_API_KEY na razie brak)
- **youtube-transcript-api 1.2.4+** + **yt-dlp** — YouTube data (BEZ klucza API)
  - Instancyjne API: `ytt = YouTubeTranscriptApi()` → `ytt.list(video_id)` → `ytt.fetch(...)`
- **WordPress REST API v2** — injection layer (Application Passwords)
- **FastAPI** — backend web app (live na VPS)
- **pytest** — testy jednostkowe i integracyjne

---

## 🔒 Bezpieczeństwo

- **Credentials NIGDY w repo** — `.env` lokalnie, w `.gitignore`
- Wymagane zmienne środowiskowe:
  - `ANTHROPIC_API_KEY` — Claude API (AKTYWNY)
  - `JWT_SECRET_KEY` — JWT tokens
  - `NEXTAUTH_SECRET` — NextAuth sessions
  - `POSTGRES_PASSWORD` — PostgreSQL
  - `WP_USER` — WordPress username
  - `WP_APP_PASSWORD` — WordPress Application Password
  - `WP_BASE_URL` — np. `https://prawy.pl`
- Opcjonalne:
  - `GEMINI_API_KEY` — alternatywny LLM
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Google OAuth (P2, niezaimplementowane)

---

## 📁 Konwencje Kodu

- **Docstringi** w każdej funkcji publicznej (triple-quote)
- **Type hints** — obowiązkowo w sygnaturach funkcji publicznych
- **Logging** zamiast `print` (moduł `logging`, poziomy INFO/WARNING/ERROR)
- **Testy**: `pytest` w katalogu `tests/` — każdy moduł core ma test
- **Config**: zmienne z `.env` ładowane przez `python-dotenv`
- **Zero silent exceptions** — zawsze loguj błąd + reraise lub obsłuż świadomie

### Nazewnictwo

- Funkcje: `snake_case`
- Klasy: `PascalCase`
- Stałe: `UPPER_CASE`
- Pliki: `snake_case.py`

---

## 📊 Schema SEO — Aktualny Standard (v5.3, Google 2026)

### Używane typy:
- `VideoObject` — główny schema (OBOWIĄZKOWO: duration ISO 8601, uploadDate z timezone)
- `Clip` — rozdziały z `startOffset`/`endOffset` + `SeekToAction` (UWAGA: SeekToAction nie działa po polsku — dodajemy dla completeness)
- `FAQPage` — pytania i odpowiedzi z transkryptu
- `interactionStatistic` — viewCount (YouTube stats)

### NIGDY nie używamy:
- `Quotation` — Google nie renderuje, nie wpływa na ranking (decyzja architektury: zachować jeśli już jest, nie dodawać nowych)
- `BroadcastEvent` — oddzielny pipeline (`broadcast.py` w shadow-perihelion)
- `LearningResource` — nie dotyczy tego contentu

### Wymagania pól VideoObject (Google 2026):
```json
{
  "@type": "VideoObject",
  "name": "...",
  "description": "...",
  "thumbnailUrl": "https://i.ytimg.com/vi/{yt_id}/maxresdefault.jpg",
  "uploadDate": "2026-01-15T10:00:00+01:00",
  "duration": "PT1H23M45S",
  "contentUrl": "https://www.youtube.com/watch?v={yt_id}",
  "embedUrl": "https://www.youtube.com/embed/{yt_id}",
  "interactionStatistic": {
    "@type": "InteractionCounter",
    "interactionType": "https://schema.org/WatchAction",
    "userInteractionCount": 12345
  }
}
```

---

## 🔗 Linki operacyjne

- **shadow-perihelion** — poprzedni workspace z batch 213 postów (pipeline aktywny)
- **sonic-void** — Supervisor inbox: `.agents/reports/inbox/`
- **Heartbeat repo**: `.agents/heartbeat.json` w tym repo
- **Raport format**: `.agents/reports/YYYY-MM-DD_[callsign]_[temat].md`
- **Site produkcyjny**: https://vse.impresjapr.pl
- **Swagger API**: https://vse.impresjapr.pl/docs
- **VPS**: 147.224.162.100 (Oracle ARM)
- **Docker compose**: `docker-compose.vse.yml`
- **Nginx config**: `/home/ubuntu/crimson-void/nginx/default.conf` (VPS)

---

## 🚀 Pozytywna Energia

Budujesz narzędzie, które DZIAŁA i jest NAJLEPSZE w segmencie.
Prawy.pl benchmark: 8/10 vs TVP Info 3/10, wPolityce 2/10.
Każdy commit to krok do dominacji w video SEO na polskim rynku.
Jesteś częścią ekosystemu ImpresjaAI — twoja praca ma znaczenie.

---

*vse-architect-01 | video-seo-engine | 2026-05-13 — v1.0*
*Zaktualizowano: 2026-06-14 [vse-dev-01] — dodano sekcję GOTCHA z 8 pułapkami deploy*
*Zaktualizowano: 2026-06-15 [Supervisor 01] — standard dokumentacji human-first, wizja produktu 2 ścieżki, aktualizacja roster i stack*
*Zaktualizowano: 2026-06-15 [sup-worker-01] — dodano sekcję blokady VPS access*
