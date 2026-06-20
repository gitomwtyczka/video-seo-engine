# D6a Hotfix Report — yt_update_enabled flag + deprecated batch fix

**Dispatch:** VSE-DEV-20-D6a-HOTFIX  
**Agent:** vse-dev-20  
**Date:** 2026-06-20  
**Status:** ✅ COMPLETE  

---

## Cel

Natychmiastowy fix: każda publikacja na portalu bez OAuth (kurier365) generowała `EnvironmentError` w logach, zaśmiecając je i maskując prawdziwe błędy.

## Zmiany

### 1. `core/injector.py` — flaga `yt_update_enabled` (commit `b4a224b`)
- **CO:** Dodano sprawdzanie flagi `profile.get('yt_update_enabled', False)` przed wywołaniem yt_admin
- **PO CO:** Portale bez OAuth (kurier365) nie generują już EnvironmentError w logach
- **JAK:** Nowy warunek `yt_enabled = (profile or {}).get('yt_update_enabled', False)` przed blokiem YT update w `inject_video()`
- Domyślna wartość: `False` — bezpieczne dla nowych portali
- Komentarze docstring zaktualizowane (D6a)

### 2. `core/yt_admin.py` — fix deprecated batch call (commit `d0efe04`)
- **CO:** `batch_update_from_registry()` zmieniono z `update_video_description()` na `update_video_title_and_description()`
- **PO CO:** Optymalizacja quota — jedna operacja API zamiast dwóch
- **JAK:** Zmiana wywołania + update docstring + deprecation warning w starej funkcji
- `update_video_description()` zachowany z deprecation warning dla backward compat

### 3. Profile YAML — nowa flaga `yt_update_enabled`
- `profiles/prawy.yaml` → `yt_update_enabled: true` (commit `0278e63`)
- `profiles/kurier365.yaml` → `yt_update_enabled: false` (commit `714be2f`)
- `profiles/template.yaml` → `yt_update_enabled: false` (commit `db2d531`)
- Każdy wpis z pełną dokumentacją CO/PO CO/JAK

## Deploy

- VPS: `git pull` → `docker compose up -d --build vse-api`
- Container `vse-api` UP, health check: `{"status":"ok","version":"2.0.0","llm_default":"claude"}`

## Commits

| SHA | Opis |
|-----|------|
| `b4a224b` | D6a: gate YT update behind yt_update_enabled profile flag |
| `d0efe04` | D6a: fix deprecated batch call → update_video_title_and_description |
| `0278e63` | D6a: add yt_update_enabled: true to prawy.yaml |
| `714be2f` | D6a: add yt_update_enabled: false to kurier365.yaml |
| `db2d531` | D6a: add yt_update_enabled: false to template.yaml |

## Weryfikacja

- [x] `kurier365` pipeline: YT update NIE jest wywoływany (yt_update_enabled: false)
- [x] `prawy` pipeline: YT update wywoływany tylko gdy yt_update_enabled: true
- [x] `batch_update_from_registry()` używa `update_video_title_and_description`
- [x] Serwis działa po deploy (container UP, health OK)

---

*vse-dev-20 | video-seo-engine | 2026-06-20*
