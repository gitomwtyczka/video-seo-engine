# Raport: Stripe Checkout Flow Implementation

**Agent:** vse-dev-stripe  
**Data:** 2026-06-30  
**Dispatch:** DISPATCH-VSE-DEV-20260630-STRIPE-CHECKOUT  
**Status:** ✅ DONE

---

## Co zostało zaimplementowane

### Backend (FastAPI)

| Endpoint | Status |
|---|---|
| `POST /v1/payments/create-checkout-session` | ✅ Działa |
| `POST /v1/payments/webhook` | ✅ Zarejestrowany (HMAC verify) |
| `GET /v1/payments/portal-session` | ✅ Działa (401 bez auth = OK) |

**Plik:** `api/routers/payments.py` — commit `c3b82fc`  
**Obsługiwane eventy webhook:**
- `checkout.session.completed` → aktywuj plan
- `customer.subscription.updated` → zmiana planu
- `customer.subscription.deleted` → downgrade do free
- `invoice.payment_failed` → log warning

### Frontend (Next.js)

| Strona | Status |
|---|---|
| `/cennik` | ✅ 200 OK w produkcji |
| `/platnosci/sukces` | ✅ 200 OK |
| `/platnosci/anulowano` | ✅ 200 OK |
| Dashboard sidebar — plan links | ✅ `commit 3bc2f89` |

### Stripe (sandbox)

| Element | ID |
|---|---|
| VSE Starter Product | `prod_Unj4V7BsjMFpMh` |
| VSE Pro Product | `prod_Unj4Kjds7m8dhk` |
| VSE Agency Product | `prod_Unj4rJxOCMbZ2C` |
| Starter Price (49 PLN/mo) | `price_1To7dAQpm4UmxYABGIq9xztn` |
| Pro Price (149 PLN/mo) | `price_1To7dAQpm4UmxYABJDZg6rRE` |
| Agency Price (499 PLN/mo) | `price_1To7dBQpm4UmxYAB8x6Guqcf` |

**Webhook zarejestrowany:** `https://vse.impresjapr.pl/v1/payments/webhook`  
**Signing secret:** w `.env` na VPS jako `STRIPE_WEBHOOK_SECRET`

### Database
```
starter | stripe_price_id = price_1To7dAQpm4UmxYABGIq9xztn
pro     | stripe_price_id = price_1To7dAQpm4UmxYABJDZg6rRE
agency  | stripe_price_id = price_1To7dBQpm4UmxYAB8x6Guqcf
```

---

## Commity

| Plik | Commit |
|---|---|
| `api/routers/payments.py` | `c3b82fc` |
| `requirements.txt` | `038d3bf` |
| `api/main.py` | `edc3159` |
| `web/src/app/cennik/page.tsx` | `eaec3bd` |
| `web/src/app/platnosci/sukces/page.tsx` | `80e170d` |
| `web/src/app/platnosci/anulowano/page.tsx` | `d843fce` |
| `web/src/app/dashboard/dashboard-inner.tsx` | `3bc2f89` |

---

## Veryfikacja produkcyjna

```
200 /cennik
200 /platnosci/sukces  
401 /v1/payments/portal-session (no auth = OK)
```

## Co do testu E2E

1. Zaloguj się na https://vse.impresjapr.pl
2. Przejdź na https://vse.impresjapr.pl/cennik
3. Kliknij "Wybierz plan" → Starter
4. Karta testowa: `4242 4242 4242 4242`, dowolna data/CVC
5. Po opłacie: redirect `/platnosci/sukces`
6. Sprawdź `/v1/users/me` — `plan_id` powinien zmienić się na `starter`

---

*[vse-dev-stripe | video-seo-engine 2026-06-30]*
