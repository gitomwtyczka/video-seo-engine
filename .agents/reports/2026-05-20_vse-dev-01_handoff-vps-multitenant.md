# RAPORT HANDOFF — VSE SESSION 2026-05-20
## vse-dev-01 → Supervisor / Następca

**Data**: 2026-05-20 11:30 CEST  
**Callsign**: vse-dev-01 (worker implementacyjny)  
**Sesja**: 32dc395c-f487-4f95-95c2-129bcf13c2f6

---

## 1. CO ZROBIONE W TEJ SESJI

### 1.1 Przetworzono backlog (łącznie 39+1 filmów)

| Batch | Filmy | Status |
|-------|-------|--------|
| Batch 1 (audyt) | 13/13 | ✅ pełny pipeline |
| Batch 2 | 5/5 | ✅ pełny pipeline |
| Batch 3 | 20/20 | ✅ pełny pipeline (1 retry `rYsvm_UfsJI`) |
| Hotfix | `M1pmpDJUyAA` (`WP#119846`) | ✅ + usunięty duplikat `WP#119959` |

**Pełny pipeline każdego filmu**: VTT → Gemini 2.5 Flash → WP REST API → RankMath → YouTube OAuth desc

### 1.2 Refaktor architektoniczny — multi-tenant (commit `6e793c4`)

- `core/profile.py` — system YAML profili per portal + env fallback
- `profiles/prawy.yaml` — profil Prawy.pl
- `profiles/template.yaml` — szablon dla nowych portali
- `core/injector.py` — odcięto hardcoded `prawySeek`/`.prawy-chapter` → `_build_player_js(seek_fn, chapter_class)`
- `cli/main.py` — `--profile <name>` dodane do `inject`, `generate`, `watch`
- `Dockerfile` + `docker-compose.vse.yml` — VPS deployment ready
- `requirements.txt` — pyyaml dodany

---

## 2. STAN KOŃCOWY SYSTEMU

### Git
```
HEAD: 6e793c4 (main)
Unpushed commits: 3 (6e793c4, 5040128, fa5ca69... vs origin/main 2789562)
```

### Pliki produkcyjne (lokalne, WSL2 Jagodziak4)
```
/home/tobroz/projects/video-seo-engine/
├── seo_results/     ← 41 wygenerowanych JSON
├── subs/            ← 43 pliki VTT
├── registry/        ← 11 wpisów
├── data/prawy/      ← nowa ścieżka (multi-tenant)
├── profiles/        ← prawy.yaml + template.yaml
├── Dockerfile       ← gotowy
└── docker-compose.vse.yml ← gotowy
```

---

## 3. CO ZOSTAŁO DO ZROBIENIA

### PRIORYTET 1 — VPS Deploy (oracle-crimson 147.224.162.100)

```
[ ] a) Eksport cookies.txt z Firefox (Jagodziak4)
        yt-dlp --cookies-from-browser "firefox:..." → cookies/prawy_cookies.txt

[ ] b) git push origin main
        (3 unpushed commits)

[ ] c) SSH oracle-crimson:
        git clone / pull /opt/vse
        cp .env → .env.production (z ~/.impresja/secrets/vse.env)
        docker compose -f docker-compose.vse.yml up -d --build
        docker logs -f vse-watch

[ ] d) Weryfikacja E2E:
        Nowy film → WP draft pojawia się w ciągu 30 min
```

### PRIORYTET 2 — Backlog historyczny (~144 filmów)

Backlog do daty 2026-04-11 i wcześniej nie przetworzony.
Mechanizm batch ready — potrzeba tylko listy matches JSON.

```bash
# Komenda startowa (po pobraniu nowych matches):
python3 -m cli.main generate --batch <nowy_batch.json> --profile prawy
python3 -m cli.main inject --batch data/prawy/seo_results/ --profile prawy
```

### PRIORYTET 3 — git push

```bash
cd /home/tobroz/projects/video-seo-engine
git push origin main
```

### PRIORYTET 4 — FastAPI REST layer (Faza 3)

Zaplanowane w `docker-compose.vse.yml` jako zakomentowany serwis `vse-api`.
Integracja z Crimson SaaS przez POST /api/v1/process.

---

## 4. CREDENTIALE (dla Supervisor — Credentials Keeper)

Wszystkie sekrety w: `~/.impresja/secrets/vse.env` na **Jagodziak4 (WSL2)**

| Zmienna | Serwis | Uwagi |
|---------|--------|-------|
| `GEMINI_API_KEY` | Google AI — Gemini 2.5 Flash | projekt: antigravity-mcp-keys |
| `WP_USER` | prawy.pl WordPress | admin user |
| `WP_APP_PASSWORD` | prawy.pl WP REST API | Application Password |
| `YT_API_KEY` | YouTube Data API v3 | quota: 10k/dzień |
| `YT_CLIENT_ID` | YouTube OAuth 2.0 | Prawy TV brand account owner |
| `YT_CLIENT_SECRET` | YouTube OAuth 2.0 | — |
| `YT_REFRESH_TOKEN` | YouTube OAuth 2.0 | **nie wygasa** (offline access) |
| `CHANNEL_ID` | YouTube kanał Prawy TV | UCxxx... |

**GCP projekt**: `antigravity-mcp-keys`  
**OAuth app name**: `PressAI Video SEO`  
**OAuth scope**: `youtube.force-ssl`  

> [!IMPORTANT]
> YT_REFRESH_TOKEN musi być skopiowany na VPS (oracle-crimson) do `.env.production`

---

## 5. ARCHITEKTURA — QUICK REFERENCE

```
vse generate --video <YT_ID> --wp-id <N> --title "..."  # Single
vse generate --batch batch.json --profile prawy           # Batch
vse inject --video <YT_ID> --wp-id <N> --profile prawy   # Single
vse inject --batch data/prawy/seo_results/ --profile prawy # Batch
vse watch --profile prawy --interval 1800                  # Daemon VPS
```

**Profile YAML**: `profiles/<portal_id>.yaml` — klucze API jako `${ENV_VAR}`  
**Nowy portal**: skopiuj `profiles/template.yaml`, uzupełnij, dodaj `.env.kurier365`

---

## 6. ZNANE PROBLEMY / OSTRZEŻENIA

1. **cookies.txt na VPS** — yt-dlp na VPS wymaga wyeksportowanych cookies z Firefox. Wygasają ~30 dni. Fallback: `youtube-transcript-api` (działa dla filmów publicznych).

2. **git push blokada** — 3 commity lokalnie, nie zpushowane. Następca musi `git push` przed deploy na VPS.

3. **data/ lokalna vs VPS** — lokalnie `subs/` + `seo_results/` (stare ścieżki). Na VPS używamy `data/prawy/subs/` (nowe ścieżki z profilu). Migracja nie jest wymagana — stary backlog można przeprocesować z nowej ścieżki.

4. **Archiwum/dashboard** — zaplanowane jako feature #30 (niski priorytet, Faza 3). SQLite `registry/` jest bazą pod to — wystarczy frontend tabelaryczny.

---

*vse-dev-01 | 2026-05-20 | handoff do następcy*
