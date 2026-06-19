# DISPATCH VSE-ANALYST — A3: YouTube Description — Audit integracji yt_admin.py
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** WYSOKI

## TWOJ CALLSIGN
Uzyj: `vse-analyst-04`

## KONTEKST
`core/yt_admin.py` to gotowy modul do aktualizacji opisow i tytulu na YouTube przez API.
Modól istnieje i jest kompletny. Problem: NIE jest podlaczony do glownego pipeline'u.
Twoim zadaniem jest zbadac dokladnie stan integracji i przygotowac plan dla dev.

**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## CO JUZ WIESZ O yt_admin.py

Modul `core/yt_admin.py` zawiera:
- `update_video_title_and_description(video_id, seo, wp_url, dry_run)` - glowna funkcja
- `build_description(seo, wp_url, original_description)` - builder opisu YouTube
  - Format: intro z article_body (2 akapity) + bullet points z FAQ + rozdzialy z timestampami
  + link do artykułu WP + tematy/frazy + oryginalny opis YT (zachowany) + footer SOS + hashtagi
- `batch_update_from_registry(registry_dir, seo_dir, wp_base_url)` - batch po registry/
- OAuth 2.0 przez env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
- Idempotentnosc: `yt_desc_updated` timestamp w registry JSON

HARDCODE DO POPRAWY w `YT_FOOTER` i `_build_hashtags()`:
- `#PrawyTV`, `#Prawy`, `#Polska` sa hardcoded jako domyslne hashtagi
- Social links (Facebook, Twitter) sa hardcoded dla prawy.pl
- Podobnie w `_build_hashtags()` - linki SOS sa prawy.pl-specific
To samo co w D1 (site_brand) — docelowo powinno byc w profilu portalu.

---

## ZADANIA ANALITYCZNE

### A3.1 — Sprawdz status integracji z pipeline

1. Przeczytaj `core/injector.py` — czy wywoluje `yt_admin.update_video_title_and_description()` po wygenerowaniu i opublikowaniu artykułu WP?
2. Przeczytaj `api/` directory — czy jest endpoint API ktory triggeruje YT update?
3. Sprawdz `local-runner/service.py` lub `local-runner/runner.py` — czy w workflołie przetwarzania videa jest krok YT description update?
4. Sprawdz `core/pipeline.py` jesli istnieje

**Odpowiedz:** Czy yt_admin jest wywolywany gdziekolwiek w pipeline? Jesli tak — gdzie i z jakimi parametrami?

### A3.2 — Sprawdz stan OAuth credentials

1. Przeczytaj `.env.example` lub `.env.api.example` — czy `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` sa wymienione jako wymagane?
2. Sprawdz `ARCHITECTURE.md` — czy jest opis Fazy 2B (YouTube Description Writer)?
3. Czy jest plik `oauth_setup.py` lub `oauth_server.py` (wspomniany w docstringu yt_admin.py)?

### A3.3 — Sprawdz hardcody w yt_admin.py do poprawy

Zidentyfikuj WSZYSTKIE miejsca w `core/yt_admin.py` gdzie jest hardcoded:
- Nazwa portalu (Prawy.pl, prawy.pl, PrawyTV)
- Social media links (facebook.com/PortalPrawy, twitter.com/prawypl, youtube.com/user/portalprawypl)
- Hashtagi (#PrawyTV, #Prawy, #Polska)
- Numer konta SOS, KRS

Przygotuj liste: linia kodu -> co jest hardcoded -> jak powinno byc (z profilu portalu)

### A3.4 — Sprawdz `registry/` — format i stan

1. Przeczytaj zawartsc katalogu `registry/` (jesli nie pusty)
2. Jak wyglada struktura jednego pliku registry JSON?
3. Czy pole `yt_desc_updated` jest obecne w jakichs plikach (czy ktos juz uruchamial batch)?

---

## OUTPUT — Format raportu

Napisz raport z sekcjami:

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
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main

Kluczowe pliki:
  core/yt_admin.py (JUZZ ZNASZ)
  core/injector.py
  local-runner/service.py lub runner.py
  api/ (sprawdz co jest)
  registry/ (sprawdz co jest)
  .env.api.example
  ARCHITECTURE.md
  profiles/ (sprawdz co jest)
```

## HEARTBEAT I RAPORT
- Heartbeat: `.agents/heartbeat.json` w `video-seo-engine` main
- Raport: `.agents/reports/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`
- Dual-write inbox: `sonic-void master .agents/reports/inbox/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`

*Supervisor 01 | video-seo-engine | 2026-06-19*
