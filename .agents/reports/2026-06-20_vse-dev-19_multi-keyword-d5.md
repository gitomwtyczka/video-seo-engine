# D5: Multi-keyword RankMath + Google Trends

**Dispatch:** DISPATCH-VSE-DEV-19-20260619-MULTI-KEYWORD-D5  
**Agent:** vse-dev-19  
**Data:** 2026-06-20  
**Status:** ✅ DONE

---

## CO zrobiono

Zintegrowano Google Trends keywords z pipeline'em VSE i rozszerzono RankMath
focus_keyword z 1 frazy na max 5 (GSC + Trends + LLM), zgodnie ze specyfikacją D5.

## Zmiany (cross-repo)

### crimson-void: `backend/routers/external.py` — commit `4d007a2`
- `_fetch_trends_keywords(topic)` — pytrends PL, top 5, graceful
- `trends_keywords: list[str]` dodane do response `/api/external/seo-data`

### video-seo-engine commits:
- `38388e7` saas_enricher: propaguje `trends_keywords`, helper `extract_trends_keywords()`
- `d92a86c` generator: prompt `focus_keyphrases` (lista), `_normalize_keyphrases()` backward compat
- `1a58965` injector: `build_focus_keywords()` merge GSC+Trends+LLM → max 5 → comma-sep
- `7eb8567` pipeline: `saas_data` flow-through do `inject_video()` i `_create_wp_post()`

## Deploy
- ✅ crimson-void backend restarted
- ✅ vse-api rebuilt + restarted
