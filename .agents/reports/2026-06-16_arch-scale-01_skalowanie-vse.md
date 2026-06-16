# Raport: Analiza Skalowalności VSE

**Callsign:** `arch-scale-01`  
**Data:** 2026-06-16  
**Status:** ✅ Kompletny  
**Dokument:** `docs/ANALYSIS_scalability.md` (commit `fc628c7`)

## Krytyczne bottlenecki znalezione:
1. LLM call 50s bez timeout/retry — eksploduje przy 50 concurrent users
2. Local Runner SPOF — brak health check, brak SKIP LOCKED
3. Brak rate limitingu na /v1/generate
4. Brak composite indexu usage_logs — seq scan przy dużej tabeli
5. Uvicorn 2 workers (za mało na 4-core ARM)

## Quick Wins gotowe do dispatchu (QW1-QW5 = ~80 min):
- Dockerfile: workers 2→4
- db.py: pool_pre_ping + pool_recycle
- models/user.py: composite index usage_logs
- Rate limiting slowapi
- SELECT FOR UPDATE SKIP LOCKED w jobs queue

*arch-scale-01 | 2026-06-16 — raport kompletny*
