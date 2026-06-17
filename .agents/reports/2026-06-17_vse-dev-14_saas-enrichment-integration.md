# Raport: SAAS Enrichment Integration — VSE ↔ SAAS

**Od:** vse-dev-14  
**Do:** Supervisor 01  
**Data:** 2026-06-17 17:28  
**Temat:** DISPATCH-VSE complete — SAAS enrichment zintegrowany z pipeline, deploy na VPS

---

## TL;DR

✅ **Kod gotowy i wdrożony.** 3 commity, 3 pliki zmienione, deploy na VPS.
⚠️ **BLOCKER SAAS-side:** GSC API zwraca 403 dla prawy.pl — brak uprawnień OAuth.
Pipeline działa poprawnie z fallbackiem (puste dane → artykuł bez wzbogacenia).

---

## Co zrobiono

### 1. Nowy moduł: `api/services/saas_enricher.py` (commit `3fa8ef7`)
- `get_saas_seo_data()` — async HTTP GET do SAAS `/api/external/seo-data`
- Cache w pamięci 30 min (TTL dict + timestamp)
- Graceful degradation: timeout, connection refused, HTTP != 200 → puste dane
- `extract_priority_keywords()` — top N fraz wg clicks desc
- `extract_internal_links()` — top pages jako propozycje linków wewnętrznych

### 2. Modyfikacja: `core/generator.py` (commit `363130a`)
- `generate_seo_v4()` — nowe parametry: `priority_keywords`, `internal_links`
- `_build_saas_prompt_section()` — buduje sekcję promptu z danymi GSC
- Jeśli brak danych → pusty string (prompt bez zmian)
- `process_video()` — metadata `saas_enriched: true/false` w wyniku

### 3. Modyfikacja: `api/services/pipeline.py` (commit `32fc3df`)
- `_fetch_saas_enrichment()` — wrapper z try/except
- `run_generate()` — **Step 0** przed generowaniem: pobierz dane z SAAS

### 4. Deploy VPS
- `.env`: `SAAS_API_URL=http://172.17.0.1:8001` (Docker bridge gateway)
- Health check: `{"status":"ok","version":"2.0.0"}`

---

## BLOCKER: GSC Permission (SAAS-side)

SAAS endpoint zwraca 502: `HttpError 403: User does not have sufficient permission for site 'https://prawy.pl/'`

**Kto naprawia:** crimson-dev — dodanie prawy.pl do GSC property + OAuth.
**VSE gotowy:** po naprawieniu GSC enrichment zadziała automatycznie.

---

## GOTCHA #10: Docker inter-container networking

| Problem | Fix |
|---|---|
| `localhost:8001` z kontenera VSE = Connection refused | `172.17.0.1:8001` (Docker bridge) |
| `docker restart` nie przeładowuje env_file | `docker compose down && up` |

---

## Commity

| SHA | Opis |
|---|---|
| `3fa8ef7` | feat: add saas_enricher.py |
| `363130a` | feat: generator accepts priority_keywords + internal_links |
| `32fc3df` | feat: pipeline integrates SAAS enrichment Step 0 |

---

*[vse-dev-14 | video-seo-engine 17.06.2026 17:28] raport kompletny*
