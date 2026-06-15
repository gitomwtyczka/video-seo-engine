# Raport — VPS Access Cleanup
**Agent:** sup-worker-01  
**Data:** 2026-06-15  
**Status:** ✅ ZAKOŃCZONY

## Zakres

Usunięcie z konfiguracji agentów i dispatchy mechanizmów dostępu do VPS:
- stellar-relay / file bridge
- Wetty (browser_subagent terminal VPS)
- SSH / PowerShell SSH
- Bloki bash z komendami VPS

## Zmiany

### video-seo-engine (branch: main)

| Plik | Co zmieniono | Commit SHA |
|------|-------------|------------|
| `AGENTS.md` | Dodano sekcję `⛔ DOSTĘP DO VPS — ZAKAZ W SESJACH PROJEKTOWYCH` po sekcji KROK 0 | `e68c5bae` |
| `.agents/tasks/DISPATCH-VSE-DEV-03-20260615-DASHBOARD-UI.md` | Usunięto sekcję DEPLOY WORKFLOW z bash VPS (git reset, docker compose), dodano blokadę narzędzi, dodano `[Deploy po sesji — zgłoś Supervisorowi]` | `ac222a66` |
| `.agents/tasks/DISPATCH-VSE-STRATEG-01-20260615-P2-ONLY.md` | Usunięto Krok 2 (bash echo .env na VPS) i Krok 3 (docker compose rebuild bash), zastąpiono `[Deploy po sesji — zgłoś Supervisorowi]`, dodano blokadę narzędzi | `dfbd1ab8` |

### shadow-perihelion (branch: main)

| Plik | Co zmieniono | Commit SHA |
|------|-------------|------------|
| `AGENTS.md` | Zastąpiono sekcję `🖥️ Dostęp do serwerów` pełną blokadą VPS (nie SSH, nie Wetty, nie stellar-relay) | `f78ddf0b` |
| `.agents/tasks/DISPATCH-SHADOW-DEV-01-20260613-PRAWYTV-FIX.md` | Usunięto sekcje `0b. Heartbeat` z bash, `Krok 1-4` z SSH/docker exec, zastąpiono diagnostyką przez publiczne endpointy + GitHub MCP | `8f725018` |
| `.agents/tasks/DISPATCH-FLEET-ANALYST-SOCIAL-SHARE-20260611.md` | Usunięto sekcję `SSH do serwera` z komendami SSH, dodano blokadę narzędzi | `1c077bd0` |

## Pominięte

| Plik | Powód |
|------|-------|
| `video-seo-engine/.agents/tasks/DISPATCH-VSE-ARCH-01-20260614-DOCS.md` | Brak bloków bash VPS — tylko curl https:// do publicznych endpointów, nie wymagał zmian |
| Dispatche shadow-perihelion z datą przed 2026-06-10 | Stare dispatche (kwiecien-maj), prawdopodobnie zakończone — nie modyfikujemy historycznych |

## Zasada docelowa (potwierdzona)

Agenci projektowi nie widzą żadnych narzędzi VPS w kontekście sesji.
Jeśli naprawdę potrzeba VPS — osobna sesja deploy, osobny dispatch, świadoma decyzja.
