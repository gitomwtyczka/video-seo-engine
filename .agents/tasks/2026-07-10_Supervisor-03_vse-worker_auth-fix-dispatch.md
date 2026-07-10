# Dispatch: VSE Auth Crash Fix — route.ts
**Od:** Supervisor-03  
**Do:** vse-worker  
**Data:** 2026-07-10 23:38  
**Priorytet:** 🔴 KRYTYCZNY — produkcja down (login nie działa)

---

## CEL

Fix NextAuth credentials authorize() — crash 500 przy logowaniu.

**Root cause:** NextAuth wysyła JSON do FastAPI, ale FastAPI (`OAuth2PasswordRequestForm`) oczekuje `application/x-www-form-urlencoded`. FastAPI zwraca 422, NextAuth crashuje bez obsługi błędu → Nginx pluje pustym 500.

**Jedna dodatkowa pułapka:** FastAPI OAuth2 używa pola `username`, nie `email`. Jeśli podasz `email` — 422 nawet z prawidłowym Content-Type.

---

## PLIK DO EDYCJI

```
repo: video-seo-engine
branch: main
path: web/src/app/api/auth/[...nextauth]/route.ts
SHA: f629461a4a4eaa042c4cf6872dcfe48a1d29cb48
```

---

## 3 ZMIANY DO WYKONANIA

### Zmiana 1 — Content-Type: JSON → form-urlencoded

**PRZED (linia ~43):**
```typescript
        const res = await fetch(`${BACKEND_URL}/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        })
        if (!res.ok) return null
```

**PO:**
```typescript
        const formData = new URLSearchParams()
        formData.append('username', credentials.email)
        formData.append('password', credentials.password)
        const res = await fetch(`${BACKEND_URL}/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData.toString(),
        })
        if (!res.ok) return null
```

**Co się zmieniło:**
1. Content-Type: `application/json` → `application/x-www-form-urlencoded`  
2. body: `JSON.stringify({email, password})` → `URLSearchParams` z polem `username` (nie `email`!)
3. Dodany `if (!res.ok) return null` — obsługa błędu bez throw

---

## ⚠️ ZNANE PUŁAPKI (przeczytaj ZANIM zaczniesz)

1. **`username` nie `email`** — FastAPI OAuth2PasswordRequestForm wymaga pola `username`. Jeśli użyjesz `email` — FastAPI zwróci 422 nawet z poprawnym Content-Type. Fix nie zadziała.
2. **GitHub MCP po create_or_update_file** — zawsze zrób `get_file_contents` i sprawdź że zmiany są w pliku.
3. **SHA** — przy `create_or_update_file` podaj SHA: `f629461a4a4eaa042c4cf6872dcfe48a1d29cb48` inaczej GitHub MCP zwróci błąd konfliktu.
4. **Uważaj na resztę pliku** — zmiana dotyczy tylko sekcji `authorize()` (ok. linie 38-55). Nie ruszaj Google OAuth, refreshAccessToken, jwt/session callbacks.

---

## WERYFIKACJA

### A. Po commicie (GitHub)
```
get_file_contents → sprawdź że `application/x-www-form-urlencoded` i `username` są w pliku
```

### B. Po restarcie kontenera
```bash
# SSH na VPS:
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose restart vse-web"

# Odczekaj 15s, potem sprawdź logi:
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "docker logs --tail 20 video-seo-engine-vse-web-1"
```

### C. Weryfikacja endpoint
```bash
# Test z VPS (zastąp email/password prawdziwymi):
ssh -i C:\Users\tomas2\.ssh\oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8085/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=test@example.com&password=test'"
# Oczekiwany wynik: 200 lub 401 (nie 422, nie 500)
```

---

## RAPORT

Po zakończeniu wyślij raport do:
1. `video-seo-engine/.agents/reports/2026-07-10_vse-worker_auth-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-07-10_vse-worker_auth-fix.md`

Raport musi zawierać:
- Commit SHA po fix
- Output weryfikacji (http_code lub docker logs)
- Czy login działa (lub opis blokera jeśli nie)

---

*[Supervisor-03 | sonic-void 10.07.2026 23:38]*