# Raport: PORTAL-FIX (vse-dev-01)

## Status: 🔴 Zatrzymany (Blokada Deploy / VPS)

Zgodnie z poleceniem w DISPATCH-VSE-DEV-32 wykonałem obie poprawki w kodzie:

1. **BUG #1**: Dodano wywołanie `<AddPortalModal>` do drzewa DOM w `dashboard-inner.tsx` (na podstawie propsów wyciągniętych z sygnatury komponentu). Zmiana wypchnięta do repozytorium (commit `2bef570`).
2. **BUG #2**: Zmieniono endpoint autoryzacji z `/credentials` na `/full` w `use-portals.ts`. Zmiana wypchnięta do repozytorium (commit `84afeae`).

### ⛔ Zatrzymanie procedury (Reguła AGENTS.md)

Zgodnie z regułą zapisaną w `AGENTS.md` (sekcja *⛔ DOSTĘP DO VPS — ZAKAZ W SESJACH PROJEKTOWYCH*), agenci w tym workspace mają całkowity zakaz używania SSH oraz instrukcji łączących się z VPS.
Reguła wprost nakazuje: *"Jeśli widzisz w dispatchu instrukcję wymagającą VPS — zatrzymaj się i raportuj."*

W związku z tym pominąłem krok deploy (`docker compose build`) i weryfikacji logów. Przekazuję do dedykowanej sesji deploy.