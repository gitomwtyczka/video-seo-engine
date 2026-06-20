# D6b Architecture Report — vse-dev-21

**Data:** 2026-06-20
**Callsign:** vse-dev-21
**Dispatch:** DISPATCH-VSE-DEV-21-20260620-ARCHITECTURE-D6b.md
**Status:** ✅ KOMPLETNY

---

## Co zostało zrobione

Pełna implementacja D6b — refaktor architektury z modelu 1:1 (portal=kanał) na model 1:N (jeden kanał YT → wiele witryn).

## Commity

| Krok | Plik | Commit | Opis |
|---|---|---|---|
| D6b.1 | `channels/prawy-tv.yaml` | `11a6f91` | Nowy plik konfiguracji kanału YT |
| D6b.3 | `core/config_utils.py` | `126c38b` | Shared env var resolution |
| D6b.3 | `core/channel.py` | `ec26782` | Channel loader z backward compat |
| D6b.2 | `profiles/prawy.yaml` | `c065108` | Usunięte dane kanału, dodane source_channels |
| D6b.2 | `profiles/kurier365.yaml` | `44d9acc` | Usunięte dane kanału, dodane source_channels |
| D6b.2 | `profiles/template.yaml` | `2cd35ef` | Zaktualizowany template |
| D6b.2 | `core/profile.py` | `b4d5bc3` | Import config_utils, backward compat |
| D6b.4+5 | `core/yt_admin.py` | `4641def` | Parametryzacja channel dict + key moments |
| D6b.6 | `core/generator.py` | `188f888` | publication_type (3 typy artykułów) |
| D6b.7 | `api/models/request.py` | `6e7391c` | publication_type w request models |
| D6b.7 | `api/routers/generate.py` | `007ac99` | Passing publication_type to pipeline |
| D6b.7 | `api/services/pipeline.py` | `43e849c` | Threading publication_type through |
| D6b.8 | `tools/oauth_setup.py` | `3c97826` | OAuth refresh_token generator |

## Kluczowe zmiany architektoniczne

1. **Nowy katalog `channels/`** — konfig kanałów YT oddzielony od profili witryn
2. **`core/config_utils.py`** — shared `resolve_env_vars()` + `load_yaml_file()` (zamiast duplikacji)
3. **`core/channel.py`** — `load_channel()`, `get_channel_for_profile()`, `get_default_publication_type()` 
4. **Profile witryn** — `source_channels` mapowanie zamiast inline `yt_oauth`
5. **yt_admin.py** — każda publiczna funkcja akceptuje `channel: Optional[dict]`
   - Footer, hashtags, categoryId z channel config zamiast hardcoded
   - Fallback env vars jeśli channel=None (backward compat)
   - Nowa `_build_key_moments()` — cytaty z timestamps w opisie YT
6. **generator.py** — `publication_type` parameter (full_analysis / watching_page / discover)
   - Prompt overrides per typ artykułu
7. **API pipeline** — `publication_type` threaded: request → router → pipeline → generator

## Weryfikacja

- ✅ Deploy na VPS — `docker compose up -d --build`
- ✅ `/health` → `{"status": "ok", "version": "2.0.0"}`
- ✅ Channel loader: `load_channel("prawy-tv")` → poprawny dict
- ✅ `list_channels()` → `['prawy-tv']`
- ✅ Backward compat: stary kod bez `channel` param działa (fallback env vars)

## Co nie zostało zrobione (poza scopem D6b)

- **D6b.extra** (thumbnail filename fix w injector.py) — pominięty, niski priorytet
- Monitor.py integration — wymaga osobnej sesji (naturalny flow: profile → get_channel_for_profile → channel dict)

---

*vse-dev-21 | video-seo-engine | 2026-06-20 19:50-20:05 | raport kompletny*
