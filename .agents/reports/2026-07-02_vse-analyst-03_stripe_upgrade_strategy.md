# Raport: Strategia i techniczna obsługa upgrade'ów abonamentu (Stripe)

## 1. Analiza techniczna (Stan obecny w `api/routers/payments.py`)

Przeanalizowałem plik `api/routers/payments.py` i zidentyfikowałem kluczowe kwestie związane z cyklem życia subskrypcji przy zmianie planu:

*   **Tworzenie podwójnych subskrypcji (Luka techniczna):** Obecny endpoint `POST /v1/payments/create-checkout-session` **zawsze** tworzy nową sesję Stripe Checkout z parametrem `mode: "subscription"`. Przekazujemy do niej identyfikator klienta (`customer_id`), ale **nie podajemy parametru `subscription_update`**. Oznacza to, że jeśli obecny subskrybent (np. planu Starter) wejdzie na cennik i wybierze plan Pro, to zamiast zaktualizowania (upgrade'u) obecnego abonamentu, Stripe **założy mu nową, równoległą subskrypcję** i pobierze pełną kwotę. To pilny problem do rozwiązania.
*   **Obsługa przez Customer Portal (Działa prawidłowo):** Aplikacja oferuje zarządzanie subskrypcją przez Customer Portal (`/v1/payments/portal-session`). Jeśli użytkownik zmieni plan z poziomu natywnego interfejsu Stripe, platforma domyślnie wylicza tzw. **proration** (odlicza różnicę za niewykorzystany czas starego planu). Nasz system wyłapuje to zdarzenie poprawnie poprzez webhook (`customer.subscription.updated`) i aktualizuje bazę danych na nowy plan.

## 2. Opcje Strategiczne i Biznesowe (Możliwości Stripe)

Odpowiadając na pytania biznesowe – z technicznego punktu widzenia Stripe daje kilka mechanizmów obliczania ceny przy zmianie planu (`proration_behavior`):

1.  **Domyślne Pro-rata (`create_prorations`):** Kiedy user robi upgrade, Stripe z dokładnością do sekundy nalicza zwrot za niewykorzystane dni z tańszego planu i pobiera zapłatę za brakujące dni w nowym, droższym planie. Co istotne, Stripe domyślnie dodaje to wyliczenie jako pozycję do kolejnej, przyszłej faktury. Oznacza to, że **w dniu zmiany planu system nie obciąża karty natychmiastową zapłatą za różnicę**, co na początku może prowadzić do nieporozumień z cash-flow.
2.  **Natychmiastowe fakturowanie różnicy (`always_invoice`):** Jest to strategicznie najlepsza opcja przy upgrade'ach. Mechanizm oblicza koszty dokładnie tak samo jak przy domyślnym Pro-rata (klient dopłaca tylko należną różnicę), ale system **od razu wystawia fakturę i natychmiast autoryzuje pobranie środków z karty na kwotę dopłaty**. 
3.  **Brak Proraty (`none`):** Zmiana planu następuje, ale klient nie otrzymuje rekompensaty za niewykorzystany czas tańszego planu. Musi opłacić pełną kwotę nowego pakietu. Odradzane, ponieważ blokuje motywację u konsumenta i powoduje poczucie niesprawiedliwości.
4.  **Użycie Rabatów (Discounts / Coupons):** Dodatkowo, przy procesie przejścia, możemy zaoferować zniżkę jednorazową lub stałą.

## 3. Rekomendowana Ścieżka Wdrożenia (Actionables)

Mając na uwadze psychologię sprzedaży oraz techniczne możliwości systemu, rekomenduję poniższe podejście:

1.  **Przejście na "Tylko Dopłacasz" (Wdrożenie `always_invoice`):** Z punktu widzenia biznesu pobieramy tylko różnicę z zachowaniem natychmiastowego obciążenia karty kwotą wyrównującą.
    *   **Technicznie:** Należy zabezpieczyć w kodzie endpoint `/create-checkout-session`, sprawdzając, czy użytkownik ma `stripe_subscription_id`. Jeśli ma, do wywołania checkout session należy dołączyć parametr:
        ```python
        session_kwargs["subscription_update"] = {
            "subscription": current_user.stripe_subscription_id,
            "proration_behavior": "always_invoice"
        }
        ```
2.  **Komunikacja Frontend (Rozbicie bariery zakupowej):** Jeżeli po stronie UI zidentyfikujemy, że użytkownik jest już opłacającym klientem, przyciski na Cenniku nie powinny mówić bezdusznie "Kup teraz". Powinny posiadać tooltip lub dopisek: *\"Upgrade do planu Pro. Zapłacisz tylko różnicę za pozostałe dni do końca miesiąca\"*.
3.  **Bodziec zachęcający do Upgrade'u (Kupon):** Jeśli chcemy mocniej zmotywować użytkowników darmowych lub pakietu Starter do podniesienia wydatków (Zwiększenia ARPU), można w panelu Stripe wygenerować kupon obniżający koszt planu, użyteczny jednokrotnie – w Stripe Checkout można to podać w parametrze `discounts`.