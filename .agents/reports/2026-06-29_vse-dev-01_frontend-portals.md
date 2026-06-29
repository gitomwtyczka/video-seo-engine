# Raport: Frontend Portals (DISPATCH-VSE-DEV-20260629-03B)

**Callsign:** vse-dev-01
**Data:** 2026-06-29
**Status:** Zakończone

## CO
Przepisano główny widok DashboardInner oraz InjectModal i zintegrowano z nowym API portali (w tym POST /v1/portals przez nowy komponent AddPortalModal). Zaktualizowano hook use-portals.ts.

## PO CO
Portal uczy się pobierać portale z bazy danych uzytkownika zamiast korzystać z localStorage i hardkodowanego formularza w InjectModal. To kluczowe dla funkcji Pro/Agency (wiele portali).

## JAK
- Usunięto logikę legacyProfile bazującą na hooku profilu w dashboard-inner.tsx.
- Wprowadzono listę portali z usePortals (fetch GET /v1/portals).
- Przy opcji publikacji pojawia się modal wyboru portalu. Formularz ręczny dostępny jako opcja dodatkowa.
- Nowe portale zapisywane są bezpośrednio przez API (POST /v1/portals) via AddPortalModal.
- Wywołano publikację kodu w remote (main).

**Commity:**
- Refactor dashboard for DB portals frontend (DISPATCH-03B) [[vse-dev-01]] (f492a8b)
- Update use-portals.ts for payload [[vse-dev-01]] (44737ea)

**Następne kroki:**
- Zdeployować branch main na środowisko VPS (Nginx / Next.js) i zweryfikować działanie integracji backend <-> frontend po naprawionych trasach /v1.
