# DISPATCH-VSE-VALIDATE-01 — Walidacja Pipeline na U9HLRRXs5EU

**Wystawia:** Supervisor 01  
**Do:** vse-architect-01  
**Data:** 2026-05-13  
**Priorytet:** HIGH — gate przed Fazą 2  
**Repo:** `video-seo-engine` | branch: `main`

---

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Callsign:** `vse-architect-01`  
**Workspace:** `video-seo-engine`  
**Model sugerowany:** Gemini 2.5 Flash (operacyjny test)

**0. Wczytaj blok systemowy:**
```
view_file → /home/tobroz/projects/sonic-void\.agents\protocols\dispatch-system-block.md
```

**1. Heartbeat** (GitHub MCP):
```
mcp_github_create_or_update_file:
  repo: video-seo-engine | branch: main
  path: .agents/heartbeat.json
  content: {"callsign":"vse-architect-01","status":"working","current_task":"Walidacja pipeline — U9HLRRXs5EU","timestamp":"[ISO]"}
  message: "heartbeat: validation start [vse-architect-01]"
```
Pobierz SHA najpierw — plik już istnieje.

**2. Callsign** — każda odpowiedź:
```
[vse-architect-01 | video-seo-engine DD.MM.YYYY HH:MM] online
```

**3. Reguły shellowe:**
1. `run_command` = ZABLOKOWANY. Nigdy.
2. Komendy lokalne → run_command (bash natywny WSL2)
3. Pliki repo → GitHub MCP `create_or_update_file`
4. `mcp_stellar-relay_*` direct = ZAKAZ

**4. Twój deliverable:** potwierdzony end-to-end test pipeline na `U9HLRRXs5EU` + raport do Supervisora.

---

## Kontekst

Właśnie ukończyłeś Fazę 1 (commity `3f9c243`–`b6570b7`).  
Pipeline `vse generate` + `vse inject` jest gotowy.  
**Ten dispatch = walidacja na żywym filmie przed Fazą 2.**

Faza 2 (Channel Monitor) NIE startuje dopóki ten test nie wróci z ✅.

---

## Film do walidacji

**YouTube ID:** `U9HLRRXs5EU`  
**URL:** https://youtu.be/U9HLRRXs5EU  
**Status:** NOT FOUND w `prawy_tv_matches.json` (stan na 13.05.2026 wieczór)  
**Portal:** prawy.pl

---

## Kroki walidacji

### Krok 1 — Znajdź WP post przez SSH (bash natywny)

```bash
# Zaloguj się do oracle-crimson i sprawdź WP post:
ssh oracle-crimson "cd /home/ubuntu/crimson-void && wp post list --post_type=post --fields=ID,post_title,guid 2>/dev/null | grep 'U9HLRRXs5EU'"
  "args": {
    "target": "local-pc",
    "command": "powershell -Command \"(Invoke-WebRequest 'https://prawy.pl/wp-json/wp/v2/posts?search=U9HLRRXs5EU&per_page=5' -UseBasicParsing).Content\"",
    "timeout": 20
  }
}
```

Jeśli brak wyniku — szukaj po tytule/dacie (film z ~13.05.2026):
```bash
(Invoke-WebRequest 'https://prawy.pl/wp-json/wp/v2/posts?after=2026-05-12T00:00:00&per_page=20&orderby=date&order=desc' -UseBasicParsing).Content
```

Znajdź `wp_id` posta z embeddednym `U9HLRRXs5EU`.

### Krok 2 — Sprawdź czy VTT istnieje

```json
{
  "command": "powershell -Command \"Test-Path 'D:\\Biblioteki\\prawy.pl\\subs\\U9HLRRXs5EU.pl.vtt'\"",
  "timeout": 10
}
```

Jeśli `False` → pobierz VTT:
```bash
cd D:\Biblioteki\prawy.pl; python youtube_fetch.py --video U9HLRRXs5EU --output subs/
```
lub przez `vse`:
```bash
cd [ścieżka do video-seo-engine]; python -m cli.main fetch --video U9HLRRXs5EU
```

### Krok 3 — Generuj SEO (dry-run najpierw)

```bash
cd [ścieżka do video-seo-engine]
python -m cli.main generate --video U9HLRRXs5EU --dry-run
```

Sprawdź output — czy JSON-LD jest poprawny:
- `VideoObject` z `duration`, `uploadDate` z timezone, `embedUrl`
- `Clip[]` — co najmniej 3 rozdziały
- `FAQPage` — co najmniej 3 pytania
- `interactionStatistic` — jeśli YT_API_KEY ustawiony

Jeśli `--dry-run` OK → uruchom pełne generate:
```bash
python -m cli.main generate --video U9HLRRXs5EU
```

### Krok 4 — Inject (dry-run najpierw)

```bash
python -m cli.main inject --video U9HLRRXs5EU --wp-id [ID_Z_KROKU_1] --dry-run
```

Sprawdź:
- Czy schema JSON-LD jest wstrzykiwana w odpowiednie miejsce w content
- Czy thumbnail jest ustawiany poprawnie
- Brak błędów WP REST API

Jeśli OK → inject produkcyjny:
```bash
python -m cli.main inject --video U9HLRRXs5EU --wp-id [ID_Z_KROKU_1]
```

### Krok 5 — Weryfikacja live

Po injekcji sprawdź post przez REST API:
```bash
(Invoke-WebRequest 'https://prawy.pl/wp-json/wp/v2/posts/[WP_ID]' -UseBasicParsing).Content | ConvertFrom-Json | Select-Object -ExpandProperty content | Select-Object -ExpandProperty rendered | Select-String "application/ld+json"
```

Czy `<script type="application/ld+json">` z VideoObject jest w contencie?

---

## Środowisko

Skonfiguruj `.env` w katalogu `video-seo-engine` przed uruchomieniem:
```
GEMINI_API_KEY=[z Credentials Workflow]
YT_API_KEY=[z Credentials Workflow — opcjonalny, dla viewCount]
WP_URL=https://prawy.pl
WP_USER=prawy_admin
WP_APP_PASS=[z Credentials Workflow]
PORTAL=prawy
```

Ścieżka do subs i seo_results — sprawdź `.env.example` dla konfiguracji lokalnych ścieżek.

---

## Raportowanie

Po walidacji:
1. Heartbeat `status: done` (GitHub MCP)
2. Raport do `video-seo-engine/.agents/reports/2026-05-13_vse-architect-01_validation-U9HLRRXs5EU.md`
3. Raport do `sonic-void/.agents/reports/inbox/2026-05-13_vse-architect-01_validation-U9HLRRXs5EU.md`

Raport musi zawierać:
- WP post ID znaleziony dla `U9HLRRXs5EU`
- Wynik dry-run (generate + inject)
- Wynik produkcyjny (czy schema jest live na stronie)
- Błędy jeśli wystąpiły
- Rekomendacja: ✅ GO dla Fazy 2 / ❌ BLOKER z opisem

---

*Supervisor 01 | sonic-void | 2026-05-13*
