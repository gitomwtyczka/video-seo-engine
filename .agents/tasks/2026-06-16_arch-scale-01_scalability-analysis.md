## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[arch-scale-01 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Opus (analiza architekturalna)

---

# TASK: arch-scale-01 — Scalability Analysis VSE

**Data:** 2026-06-16 (re-dispatch)  
**Dispatch from:** Supervisor 03  
**Uwaga:** Poprzednia sesja tego agenta zaparła raport — brak w inbox. Re-dispatch.

---

## Twój deliverable:
`ANALYSIS_scalability.md` — audyt skalowalności VSE pod kątem 1000 concurrent users.

**Gotowe raporty z równoległych sesji (możesz referencjować):**
- `2026-06-16_arch-sec-01_security-analysis-vse.md`
- `2026-06-16_arch-api-01_api-design.md`
- `2026-06-16_arch-saas-01_saas-patterns-analysis.md`

---

## Zakres analizy

Oceń VSE (FastAPI + Next.js + PostgreSQL + Docker + Local Runner) pod kątem:

1. **Database connection pooling** — czy asyncpg/SQLAlchemy jest prawidłowo skonfigurowany? Czy pool się wyczerpie przy 1k users?
2. **Async implementation** — czy endpointy są prawdziwie async czy blokują event loop?
3. **Statelessness** — czy API może być skalowane horyzontalnie? Czy jest shared state?
4. **Job queuing** — YouTube download + transcript pipeline. Czy jest kolejka? Czy może się zatkacć?
5. **Local Runner bottleneck** — single Windows machine. Co się dzieje przy 100+ jobów?
6. **Infrastructure** — single Oracle ARM node. Jak wyglądałby multi-node?

---

## Jak czytać kod

Repo: `gitomwtyczka/video-seo-engine`, branch: `main`

Kluczowe pliki do analizy:
- `backend/app/api/` — endpointy FastAPI
- `backend/app/core/database.py` — konfiguracja DB
- `backend/app/jobs.py` lub `backend/app/tasks.py` — pipeline jobów
- `local-runner/runner.py` — Windows runner
- `docker-compose.vse.yml` — infrastruktura

Użyj GitHub MCP `get_file_contents` do odczytu.

---

## Format raportu

```markdown
# ANALYSIS: Scalability — Video SEO Engine
**Analityk:** arch-scale-01  
**Data:** 2026-06-16

## Executive Summary
[1-3 zdania: skąd wychodzi błąd i co go naprawia]

## Bottlenecks (priorytetowane)
### 1. [Nazwa] — ́ CRITICAL / HIGH / MEDIUM
- Opis problemu
- Wymagany effort (story points / dni)
- Rekomendacja konkretna

## Rekomendacje architekturalne
[Konkretne kroki do skalowalności]

## Effort summary
[Co jest quick win a co big bang]
```

---

## Raport po wykonaniu

Wyślij do:
1. `video-seo-engine/.agents/reports/2026-06-16_arch-scale-01_scalability-analysis-vse.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_arch-scale-01_scalability-analysis-vse.md`

**Dual-write jest OBOWIĄZKOWY.** Bez raportu w inbox — sesja niewidoczna dla Supervisora.

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100` (jeśli potrzebne runtime checks)

---

## Protokół callsign (OBOWIĄZKOWE)

```
[arch-scale-01 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[arch-scale-01 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

---

*Supervisor 03 | sonic-void | 2026-06-16 18:13 | re-dispatch*
