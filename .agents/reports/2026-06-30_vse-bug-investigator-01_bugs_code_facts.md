# Raport z zebrania kodu dla 3 bugów (FAZA 1)
**Agent:** vse-bug-investigator-01 | **Data:** 2026-06-30 22:32

Zgodnie z poleceniem zebrałem kod (bezpośrednio przez GitHub MCP z brancha `main`) z wskazanych plików w celu dalszej analizy przez model Claude Sonnet. Poniżej przedstawiam konkretne fakty ze znalezionego kodu:

## Fakty z pobranego kodu

### BUG-1: Plan wraca do FREE po odświeżeniu strony (Race condition w Stripe)
- **Pliki:** `api/routers/payments.py` (webhook)
- **Fakty:**
  - W funkcji `_handle_subscription_deleted(subscription: dict, db: AsyncSession)` agent znajduje użytkownika bazując jedynie na `customer_id`.
  - Po znalezieniu, wywołuje _na ślepo_: 
    ```python
    user.plan_id = "free"
    user.stripe_subscription_id = None
    ```
  - **Brak walidacji ID:** Endpoint nie sprawdza, czy `subscription.get("id")` (czyli anulowana/usunięta subskrypcja) pokrywa się z `user.stripe_subscription_id`! Oznacza to, że jeśli usunięto starą subskrypcję chwilę po utworzeniu nowej, użytkownik zostaje zdegradowany do FREE, mimo że ma już aktywną nową subskrypcję.

### BUG-2: Nie można dodać portalu
- **Pliki:** `api/routers/portals.py`
- **Fakty:**
  - W endpointcie `POST /v1/portals` w ogóle nie ma kodu backendowego odpytującego bazę o limity z planu (`wp_sites_limit`). Nie jest rzucany żaden backendowy błąd z tego powodu wewnątrz `portals.py`.
  - Prawdopodobnie blokada jest nałożona po stronie klienta (UI/frontend sprawdza czy plan zezwala na dodanie portalu, i jeśli plan == free [skutek BUG-1], rzuca błędem). Albo brakuje logiki weryfikacyjnej na backendzie, a błąd, który widział user, pochodził z innego miejsca (np. walidacji przed requestem).

### BUG-3: Historia pokazuje joby WSZYSTKICH użytkowników
- **Pliki:** `api/routers/jobs.py`
- **Fakty:**
  - Endpoint `@router.get("/history")` aktualnie nie wykorzystuje mechanizmu pobierania zalogowanego usera — brakuje parametru np. `current_user: User = Depends(get_current_user)`.
  - SQL query pobiera wszystko jak leci:
    ```python
    result = await db.execute(
        select(TranscriptJob)
        .order_by(desc(TranscriptJob.created_at))
        .offset(offset)
        .limit(limit)
    )
    ```
  - Jest jawny komentarz w kodzie zostawiony przez programistę: `Nie filtruje po user_id — w MVP jest jeden użytkownik (Admin/Agency). W przyszłości: filtrowanie po user_id z JWT tokenu.`

---
*Kod źródłowy został zbadany i znajduje się teraz w kontekście konwersacji. Gotowy do przejęcia i zaprojektowania fixa (Faza 2).*