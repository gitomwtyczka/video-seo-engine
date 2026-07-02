# Raport diagnostyczny: Brak możliwości usuwania użytkowników z panelu administratora

**Data:** 2026-07-02
**Agent:** vse-analyst-01

## 1. Diagnoza problemu
Zgłoszony błąd projektowy wynika z faktu, że w systemie całkowicie brakuje mechanizmu usuwania użytkownika — zarówno na poziomie API, jak i interfejsu panelu administratora.

### Analiza Backend (API)
- W pliku `api/routers/admin.py` nie zdefiniowano endpointu `DELETE /v1/admin/users/{user_id}`. Obecnie istnieje tam tylko pobieranie listy, detali oraz modyfikacja planu (PATCH).
- W pliku `api/models/user.py` relacje modelu `User` nie są w pełni przygotowane na bezpieczne usunięcie kaskadowe. Zdefiniowano:
  `usage_logs = relationship("UsageLog", back_populates="user")`
  `api_keys = relationship("ApiKey", back_populates="user")`
  `portals = relationship("WpPortal", back_populates="user", cascade="all, delete-orphan")`
  
  Próba usunięcia użytkownika za pomocą `session.delete(user)` przy obecnym stanie spowoduje błąd integralności bazy danych (`IntegrityError`), ponieważ brakuje kaskadowego usuwania w powiązaniach z `usage_logs` oraz `api_keys`.

### Analiza Frontend (UI)
- Plik: `web/src/app/admin/page.tsx`
- W tabeli użytkowników, w ostatniej kolumnie "Akcje", znajduje się wyłącznie przycisk "Zmień plan".
- Brak przycisku usuwania oraz brak wspierającego modala z potwierdzeniem akcji usunięcia (co jest niezbędne przy operacjach destruktywnych).

## 2. Plan wdrożenia (Lista zadań)

**Zadanie 1: Aktualizacja modelu bazy danych**
- Plik: `api/models/user.py`
- Dodanie `cascade="all, delete-orphan"` do relacji `usage_logs` oraz `api_keys` w klasie `User`, aby usunięcie konta automatycznie czyściło jego historię logów użycia i klucze API.

**Zadanie 2: Dodanie endpointu DELETE w API**
- Plik: `api/routers/admin.py`
- Zdefiniowanie endpointu `@router.delete("/users/{user_id}")`.
- Weryfikacja po stronie serwera czy konto istnieje, wykonanie `await db.delete(user)`, potem `await db.commit()` i ewentualnie odświeżenie/zwrot statusu sukcesu.

**Zadanie 3: Rozbudowa panelu Admina w UI**
- Plik: `web/src/app/admin/page.tsx`
- Dodanie przycisku "Usuń" obok przycisku "Zmień plan" w rzędzie tabeli użytkowników.
- Stworzenie komponentu `DeleteUserModal` wymuszającego świadome potwierdzenie akcji usunięcia (aby zabezpieczyć przed przypadkowym skasowaniem).
- Integracja modala z nowym endpointem API (obsługa błędu, sukcesu oraz odświeżenie widoku/listy po usunięciu).
