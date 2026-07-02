# Implementation Plan: System Kuponów Promocyjnych dla Stripe (VSE Komercjalizacja MVP)

## 1. Wnioski z analizy i rekomendacja architektoniczna

### Opcje wprowadzania kodów
Przeanalizowano dwa warianty obsługi kuponów rabatowych:
**Opcja A (Customowa walidacja):**
Frontend pyta o kupon -> Backend odpytuje Stripe o walidację -> Backend tworzy sesję Checkout ze sztywną zniżką (`discounts=[...]`). Wymaga modyfikacji UI, budowy formularzy i nowej logiki backendowej.

**Opcja B (Stripe-hosted Promotion Codes - REKOMENDOWANA):**
Wykorzystanie natywnego mechanizmu Stripe Checkout przez włączenie flagi `allow_promotion_codes=True`. Użytkownik klika "Wybierz plan" i wpisuje kod bezpośrednio w bezpiecznym oknie Stripe Checkout. 
*Zalety:* Zero logiki walidacji po naszej stronie. Stripe zarządza limitami (np. kody jednorazowe, wygasające). Nie wymaga dużych ingerencji w kod źródłowy. Nasz webhook `checkout.session.completed` odczyta sukces jak przy zwykłej transakcji.

### Kwestia bazy danych
**Brak konieczności modyfikacji modeli bazy danych.** 
Modele w `api/models/user.py` mapują tylko `plan_id` (np. `starter`, `pro`). Nasza logika nie zapisuje kwoty bazowej ani zniżki per użytkownik w lokalnej DB. Odbywa się to w 100% na poziomie platformy billingowej Stripe. Ponieważ polegamy na webhooku aktualizującym `user.plan_id`, bazy danych nie trzeba modyfikować by obsłużyć kody rabatowe. Śledzenie wykorzystania kodów będzie dostępne natywnie w Stripe Dashboard.

## 2. Plan Wdrożenia (Krok po Kroku)

### Krok 1: Modyfikacja backendu (FastAPI)
Włączamy natywne wsparcie promocji na ekranie Stripe Checkout.

**Plik:** `api/routers/payments.py`
**Zmiana:** W metodzie `create_checkout_session` (linia ok. 79), w konfiguracji zmiennej `session_kwargs` dodajemy flagę `allow_promotion_codes`.

```python
        session_kwargs: dict = {
            "mode": "subscription",
            "line_items": [
                {"price": plan.stripe_price_id, "quantity": 1}
            ],
            "success_url": f"{FRONTEND_URL}/platnosci/sukces?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{FRONTEND_URL}/cennik",
            "metadata": {
                "user_id": str(current_user.id),
                "plan_id": plan.id,
            },
            "allow_promotion_codes": True,  # <--- DODANA LINIA
            "customer_email": current_user.email
            if not current_user.stripe_customer_id
            else None,
        }
```

### Krok 2: Modyfikacja frontendu (Next.js) - UX Hint
Mimo że cały mechanizm odbywa się po stronie okna Stripe, warto poprawić UX, informując użytkowników na stronie cennika, że kod wpisuje się na następnym ekranie.

**Plik:** `web/src/app/cennik/page.tsx`
**Zmiana:** Dodaj krótki tekst informacyjny pod sekcją notatki "Free tier" (linia ok. 183):

```tsx
        {/* Promotion info hint */}
        <p className="text-center text-gray-500 text-xs mt-4">
          Masz kod rabatowy? Zrealizujesz go w bezpiecznym oknie płatności Stripe w następnym kroku.
        </p>
```

### Krok 3: Konfiguracja Stripe Dashboard (Operacyjne, nie kodowe)
Wdrożenie to wymaga następujących akcji biznesowych:
1. Skonfigurować **Coupons** w panelu Stripe (np. nazwa wewnętrzna "-20%").
2. Przypisać do nich **Promotion Codes** w panelu Stripe (np. widoczny kod `START20`).
3. (Opcjonalnie) Dla *Customer Portal*, aby pozwolić userom na aplikowanie zniżek także przy późniejszych upgrade/downgrade: W Stripe Dashboard -> Settings -> Billing -> Customer portal zaznaczyć opcję **"Customers can apply promotion codes"**.

## 3. Rozważania brzegowe (Edge Cases)
- **Kupon 100% zniżki:** Stripe wygeneruje fakturę z kwotą $0 / 0 PLN. Webhook przejdzie naturalnie i plan zostanie aktywowany.
- **Kody limitowane czasowo / ilościowo:** Jeśli kod wygaśnie, UI na ekranie Checkout natychmiast odrzuci próbę aplikacji. Do backendu VSE w ogóle nie dotrze zapytanie `create-checkout-session` z błędem, system jest stabilny z definicji.