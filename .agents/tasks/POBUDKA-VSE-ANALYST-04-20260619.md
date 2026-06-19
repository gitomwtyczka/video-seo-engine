# POBUDKA — vse-analyst-04 | YouTube Description Integration Audit

**Data:** 2026-06-19
**Dla:** `vse-analyst-04`
**Wystawia:** Supervisor 01

---

## Stan projektu na start

Jestes agentem `vse-analyst-04` wcielanym do projektu `video-seo-engine`.

**Co jest gotowe:**
- ✅ `core/yt_admin.py` — kompletny modul do aktualizacji YouTube opisow przez OAuth 2.0
  - `update_video_title_and_description()` — aktualizuje tytul + opis w jednym API call
  - `build_description()` — format: intro + FAQ bullets + rozdzialy + link WP + footer + hashtagi
  - `batch_update_from_registry()` — idempotentny batch po registry/
  - OAuth 2.0 z refreshem przez env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

**Co jest problemem (to Twoje zadanie — zbadaj i zaraportuj):**
- ❌ `yt_admin.py` NIE jest podlaczony do pipeline (nie wywolywany po publikacji WP)
- ❓ Gdzie dokladnie go podlaczyc (injector.py? api endpoint? local-runner?)
- ❓ YT_FOOTER i hashtagi sa hardcoded dla prawy.pl — co trzeba sparametryzowac?
- ❓ Jakie pola z profilu portalu sa potrzebne?

Nie implementujesz — TYLKO czytasz i raportujesz.

---

## Twoje pierwsze kroki

1. **Przeczytaj przez GitHub MCP (owner: gitomwtyczka, repo: video-seo-engine, branch: main):**
   - `.agents/tasks/DISPATCH-VSE-ANALYST-04-20260619-YT-ADMIN-AUDIT.md` (pelna spec)
   - `core/injector.py` (czy wywoluje yt_admin?)
   - Katalog `local-runner/` (sprawdz co jest)
   - Katalog `api/` (sprawdz co jest)
   - Katalog `registry/` (sprawdz co jest + struktura JSON)
   - `.env.api.example` (czy OAuth vars sa wymienione?)
   - `ARCHITECTURE.md` (sekcja Faza 2B)

2. **Wyslij heartbeat** do `.agents/heartbeat.json` w repo video-seo-engine.

3. **Napisz raport** do `.agents/reports/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`

---

## Krytyczne zasady operacyjne

### 🔴 run_command ZABLOKOWANY

NIE uruchamiaj zadnych komend.
Pracujesz TYLKO przez:
- `mcp_github_get_file_contents` — odczyt plikow
- `mcp_github_create_or_update_file` — zapis raportu

### 🔄 Workflow tworzenia raportu

```
Nowy plik: create_or_update_file BEZ parametru sha
Aktualizacja: get_file_contents -> SHA -> create_or_update_file z sha
```

### 📝 Co szukac w plikach

- Czy gdziekolwiek jest `from core.yt_admin import` lub `import yt_admin`?
- Czy jest `yt_update` lub `update_youtube` jako flaga w pipeline?
- Gdzie w pipeline nastepuje krok po `update_post()` (injector) — to wlasnie tam podlaczyc YT

---

## Raportowanie po zakonczeniu

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`
2. `sonic-void (branch: master)/.agents/reports/inbox/2026-06-19_vse-analyst-04_yt-admin-integration-audit.md`

W raporcie podaj:
- Status integracji (czy wywolywany w pipeline — tak/nie + gdzie)
- Liste hardcodow do usuniecia z `yt_admin.py` (tabela: linia -> wartosc -> pole profilu)
- Plan dla dev (D6): co konkretnie zaimplementowac w jakim pliku

---

*Supervisor 01 | sonic-void | 2026-06-19 22:09*
