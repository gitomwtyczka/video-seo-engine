# D8: Internal Links Fallback — Report

**Callsign:** vse-dev-24  
**Data:** 2026-06-20  
**Dispatch:** DISPATCH-VSE-DEV-24-20260620-INTERNAL-LINKS-D8  
**Status:** ✅ ZAKOŃCZONY  
**Commit:** `3a26aa48412182ead899bd84ea6db2c458955ab4`  

---

## Diagnoza

| Źródło | Status | Przyczyna |
|--------|--------|----------|
| SAAS API (crimson-void) | ❌ `top_pages: []` | GSC `not_connected` |
| Registry (data/prawy/registry/) | ❌ Pusty katalog | Brak danych |
| WordPress REST API | ✅ Działa | Publiczne, zwraca posty z `link` + `title` |

**Decyzja:** Opcja B — WordPress REST API self-sourcing jako fallback.

## Implementacja

### Zmiany w `api/services/pipeline.py`

1. **Nowa funkcja `_fetch_wp_internal_links()`**
   - Async (httpx), 10s timeout
   - `GET /wp-json/wp/v2/posts?per_page=15&orderby=date&status=publish&_fields=id,title,link`
   - Filtruje self-links (pomija posty z `video_id` w URL)
   - Max 10 linków
   - Graceful: timeout/error → pusta lista (pipeline continues)

2. **Step 0b (D8) w `run_generate()`**
   - Wywoływany PO SAAS enrichment (Step 0)
   - Aktywuje się TYLKO gdy `internal_links` z SAAS jest puste
   - Wstecznie kompatybilny z D9 (profile support)

3. **Import `httpx`** dodany na poziomie modułu

### Zachowana wsteczna kompatybilność
- Jeśli SAAS zwraca `top_pages` → używane (WP fallback nie aktywowany)
- Jeśli WP API niedostępny → pusta lista (pipeline działa jak dotychczas)
- Generator (`_build_saas_prompt_section`) i injector bez zmian

## Deploy

- VPS: `vse-api` rebuilt + restarted
- Container UP, API healthy
- HEAD: `3a26aa4 D8: internal links fallback via WP REST API [vse-dev-24]`

## Weryfikacja

D8 jest gotowy do działania — przy następnej generacji artykułu pipeline pobierze
10 ostatnich postów z prawy.pl i poda je do LLM jako propozycje linków wewnętrznych.
LLM wstawi 2-3 linki jeśli pasują tematycznie do materiału.

---

*vse-dev-24 | video-seo-engine | 20.06.2026*
