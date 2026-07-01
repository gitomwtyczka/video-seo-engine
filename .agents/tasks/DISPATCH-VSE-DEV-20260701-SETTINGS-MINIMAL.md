# DISPATCH: VSE-DEV-20260701 — Minimal Settings Page

**Zlecenie od:** Supervisor 02 (sonic-void)
**Data:** 2026-07-01
**Priorytet:** Sredni-wysoki — UX przed komercjalizacja
**Estymacja:** 1-2 dni

## Problem

`web/src/app/ustawienia/page.tsx` to placeholder "W trakcie budowy" z informacja o Fazie 5 i 7. Portale WP sa JUZ zaimplementowane (D34-D36). Link "Konfiguruj" na dashboardzie prowadzi do tego placeholdera.

## Co zaimplementowac

Zastap placeholder dzialajaca strona ustawien z 3 sekcjami:

### Sekcja 1: Konto
- Email uzytkownika (z session?.user?.email)
- Aktualny plan (fetch GET /v1/users/me lub z session)
- Przycisk "Zarzadzaj subskrypcja" (Stripe Customer Portal) — reuse ManageSubscriptionLink z dashboard-inner.tsx. Pokazuj tylko dla plan != 'free'

### Sekcja 2: Portale WordPress
- Lista portali uzytkownika: GET /v1/portals przez usePortals hook (web/src/app/dashboard/use-portals.ts)
- Kazdy portal: nazwa, URL, czy domyslny (badge)
- Przycisk "Dodaj portal" (reuse AddPortalModal z dashboardu)
- Przycisk "Usun" per portal
- Limit portali per plan (Free: 0, Starter: 3, Pro: 10, Agency: 999) — pokaz "X/Y portali"
- Jesli Free: pokaz lock z info "Upgrade do Starter aby dodac portal"

### Sekcja 3: Plany
- Link do /cennik jesli Free
- Lub info o aktualnym planie z data odnowienia jesli platny

## Techniczne wytyczne

- Reuse hookow: usePortals z web/src/app/dashboard/use-portals.ts
- Reuse modali: AddPortalModal z dashboard-inner.tsx
- Auth guard tak jak teraz
- Styl: taki sam dark theme jak reszta aplikacji
- Sprawdz czy ManageSubscriptionLink jest osobnym komponentem czy inline i wyekstrahuj jesli trzeba

## Deployment

1. Commit przez GitHub MCP
2. SSH (ubuntu@147.224.162.100): git pull && docker compose restart vse-web
3. Weryfikacja: docker logs vse-web --tail 10

## ZNANE PULAPKI
1. SSH user: ubuntu (NIE root)
2. Nie uzywaj ask_permission na SSH
3. ManageSubscriptionLink moze wymagac accessToken — pobierz z useSession
4. AddPortalModal moze miec zaleznosci od kontekstu dashboardu — sprawdz props przed reuse
5. GitHub MCP: po commicie weryfikacja newlines

## Raport koncowy
- Commit SHA
- Opis co widac na /ustawienia po deployu
- Czy ManageSubscriptionLink dziala
- Czy lista portali sie laduje
