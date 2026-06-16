## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-dev-08 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet (debug + fix)

---

# TASK: vse-dev-08 — JWT Plan Fix (sidebar pokazuje Free zamiast Agency)

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Priorytet:** 🔴 PILNE — bloker dla Dashboard UI (D2+D3)

---

## Twój deliverable:
Po zalogowaniu przez Google sidebar VSE pokazuje prawidłowy plan z bazy danych (Agency), nie hardcoded Free.

---

## Problem

Użytkownik `tobroz@gmail.com` ma w bazie PostgreSQL:
- `plan = 'agency'`
- `is_admin = true`

Ale po zalogowaniu przez Google OAuth sidebar pokazuje:
- **"Free"** zamiast **"Agency"**
- **"0/5 Plan Free"** zamiast unlimited

Screenshot potwierdza: https://vse.impresjapr.pl/dashboard — sidebar: "Free", "0/5".

**Poprzednia próba naprawy (Supervisor 02):** commity `8f80403`, `9fed9db`, `719e61e` — nie rozwiązały problemu.

---

## Kontekst techniczny

- Auth: NextAuth.js z Google OAuth provider
- Config: `web/src/app/api/auth/[...nextauth]/route.ts`
- Backend: FastAPI (Python), PostgreSQL
- DB container: `vse-postgres`, user: `vse`

**Prawdopodobna przyczyna:** NextAuth JWT/session callback nie pobiera `plan` z bazy danych po logowaniu, albo frontend czyta plan z innego źródła niż sesja.

---

## Co zbadać (kolejność diagnostyczna)

1. **Sprawdź DB** — czy `plan` naprawdę = 'agency':
   ```
   ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 \
     "docker exec vse-postgres psql -U vse -c \"SELECT email, plan, is_admin FROM users WHERE email='tobroz@gmail.com'\""
   ```

2. **Sprawdź JWT callback w route.ts** — czy `plan` jest dodawany do tokenu JWT

3. **Sprawdź session callback** — czy `plan` z tokenu trafia do `session.user`

4. **Sprawdź frontend** — skąd sidebar czyta plan (session? osobny API call? hardcoded?)

5. **Napraw** — zapewnij że pełen łańcuch działa: DB → JWT callback → session callback → frontend

6. **Deploy** — po naprawie:
   ```
   ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 \
     "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web"
   ```

7. **Weryfikacja** — potwierdź że po re-login plan = Agency

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- DB: `docker exec vse-postgres psql -U vse`
- **FILE BRIDGE / Wetty: ZAKAZ**

---

## Raport po wykonaniu

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-08_jwt-plan-fix.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-08_jwt-plan-fix.md`

**Dual-write OBOWIĄZKOWY.**

---

## Protokół callsign (OBOWIĄZKOWE)

```
[vse-dev-08 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-08 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

---

*Supervisor 03 | sonic-void | 2026-06-16 18:39*
