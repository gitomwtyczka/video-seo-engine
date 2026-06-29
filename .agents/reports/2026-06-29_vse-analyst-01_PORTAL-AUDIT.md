# Raport Analityczny: Portal Management Audit
Data: 2026-06-29
Callsign: vse-analyst-01
Zadanie: DISPATCH-VSE-ANALYST-11-20260629-PORTAL-AUDIT

## 1. Dlaczego opcja "Dodaj nowy portal" nie działa na produkcji?
Po audycie frontendu (`web/src/app/dashboard/dashboard-inner.tsx`) stwierdzono, że problem wynika z braku wyrenderowania komponentu modala w drzewie DOM.

- **Przyczyna:** Wybór opcji `+ Dodaj nowy portal` z dropdownu zmienia stan lokalny `showAddPortalModal` na `true` (linie 1079 oraz 1094). Komponent `<AddPortalModal>` faktycznie istnieje i jest zdefiniowany w tym pliku (linie 658-818).
- **Błąd:** W głównym `return` komponentu `DashboardInner` (od linii 980 do końca) **nie umieszczono** wywołania `<AddPortalModal>`. Jest tam tylko warunek dla `<InjectModal>` (linie 1462-1469).
- **Rozwiązanie (dla zespołu dev):** Należy dodać warunkowe renderowanie `<AddPortalModal>` na samym końcu funkcji `DashboardInner`, pod komentarzem `/* Inject Modal */`. Przykład:
  ```tsx
  {showAddPortalModal && (
    <AddPortalModal
      onClose={() => setShowAddPortalModal(false)}
      onSuccess={(portalId) => {
        setShowAddPortalModal(false)
        setSelectedPortalId(portalId)
      }}
    />
  )}
  ```

## 2. Dlaczego endpoint pobierający hasło aplikacji (credentials) zwraca 404?
Zgodnie z wymaganiami przeprowadzono analizę pliku `api/routers/portals.py` oraz `web/src/app/dashboard/use-portals.ts`.

- **Przyczyna (Mismatch Endpointów):**
  - Frontend (`use-portals.ts`, l. 67) próbuje pobrać hasło z adresu `/v1/portals/${portalId}/credentials`.
  - Backend (`api/routers/portals.py`, l. 173) eksponuje ten zasób pod adresem `@router.get("/{portal_id}/full")`.
- **Zgodność z modelem:** Plik ORM (`api/models/portal.py`) prawidłowo używa `uuid` dla id, oraz zawiera pole `profile_id`. Definicje modeli Pydantic w `portals.py` (np. `PortalFull`, `PortalResponse`) prawidłowo odbijają ten stan. Sama konstrukcja modeli nie jest problemem.
- **Rozwiązanie (dla zespołu dev):** Wystarczy zmienić zapytanie fetch w `use-portals.ts` z `/v1/portals/${portalId}/credentials` na `/v1/portals/${portalId}/full`. Backend funkcjonuje prawidłowo.

## Podsumowanie
Dwa krytyczne błędy blokujące zarządzanie portalami mają charakter powierzchowny. Nie ma problemów z architekturą ORM ani strukturą stanu React — błędy to wyłącznie literówka w nazwie endpointu i przeoczenie dopisania znacznika do widoku. Zaplanowane poprawki w kodzie powinny zająć minimum czasu. (Przeanalizowano również, że błąd wkradł się w trakcie implementacji z DISPATCH-03A/B, gdzie skupiono się na logice API, gubiąc renderowanie modala na frontendzie).
