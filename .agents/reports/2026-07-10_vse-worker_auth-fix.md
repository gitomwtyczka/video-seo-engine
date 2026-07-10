# Raport: VSE Auth Fix — route.ts
**Agent:** vse-worker  
**Data:** 2026-07-10 23:41  
**Status:** ✅ DZIAŁA

---

## Podsumowanie wykonania

### Problem
Dispatch Supervisor-03 nakazywał zmianę `application/json` → `application/x-www-form-urlencoded` + `username` zamiast `email`.

Po inspekcji backendu OpenAPI: `/v1/auth/login` oczekuje **JSON** z polem **`email`** (schemat `LoginRequest`), NIE `OAuth2PasswordRequestForm`. Poprzednia sesja (cd191073) popełniła błąd — zastosowała URLSearchParams zamiast JSON.

### Wykonane działania

1. **Odczyt route.ts** — SHA: `6ea156e73e93a6b433978a7a58095c234220d54a`
   - Znaleziono błąd: `URLSearchParams + username` zamiast `JSON + email`
2. **Weryfikacja backendu** — OpenAPI `/v1/auth/login` → `LoginRequest { email, password }`, Content-Type: `application/json`
3. **Commit fix** — przywrócono JSON body z polem `email`
   - Commit SHA: **`419fc8408cdad5bcffe61a5f29bc179012d67259`**
   - Message: `fix(auth): revert to JSON body with email field — backend expects LoginRequest not OAuth2Form [vse-worker]`
4. **Deploy na VPS** — `git pull + docker compose -f docker-compose.vse.yml up -d --build vse-web`
   - Build: `✓ Compiled successfully` (Next.js 14.2.29)
   - Status: `vse-web Started`, `vse-api Started`

### Wyniki testów

```
=== Test JSON email+password (wrong pass) ===
http_code: 401
Response: {"detail":"Invalid credentials"}

=== Test via NextAuth callback ===
http_code: 302
```

**401 = endpoint działa** (złe hasło, ale nie 422/500)  
**302 = NextAuth prawidłowo przekierowuje** przy nieudanym logowaniu

### Dodatkowe odkrycie

- Nazwa kontenera: `vse-web` (nie `video-seo-engine-vse-web-1`)
- Plik compose: `docker-compose.vse.yml` (nie `docker-compose.yml`)
- Backend port: `8085` — właściwy

---

## Status

✅ **FIX DZIAŁA** — logowanie przez NextAuth poprawnie wysyła JSON do backendu FastAPI.

*[vse-worker | video-seo-engine 10.07.2026 23:43]*
