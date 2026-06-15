# Raport: AGENTS.md Update — Ekosystem audit

**Agent:** sup-worker-01  
**Data:** 2026-06-15  
**Dispatch:** DISPATCH-SUP-WORKER-01-20260615-AGENTS-MD-UPDATE.md  
**Status:** ✅ Zamknięte

---

## Wyniki audytu

### Repo ze znalezionymi zmiankami (zaktualizowane)

| Repo | Branch | Problem | SHA commitu |
|---|---|---|---|
| `crimson-void` | main | CI wskazywało `run_recipe: deploy-backend (stellar-relay)` | `137d202` |
| `security-void` | main | PRIMARY = stellar-relay, FALLBACK = Wetty (odwrotna kolejność) | `af4de76` |
| `local-guardian` | master | `Target stellar-relay: local-pc (execute_command)` | `54bc0a0` |

### Repo już poprawne (nie zmieniano)

| Repo | Branch | Uwagi |
|---|---|---|
| `sonic-void` | master | Zaktualizowany 08.06.2026 — deprecated FILE BRIDGE, SSH primary |
| `video-seo-engine` | main | Zaktualizowany przez sup-worker-01 wcześniej, blokada VPS |
| `shadow-perihelion` | main | Zaktualizowany przez sup-worker-01 15.06.2026, pełna blokada |

### Repo bez AGENTS.md (OK — pominąć)

| Repo | Branch | Status |
|---|---|---|
| `axial-supernova` | master | Brak AGENTS.md — 404 |
| `social-publisher` | master | Brak AGENTS.md — 404 |
| `pressai-wp` | master | Brak AGENTS.md — 404 |
| `feed-crawler` | main | Brak AGENTS.md — 404 |
| `stellar-relay` | main | Brak AGENTS.md — 404 (repo jest infrastrukturą, nie zmieniano) |

---

## Zmiany wprowadzone

### crimson-void/AGENTS.md
- Sekcja Stack: `run_recipe: deploy-backend (stellar-relay)` → `SSH przez run_command → git pull && docker compose up -d --build`
- Dodano sekcję "DOSTĘP DO VPS — HIERARCHIA NARZĘDZI" z pelną tabelą priorytetów

### security-void/AGENTS.md
- Sekcja "Komunikacja i Dostęp VPS" przepisana całkowicie
- PRIMARY: SSH przez `run_command` | FALLBACK: Wetty | ARCHIW.: Stellar Relay
- Dodano przykład SSH na oracle-crimson

### local-guardian/AGENTS.md
- Usunięto `Target stellar-relay: local-pc (execute_command)`
- Zastąpiono: Środowisko = local-pc (Antigravity IDE — `run_command`)
- Zaktualizowano sekcję UAC: bridge → Antigravity IDE

---

*sup-worker-01 | sonic-void | 2026-06-15 21:58*
