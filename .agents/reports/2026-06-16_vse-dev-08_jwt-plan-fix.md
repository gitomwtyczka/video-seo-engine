# Report: vse-dev-08 — JWT Plan Fix (MissingGreenlet)

**Data:** 2026-06-16  
**Callsign:** vse-dev-08  
**Status:** ✅ DONE  
**Commit:** `5578c64`  

---

## Problem

Po zalogowaniu przez Google OAuth, sidebar dashboardu VSE pokazywał:
- **"Free"** zamiast **"Agency"**
- **"0/5"** zamiast **"0/9999"**

Pomimo że w bazie danych `tobroz@gmail.com` miał `plan_id = agency` i `is_admin = true`.

## Root Cause

**`sqlalchemy.exc.MissingGreenlet`** — lazy loading w async SQLAlchemy.

Łańcuch awarii:
1. `POST /v1/auth/google/token-exchange` → **200 OK** ✅
2. `GET /v1/users/me` → **500 Internal Server Error** ❌
   - `get_current_user()` w `api/auth.py` ładował `User` bez eager-loadingu relacji `plan`
   - Gdy `get_me` próbował odczytać `current_user.plan.monthly_quota`, async SQLAlchemy próbował lazy-load → `MissingGreenlet`
3. NextAuth `fetchUserProfile()` dostawał `null` (500 response)
4. Session fallback: `token.plan ?? 'free'` → wyświetlane **"Free"**
5. Dashboard client-side fetch też dostawał 500 → `userProfile = null` → **"Free"**

## Fix

**Plik:** `api/auth.py`  
**Zmiana:** Dodano `selectinload(User.plan)` do query w `get_current_user()`:

```python
from sqlalchemy.orm import selectinload

# Przed (crash):
result = await db.execute(select(User).where(User.id == user_id))

# Po (fix):
result = await db.execute(
    select(User)
    .options(selectinload(User.plan))
    .where(User.id == user_id)
)
```

To jest standardowy pattern w async SQLAlchemy — lazy loading nie działa w async kontekście.

## Weryfikacja

1. **API test:** `GET /v1/users/me` → 200 OK, `plan.id = agency`, `is_admin = true`
2. **Dashboard screenshot:** Sidebar pokazuje "Agency", usage "0/9999", stat card "Plan Agency"
3. **Logi:** Brak `MissingGreenlet` errors po fix

## Diagnostyka dev-07

Dev-07 commity (`8f80403`, `9fed9db`, `719e61e`) były **koncepcyjnie poprawne** — dodały `fetchUserProfile()` i `exchangeGoogleToken()` do route.ts. Te zmiany BYŁY w buildzie na VPS. Problem nie leżał w frontendzie — leżał w backendzie (500 na `/v1/users/me`).

## Uwaga: Agency monthly_quota = 9999

W tabeli `plans` Agency ma `monthly_quota = 9999` (nie `-1` unlimited). To wystarczy na produkcję, ale docelowo warto zmienić na `-1` i obsłużyć w UI jako "Unlimited".

---

*vse-dev-08 | video-seo-engine | 2026-06-16 19:25*
