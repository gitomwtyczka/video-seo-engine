# Raport: Fix Dashboard Portal Dropdowns & DB Datatypes
**Data:** 2026-06-30
**Callsign:** vse-dev-01

## Cel
Wdrożenie poprawek naprawiających błędy z `portal_id` (zdiagnozowane w RCA), w tym migracja bazy danych i usunięcie rzutowania w kodzie frontendu.

## Zrealizowane kroki (CO i JAK)
1. **Frontend (vse-web)**: Usunięto rzutowanie `parseInt(selectedPortalId, 10)` z komponentu `dashboard-inner.tsx`. Dzięki temu wartości tekstowe (`biznesciti`, itp.) nie stają się `NaN`, a w JSONie jako `null`. Typowanie TypeScript działa poprawnie.
2. **Backend (vse-api)**: Zaimplementowano ręczną migrację DDL do skryptu bazy danych `api/migrate.py`:
   `ALTER TABLE transcript_jobs ALTER COLUMN portal_id TYPE VARCHAR(50);`
3. **Deploy (Produkcja)**: Za pomocą SSH zbudowano nowo zatwierdzone obrazy dockera dla `vse-api` i `vse-web`, uruchomiono je (`docker compose up -d`) oraz wykonano skrypt migracji w uruchomionym kontenerze (`python -m api.migrate`). Migracja poprawnie zaktualizowała typ kolumny na serwerze.
4. **Weryfikacja**:
   Wykonano testy End-To-End poprzez skrypt `api_smoke_test.py` operujący na produkcji `https://vse.impresjapr.pl`. Analiza logów API produkcyjnego za pomocą SSH po testach potwierdziła, że:
   - Żądanie `generate` z nowym profilem tekstowym `biznesciti` kończy się **sukcesem** i zapisuje wygenerowane dane do bazy. Eliminuje to krytyczny błąd HTTP 500 (`DataError: InvalidTextRepresentation`).
   - Żądanie `generate` testujące profil niesłownikowy eliminuje błąd walidacji schemy HTTP 422 (`int_parsing`), dopuszczając identyfikatory w formie tekstowej.

## Wynik (PO CO)
Poprawki likwidują blokadę generowania treści na portale. Klienci agencyjni mogą teraz tworzyć inline i wybierać nowe portale bez wywołania błędów walidacji i wyjątków bazodanowych.

Zadanie wykonane i wdrożone na produkcję z sukcesem.
