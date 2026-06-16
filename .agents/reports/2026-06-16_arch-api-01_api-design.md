# Raport: Analiza API Design — Video SEO Engine

**Callsign:** arch-api-01  
**Data:** 2026-06-16  
**Commit output:** 0ac9da2a1f3172eb2f5da6be13d9a9540c6b444c  
**Output:** `docs/ANALYSIS_api_design.md`

---

## TL;DR — Kluczowe Odkrycia

### 🔴 KRYTYCZNE
1. `POST /v1/generate` i `POST /v1/inject` bez auth — publiczne endpointy!
2. Quota enforcement brak — `quota.py` istnieje ale nie używane w generate.py
3. API keys CRUD brak — tabela jest, endpointy nie

### 🟡 WYSOKI (inter-SaaS)
4. Brak M2M auth (X-API-Key) — blokuje integrację z crimson-void
5. Niespójny error format — każdy endpoint inaczej
6. Brak webhooków — crimson-void musi pollować

### 🟢 NISKI
- N+1 query w admin/users
- Akcje w URL (tech debt)
- OpenAPI SecurityScheme display

## Rekomendacje

| Sprint | Zadania |
|--------|--------|
| Sprint 1 | Auth, quota, api-keys CRUD |
| Sprint 2 | Error format, M2M test, crimson-void kontrakt |
| Sprint 3 | Webhooks |

*arch-api-01 | video-seo-engine | 2026-06-16 | raport kompletny*
