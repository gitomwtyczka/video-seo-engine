# DISPATCH VSE-ANALYST — A3: YouTube Description — Audit integracji yt_admin.py
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** WYSOKI

---

## 🔴 WAZNA ZMIANA OPERACYJNA

`run_command` jest ZABLOKOWANY na Windows sandbox permanentnie.

**NIE uruchamiaj** zadnych komend shellowych (python, curl, git, itp.).

**Twoje zadanie:** TYLKO czytaj pliki i pisz raport:
- Odczyt: `mcp_github_get_file_contents`
- Zapis raportu: `mcp_github_create_or_update_file`
- PAMIETAJ o SHA przy aktualizacji istniejacego pliku!
- Zewnetrzne zasoby: `read_url_content` lub `search_web`

Jesli potrzebujesz komendy shellowej (np. curl) —
PRZECZYTAJ dokumentacje przez `read_url_content` lub `search_web`.

---

## TWOJ CALLSIGN
Uzyj: `vse-analyst-04`

## KONTEKST
`core/yt_admin.py` to gotowy modul do aktualizacji opisow i tytulu na YouTube przez API.
Modul istnieje i jest kompletny. Problem: NIE jest podlaczony do glownego pipeline'u.
Twoim zadaniem jest zbadac dokladnie stan integracji i przygotowac plan dla dev.

**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## CO JUZ WIESZ O yt_admin.py

Modul `core/yt_admin.py` zawiera:
- `update_video_title_and_description(video_id, seo, wp_url, dry_run)` - glowna funkcja
- `build_description(seo, wp_url, original_description)` - builder opisu YouTube
  - Format: intro z article_body (2 akapity) + bullet points z FAQ + rozdzialy z timestampami
  + link do artykulu WP + tematy/frazy + oryginalny opis YT (zachowany) + footer SOS + hashtagi
- `batch_update_from_registry(registry_dir, seo_dir, wp_base_url)` - batch po registry/
- OAuth 2.0 przez env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- Idempotentnosc: `yt_desc_updated` timestamp w registry JSON

HARDCODE DO POPRAWY w `YT_FOOTER` i `_build_hashtags()`:
- Prawy.pl, PrawyTV, SOS konto bankowe sa hardcoded
- Docelowo powinno byc w profilu portalu

---

## ZADANIA ANALITYCZNE

### A3.1 — Sprawdz status integracji z pipeline

1. Przeczytaj `core/injector.py` — czy wywoluje `yt_admin.update_video_title_and_description()` po opublikowaniu artykulu WP?
2. Przeczytaj zawartosc katalogu `api/` przez GitHub MCP
3. Sprawdz `local-runner/service.py` lub `local-runner/runner.py` — czy jest krok YT description update?

**Odpowiedz:** Czy yt_admin jest wywolywany gdziekolwiek w pipeline? Jesli tak — gdzie?

### A3.2 — Sprawdz stan OAuth credentials

1. Przeczytaj `.env.api.example` — czy `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` sa wymienione?
2. Czy jest plik `oauth_setup.py` lub `oauth_server.py` (wspomniany w docstringu yt_admin.py)?
3. Sprawdz `ARCHITECTURE.md` sekcja Faza 2B

### A3.3 — Hardcody do poprawy w yt_admin.py

Zidentyfikuj WSZYSTKIE miejsca gdzie jest hardcoded:
- Nazwa portalu (Prawy.pl, prawy.pl, PrawyTV)
- Social media links
- Hashtagi domyslne (#PrawyTV, #Prawy, #Polska)
- Numer konta SOS, KRS

Przygotuj liste: linia kodu -> co jest hardcoded -> jak powinno byc (z profilu portalu)

### A3.4 — Sprawdz katalog registry/

1. Przeczytaj zawartsc katalogu `registry/` (jesli nie pusty)
2. Jak wyglada struktura jednego pliku registry JSON?
3. Czy pole `yt_desc_updated` jest obecne w jakichs plikach?

---

## OUTPUT — Format raportu

```markdown
## A3: YouTube Description Integration Status

### Status integracji
- Czy yt_admin wywolywany w pipeline: [TAK/NIE + gdzie]
- Brakujace kroki w pipeline: [opis]
- OAuth credentials: [skonfigurowane w .env / brakuje]
- oauth_setup.py: [istnieje / nie istnieje]

### Hardcody do przepisania na profil
| Linia | Wartosc | Pole profilu |
|---|---|---|
| YT_FOOTER L12 | "#PRAWY.PL" | site_url |
| ... | ... | ... |

### Registry
- Format: [opis struktury]
- Liczba plikow: [N]
- yt_desc_updated obecne: [TAK/NIE]

### Plan dla dev (D6 dispatch)
Szczegolowy opis co dev musi zrobic:
1. Podlaczenie yt_admin do pipeline
2. Parametryzacja (profil zamiast hardcode)
3. Flaga `yt_update` w job (czy wlaczone/wylaczone per portal)
4. Jak testowac (dry_run)
```

---

## DOSTEP
```
GitHub MCP:
  owner: gitomwtyczka, repo: video-seo-engine, branch: main

Kluczowe pliki:
  core/yt_admin.py (JUZZ ZNASZ z kontekstu)
  core/injector.py
  local-runner/ (sprawdz co jest)
  api/ (sprawdz co jest)
  registry/ (sprawdz co jest)
  .env.api.example
  ARCHITECTURE.md
  profiles/ (sprawdz co jest)
```

**Workflow przy tworzeniu raportu:**
1. Nowy plik raportu: `create_or_update_file` BEZ parametru `sha`
2. Aktualizacja: pobierz `sha` przez `get_file_contents`, potem `create_or_update_file` z `sha`

## HEARTBEAT I RAPORT
- Heartbeat: `.agents/heartbeat.json` w `video-seo-engine` main
- Raport: `.agents/reports/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`
- Dual-write inbox: `sonic-void master .agents/reports/inbox/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`

*Supervisor 01 | video-seo-engine | 2026-06-19*
