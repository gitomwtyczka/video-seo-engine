# Raport: Hotfix P0 (jobs.py + dashboard-inner.tsx)
**Data:** 2026-07-02
**Wykonawca:** vse-dev-01
**Status:** Zakończone, Pushnięte do main, Oczekuje na GO

## Zmiany w `api/routers/jobs.py` (Fix 1A, 1B, 1C)
- Przywrócono filtr admina w `get_job_history`.
- Usunięto wadliwy, duplikujący się blok sprawdzania `current_user.is_admin` z `complete_job` (całkowicie).
- Usunięto zduplikowane bloki (pozostawiono pojedyncze) z `get_job` oraz `get_job_vtt`.

## Zmiany w `web/src/app/dashboard/dashboard-inner.tsx` (Fix 2)
- Zaktualizowano zmienną `isPro`, by uwzględniała fallback na `session.user.plan` w przypadku błędu API (gdy `userProfile == null`). Zastąpiono tymczasowy kod docelowym kodem z dispatcha.

⚠️ **Odnotowane trudności operacyjne**: 
Próby zastosowania zmian bezpośrednio poprzez `GitHub MCP` z argumentem `content` zostały zatrzymane przez ograniczenia limitów tokenów dla wielkich plików (dashboard.tsx = 77 KB). Zastosowano dozwoloną piaskownicową ścieżkę awaryjną: edycja przez narzędzia plikowe (`replace`) + git push.

Oczekuję na weryfikację i GO do wdrożenia. 