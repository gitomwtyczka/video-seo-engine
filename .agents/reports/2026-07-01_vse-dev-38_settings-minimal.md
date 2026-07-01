# Raport: SETTINGS-MINIMAL — vse-dev-38

**Data:** 2026-07-01 19:41 UTC  
**Callsign:** vse-dev-38 | video-seo-engine 2026-07-01  
**Dispatch:** DISPATCH-VSE-DEV-20260701-SETTINGS-MINIMAL  
**Status:** COMMIT OK | DEPLOY ZABLOKOWANY (SSH timeout)

---

## Commit SHA

`35381247579c914bb97941ad78ad575163577a40`

Plik: `web/src/app/ustawienia/page.tsx`  
Rozmiar: 29 683 bajtów  
SHA pliku: `426cc2f3fbc0de666a0a80c8b8927ebb4d9ad65e`

---

## Co zaimplementowano

### Sekcja 1: Konto
- Email użytkownika z `session?.user?.email`
- Aktualny plan z GET `/v1/users/me` (Bearer token)
- Badge statusu (Aktywny / Bezpłatny)
- Progress bar wykorzystania generacji w tym miesiącu
- `ManageSubscriptionLink` — widoczny tylko gdy `planId !== 'free'` i accessToken dostępny
  - Wywołuje GET `/v1/payments/portal-session` → redirect do Stripe Portal

### Sekcja 2: Portale WordPress
- `usePortals()` — lista portali z GET `/v1/portals`
- Każdy portal: nazwa, URL, badge "domyślny" (is_default)
- Przycisk "Usuń" per portal z potwierdzeniem (confirm dialog)
- Limity per plan: Free: 0, Starter: 3, Pro: 10, Agency: 999
- Licznik X/Y portali w nagłówku sekcji
- Plan Free: lock z komunikatem + link "Upgrade do Starter →"
- Skeleton loaders podczas ładowania
- Przycisk "Dodaj portal" → `AddPortalModal` (inline, bez importu z dashboard-inner.tsx)

### Sekcja 3: Plan subskrypcji
- Plan Free → link "Upgrade ↗" do /cennik
- Plan płatny → info o planie, `ManageSubscriptionLink`, data odnowienia (gdy dostępna), limit portali i generacji

---

## Decyzje architektoniczne

- **NIE importowano** `AddPortalModal` z `dashboard-inner.tsx` (75KB) — stworzono uproszczony modal inline w pliku ustawień (bez inline profile creation — zbyt złożone dla strony ustawień)
- **Hooki reużyte**: `usePortals` i `useProfiles` z `../dashboard/`
- **TypeScript strictness**: bez `ignoreBuildErrors` — kod jest type-safe
- **Auth guard**: identyczny jak w dashboardzie

---

## Status deployu

| Krok | Status | Szczegóły |
|------|--------|-----------|
| Commit | ✅ OK | SHA: 3538124 |
| Newlines weryfikacja | ✅ OK | LF, 29683B |
| Pre-deploy backup | ❌ BLOCKED | SSH permission timeout |
| Deploy | ❌ SKIPPED | Backup niewykonany — STOP per reguły |
| Weryfikacja | ❌ SKIPPED | |

### Deploy wymagany
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "/home/ubuntu/scripts/backup_pre_deploy.sh && \
  cd /home/ubuntu/video-seo-engine && \
  git pull origin main && \
  docker compose -f docker-compose.vse.yml restart vse-web"
```

---

## Blokery

- **SSH permission timeout** — środowisko nie przyznało uprawnień SSH w oknie 60s.
- Supervisor musi uruchomić deploy manualnie lub przez osobny dispatch do workera z uprawnieniami SSH.

---

*[vse-dev-38 | video-seo-engine 2026-07-01 19:41] raport kompletny*
