# Raport sesji: vse-dev-08 | Google OAuth plan=free fix

**Data:** 2026-06-16 | **Agent:** vse-dev-08 | **Workspace:** video-seo-engine

---

## Cel sesji

Naprawa bugu: użytkownicy logujący się przez Google OAuth otrzymywali plan=free
niezależnie od faktycznego planu przypisanego do konta w bazie danych.

---

## Root Cause Analysis

**Problem:** `jwt callback` w NextAuth (`web/src/app/api/auth/[...nextauth]/route.ts`)
przy `account.provider === 'google'` nie wykonywał żadnego fetch'a planu.

Kod `if (token.accessToken && !user && (now - lastPlanFetch > 300))` nigdy nie był
wykonywany dla kont Google, ponieważ:
- `account.id_token` to Google JWT — nie nasz backend JWT
- `token.accessToken` nie był ustawiany przy Google logowaniu
- Warunek `if (token.accessToken && ...)` był zawsze `false`
- Plan pozostawał `'free'` (default z `session callback: token.plan ?? 'free'`)

---

## Implementacja

### Commit 1: `8f80403` — `api/routers/auth.py`

**Nowy endpoint:** `POST /v1/auth/google/token-exchange`

**CO:** Wymienia Google `id_token` (JWT podpisany przez Google) na parę JWT VSE.

**PO CO:** NextAuth przekazuje `account.id_token` w `jwt callback` — ale to Google token,
nie nasz backend JWT. Endpoint uzupełnia brakujące ogniwo.

**JAK:**
1. Przyjmuje `{ id_token: string }` w body
2. Weryfikuje przez `https://oauth2.googleapis.com/tokeninfo?id_token=...`
3. Sprawdza `aud === GOOGLE_CLIENT_ID` (security — zapobiega token injection)
4. Upsertuje usera identycznie jak `/google/callback`
5. Zwraca `{ access_token, refresh_token, token_type }`

### Commit 2: `9fed9db` — `web/src/app/api/auth/[...nextauth]/route.ts`

**Nowa funkcja:** `exchangeGoogleToken(idToken: string)`

**Zmiana w `jwt callback` dla `account.provider === 'google'`:**
```typescript
// PRZED (było):
if (account?.provider === 'google') {
  token.provider = 'google'
  // For Google OAuth, plan is fetched from backend on first login
  // accessToken here is Google token, not our JWT — plan fetched separately
}

// PO (jest):
if (account?.provider === 'google') {
  token.provider = 'google'
  const googleIdToken = account.id_token
  if (googleIdToken) {
    const exchanged = await exchangeGoogleToken(googleIdToken)  // → POST /v1/auth/google/token-exchange
    if (exchanged) {
      token.accessToken = exchanged.accessToken
      token.refreshToken = exchanged.refreshToken
      const profile = await fetchUserProfile(exchanged.accessToken)  // → GET /v1/users/me
      if (profile) {
        token.plan = profile.plan_id      // plan natychmiast!
        token.is_admin = profile.is_admin
        token.planFetchedAt = Math.floor(Date.now() / 1000)
      }
    } else {
      token.planFetchedAt = 0  // fallback: wymusza refresh przy następnym żądaniu
    }
  }
}
```

**Dodatkowe zabezpieczenie:** warunek `!account` w periodic refresh zapobiega
podwójnemu fetch przy pierwszym logowaniu Google.

### Commit 3: `719e61e` — `ARCHITECTURE.md`

Aktualizacja dokumentacji:
- §5B: cały Google OAuth Token Exchange flow
- §7: dodano shape dla `POST /v1/auth/google/token-exchange`
- §8: dodano endpoint do tabeli
- G11: gotcha dokumentujący bug i fix

---

## Pliki zmienione

| Plik | Commit | Opis |
|------|--------|------|
| `api/routers/auth.py` | `8f80403` | Nowy endpoint `POST /v1/auth/google/token-exchange` |
| `web/src/app/api/auth/[...nextauth]/route.ts` | `9fed9db` | jwt callback Google fix + exchangeGoogleToken() |
| `ARCHITECTURE.md` | `719e61e` | Dokumentacja §5B + §7 + §8 + G11 |

---

## Wymagany deploy

Zmiany wymagają rebuildu **obu** serwisów:
```bash
# Na VPS:
docker compose -f docker-compose.vse.yml up -d --build vse-api vse-web
```

> **UWAGA dla Supervisora:** Proszę o deploy — zmiany w `api/` i `web/` wymagają rebuildu.

---

## Weryfikacja po deployu

1. Wejść na https://vse.impresjapr.pl/login
2. Kliknąć "Zaloguj przez Google"
3. Po przekierowaniu na /dashboard sprawdzić czy plan jest widoczny natychmiast
4. W Swagger: `GET /docs` → sprawdzić czy `POST /v1/auth/google/token-exchange` widoczny
5. Test endpointu z nieprawidłowym token → oczekiwane 401

---

*vse-dev-08 | video-seo-engine | 2026-06-16 | raport kompletny*
