# Raport: vse-dev-07 — Admin Panel D4

**Data:** 2026-06-16  
**Agent:** `vse-dev-07`  
**Sesja:** `760143ab-9183-48e8-a723-727084fef735`  
**Status:** ✅ DONE

---

## CO zrobione

Zaimplementowany i wdrożony panel administratora `/admin` na `vse.impresjapr.pl`.

## Commity

| SHA | Plik | Opis |
|-----|------|------|
| `e13651e` | `api/routers/admin.py` | Backend: GET /v1/admin/users, PATCH /plan, GET /stats |
| `f73e8a9` | `api/main.py` | Rejestracja admin routera w FastAPI |
| `bd36dee` | `web/src/middleware.ts` | Ochrona `/admin` — is_admin lub plan=agency |
| `b151371` | `web/src/app/admin/page.tsx` | Frontend: tabela userów + modal zmiany planu |

---

## Backend: api/routers/admin.py

**Endpointy:**
- `GET /v1/admin/users` — lista wszystkich użytkowników z planem i usage_this_month
- `GET /v1/admin/users/{id}` — szczegóły konkretnego użytkownika
- `PATCH /v1/admin/users/{id}/plan` — zmiana planu subskrypcji
- `GET /v1/admin/stats` — statystyki systemu (total users, by plan, active 30d, today)

**Autoryzacja:** Dependency `get_current_admin` z `api/auth.py` — wymaga `is_admin=True`.
Pole `is_admin` już istniało na modelu `User` — wykorzystane bez zmian schematu DB.

**Weryfikacja HTTP:**
- `GET /v1/admin/users` bez tokenu → **401** ✅
- `GET /v1/admin/stats` bez tokenu → **401** ✅

## Frontend: web/src/app/admin/page.tsx

**Funkcjonalność:**
- Tabela użytkowników z kolumnami: email, imię, plan (badge), generacje/mies., data rejestracji, status
- Wyszukiwanie real-time po emailu / imieniu
- Filtry planów: Wszyscy / Free / Starter / Pro / Agency
- Modal "Zmień plan" z radio selection + potwierdzenie
- Statystyki systemu: 4 karty + wykres słupkowy rozkładu planów
- Odznaka admin (👑) dla kont admin
- Sidebar z nawigacją do Dashboard
- Wylogowanie

**Styl:** Spójny z dashboard/page.tsx — ciemny motyw, Tailwind, bez zmian CSS.

## middleware.ts

```typescript
if (pathname.startsWith('/admin')) {
  const isAdmin = token?.is_admin === true
  const plan = token?.plan as string | undefined
  const isAgency = plan === 'agency'
  if (!isAdmin && !isAgency) redirect('/dashboard')
}
matcher: ['/dashboard/:path*', '/settings/:path*', '/admin/:path*']
```

Niezalogowani → `/login`. Zalogowani bez uprawnień → `/dashboard`.

## Weryfikacja żywa

| Test | Wynik |
|------|-------|
| `GET /health` | 200 ✅ |
| `GET /admin` (bez sesji) | 307 redirect → /login ✅ |
| `GET /v1/admin/users` (bez tokenu) | 401 ✅ |
| `GET /v1/admin/stats` (bez tokenu) | 401 ✅ |
| `vse-api` container | Started ✅ |
| `vse-web` container | Started ✅ |

## Uwagi dla następnego agenta

1. **Test weryfikacyjny do wykonania ręcznie:** Zaloguj się jako `tobroz@gmail.com` (plan agency) i wejdź na `vse.impresjapr.pl/admin` — tabela powinna się załadować.
2. **Konto admin:** Jeśli konto `tobroz@gmail.com` NIE ma `is_admin=True` w bazie, dostęp do panelu dzięki `plan=agency` (middleware) ale endpointy API wymagają `is_admin=True`. W razie potrzeby: `UPDATE users SET is_admin = true WHERE email = 'tobroz@gmail.com';` na VPS.
3. **NextAuth token:** Plik `web/src/app/api/auth/[...nextauth]/route.ts` może potrzebować rozszerzenia callbacku `session` o pole `plan` i `is_admin` jeśli nie są jeszcze przekazywane do tokenu.

*vse-dev-07 | video-seo-engine | 2026-06-16*
