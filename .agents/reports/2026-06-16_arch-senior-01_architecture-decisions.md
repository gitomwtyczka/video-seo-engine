# Raport: Architecture Decisions & Roadmap VSE

**Agent:** `arch-senior-01`  
**Data:** 2026-06-16  
**Task:** Synteza 4 raportów analitycznych → ADR + roadmap techniczny  
**Commit:** `2821a03` — `docs/ARCHITECTURE_decisions.md`

---

## Wykonano

- ✅ Przeczytano 4 raporty analityczne: ANALYSIS_security.md, ANALYSIS_api_design.md, ANALYSIS_saas_patterns.md, ANALYSIS_scalability.md
- ✅ Stworzono `docs/ARCHITECTURE_decisions.md` (10 ADR + roadmap P0–P4 + czerwone linie)
- ✅ Odpowiedziano na 5 pytań strategicznych (P1–P5)

---

## Kluczowe Wnioski (CEO Summary)

### 🔴 KRYTYCZNE — do natychmiastowego wdrożenia

1. **Auth na generate/inject/process/sitemap** — te 4 endpointy są publicznie dostępne. Koszt: anonimowy klient może wywoływać Claude API bez ograniczeń. Fix: 2h.

2. **JWT_SECRET_KEY fail-fast** — aplikacja startuje z kluczem `"CHANGE_ME_IN_PRODUCTION"` jeśli env nie jest ustawiony. Fix: 5 minut.

3. **Rate limit na auth endpoints** — brak ochrony przed brute-force i credential stuffing. Fix: nginx config, 1h.

### 🟠 P0/P1 — Sprint 1 (tydzień 1)

- IDOR fix w jobs.py (weryfikacja ownership)
- OAuth one-time code (tokeny nie w URL — OWASP A02)
- Composite index usage_logs (DB performance @ scale)
- SKIP LOCKED w jobs pickup (multi-runner readiness)
- Runner health check + cleanup stale jobs (SPOF mitigation)
- Uvicorn workers 2→4 + DB pool hardening

### 🟡 P2 — Sprint 2 (tydzień 2)

- API key CRUD + X-API-Key auth (crimson-void M2M)
- Response envelope standaryzacja (API contract stability)
- Quota enforcement (business logic)

### 🟢 P3–P4 — Dalej

- Stripe billing (P3, ~16h)
- Email verification (P3)
- 2. runner na innym IP (P3)
- Redis cache LLM / PgBouncer (P4, przy >500 users)

---

## Czerwone Linie

- NIE otwierać user acquisition przed auth na generate/inject
- NIE migrować do Celery/Redis (PostgreSQL SKIP LOCKED wystarczy)
- NIE zmieniać URL versioning (/v1/)
- NIE K8s przed >500 paying users

---

## Otwarte Pytania do Supervisora

1. Czy są zewnętrzni klienci API poza crimson-void? — decyduje o ADR-09 (envelope standaryzacja teraz vs adapter)
2. Czy możemy dedykować VPS na 2. runner? (~$5-10/mies) — blokuje skalowanie Local Runner
3. Kiedy monetyzacja? Jeśli <30 dni — billing do P1

---

*arch-senior-01 | video-seo-engine | 2026-06-16*
