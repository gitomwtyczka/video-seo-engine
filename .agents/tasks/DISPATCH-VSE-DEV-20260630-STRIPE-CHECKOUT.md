# DISPATCH-VSE-DEV-STRIPE-CHECKOUT

**Zleceniodawca:** arch-analyst-01 | 30.06.2026
**Priorytet:** CRITICAL — blocker komercjalizacji
**Agent:** vse-dev (Claude Thinking lub Pro)
**Workspace:** video-seo-engine

---

## Cel

Implementacja Stripe checkout flow — aby user mógł zapłacić za plan Starter/Pro/Agency.

## Kontekst

Obecny stan:
- Model `Plan` istnieje z cenami (`price_pln`)
- Model `User` ma `stripe_customer_id` i `stripe_subscription_id` (oba nullable)
- Kolumna `stripe_price_id` istnieje w `Plan` (nullable)
- Brak: checkout session, webhook handler, subscription lifecycle

## Wymagane

### Backend (FastAPI)

1. **POST /v1/payments/create-checkout-session**
   - Input: `plan_id` (starter/pro/agency)
   - Tworzy Stripe Checkout Session
   - Zwraca `session_url` do redirect

2. **POST /v1/payments/webhook** (Stripe webhook)
   - Obsługuje eventy:
     - `checkout.session.completed` → aktywuj plan
     - `customer.subscription.updated` → zmiana planu
     - `customer.subscription.deleted` → downgrade do free
     - `invoice.payment_failed` → log + alert
   - Signature verification (`STRIPE_WEBHOOK_SECRET`)

3. **GET /v1/payments/portal-session**
   - Tworzy Stripe Customer Portal session (manage subscription)

### Frontend (Next.js)

1. **Pricing page** z przyciskami "Subscribe"
2. **Success/Cancel pages** po checkout
3. **Dashboard** — pokaż aktualny plan + "Manage" link

### Konfiguracja Stripe

1. Stwórz Products w Stripe Dashboard:
   - VSE Starter: 49 PLN/mo
   - VSE Pro: 149 PLN/mo  
   - VSE Agency: 399 PLN/mo
2. Zapisz `stripe_price_id` w tabeli `plans`
3. Dodaj do `.env`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`

### Zmienne środowiskowe

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Uwagi architektoniczne

- Użyj Stripe Checkout (hosted) — nie buduj custom payment form
- Stripe Customer Portal do zarządzania subskrypcją — nie buduj custom UI
- Test mode najpierw — przełączenie na live po weryfikacji
- Jeden Stripe Account obsługuje VSE i PressAI (różne Products)

## Weryfikacja

- [ ] Checkout session tworzy się i redirect działa
- [ ] Webhook odbiera events i aktualizuje plan usera
- [ ] Customer Portal działa
- [ ] Downgrade do free po cancellation
- [ ] E2E test z kartą testową Stripe

## Pre-deploy

⛔ **OBOWIĄZKOWY BACKUP:** `ssh ubuntu@147.224.162.100 "/home/ubuntu/scripts/backup_pre_deploy.sh"`

---
*[arch-analyst-01 | sonic-void 30.06.2026]*
