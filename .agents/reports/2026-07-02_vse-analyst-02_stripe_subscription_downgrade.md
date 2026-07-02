# Raport z analizy: Wygasanie subskrypcji Stripe i cykl życia użytkownika

## 1. Analiza webhooków Stripe
Integracja ze Stripe znajduje się w pliku `api/routers/payments.py`. Logika opiera się na webhookach (`POST /v1/payments/webhook`), które aktualnie obsługują 4 główne eventy:
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

## 2. Diagnoza problemu braku downgrade'u (do planu 'free')
Użytkownicy nie tracą płatnego planu w systemie, mimo że subskrypcja teoretycznie wygasa/jest anulowana. Zlokalizowałem dwa główne powody:

1. **Brak weryfikacji statusu (`subscription.status`)**: Funkcja `_handle_subscription_updated` (linia 223 w `payments.py`) odczytuje identyfikator cennika (`price_id`) i na tej podstawie przypisuje użytkownikowi płatny plan. Proces ten CAŁKOWICIE ignoruje status subskrypcji! Oznacza to, że jeśli subskrypcja przejdzie w status `past_due` (brak środków) lub `unpaid`, webhook `updated` po prostu przypisze konto z powrotem do planu `pro`, bo widzi odpowiedni `price_id`.
2. **Race condition przy anulowaniu**: Kiedy subskrypcja zostaje finalnie skasowana, Stripe wysyła webhook `customer.subscription.deleted`. Ta funkcja (`_handle_subscription_deleted`) poprawnie wykonuje downgrade do `free`. Niestety, w tym samym czasie asynchronicznie Stripe emituje event `customer.subscription.updated` (ze statusem `canceled`). Jeżeli webhook `updated` przetworzy się ułamek sekundy *po* zdarzeniu `deleted`, funkcja `updated` znów dostrzeże `price_id` i ponownie przypisze użytkownikowi płatny plan, nadpisując "free".

Event `invoice.payment_failed` jest obecnie tylko logowany w postaci warningu, i nie wywołuje odebrania dostępu. Model uzytkownika w pliku `api/models/user.py` istotnie nie posiada pól takich jak `plan_expires_at` czy `stripe_subscription_status`.

## 3. Ocena powiązania wdrożeń (Wygasanie subskrypcji + Usuwanie Użytkownika)
Zgrupowanie naprawy webhooków Stripe z implementacją usuwania konta w panelu admina (brakujący endpoint w `api/routers/admin.py`) jako **jedno zadanie jest w pełni uzasadnione**:
- Oba zgłoszenia ingerują bezpośrednio w proces cyklu życia obiektu `User`.
- Gdy admin usunie konto używając panelu (a system skasuje z bazy obiekty `User`, portale etc.), proces *musi* wysłać żądanie do API Stripe na podstawie pola `stripe_subscription_id`, by natychmiast anulować aktywną subskrypcję. Zaniechanie tego kroku spowodowałoby, że klient pomimo braku konta byłby nadal obciążany cyklicznie ("ghost charging").
- Rozwiązanie obu ticketów najprawdopodobniej będzie wiązać się z rozbudową mechanizmów z pliku `api/routers/payments.py` oraz dodaniem nowej kolumny w `api/models/user.py`. 

## 4. Rekomendacja do Dispatchu dla Developera
1. **Model Bazy**: Rozszerzyć encję `User` o pole określające status np. `stripe_subscription_status` (`active`, `past_due`, `canceled`).
2. **Payments / Webhooki**: W funkcji `_handle_subscription_updated` upewnić się, że program przypisuje plan płatny WYŁĄCZNIE wtedy, gdy `subscription.status in ('active', 'trialing')`. W przeciwnym razie profil trafia na `free`.
3. **Panel Admina**: Dodać brakujący `DELETE /v1/admin/users/{user_id}` i użyć np. instrukcji `stripe.Subscription.delete(...)` jeśli pole `user.stripe_subscription_id` istnieje.
