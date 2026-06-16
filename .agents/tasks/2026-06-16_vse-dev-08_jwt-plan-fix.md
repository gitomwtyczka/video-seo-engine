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
- `is_admin = true` (potwierdzony SQL UPDATE)
- Plan powinien być `agency`

Ale po zalogowaniu przez Google OAuth sidebar pokazuje:
- **"Free"** zamiast **"Agency"**
- **"0/5 Plan Free"** zamiast unlimited

Screenshot potwierdza: https://vse.impresjapr.pl/dashboard — sidebar: "Free", "0/5".

---

## ⚠️ KRYTYCZNY KONTEKST — Poprzednia nieudana próba (dev-07)

Dev-07 próbował to naprawiać (commity `8f80403`, `9fed9db`, `719e61e`). Fix był koncepcyjnie poprawny:

```typescript
// jwt callback — po zalogowaniu woła GET /v1/users/me i zapisuje:
token.plan = profile.plan_id
token.is_admin = profile.is_admin

// session callback:
session.user.plan = token.plan ?? 'free'
session.user.is_admin = token.is_admin ?? false
```

**ALE fix nie zadziałał.** Dev-07 zidentyfikował prawdopodobną przyczynę zanim sesja się skończyła:

### Trzy podejrzenia do zweryfikowania (ZACZYNAJ OD TYCH):

**A) Nazwa kolumny w DB nie zgadza się z tym co czyta NextAuth:**
- SQL mówił `SET plan = 'agency'` — ale model może mieć kolumnę `plan_id`
- NextAuth callback czyta `profile.plan_id` — ale backend może zwracać pole `plan`
- **Sprawdź model User w `api/models/user.py`** — jak się naprawdę nazywa kolumna?

**B) Nazwa kontenera DB jest inna niż założono:**
- Dev-07 próbował `docker exec vse-db` → **"No such container: vse-db"**
- W taśce Supervisor 02 jest `vse-postgres` — ale to też może być błędne
- **Pierwsza komenda: `docker ps --format '{{.Names}}'`** — ustal prawdziwą nazwę

**C) Build nie wciągnął zmian dev-07:**
- Commity poszły do repo, ale `docker compose up --build` mógł nie przebudować
- **Sprawdź czy `route.ts` na VPS ma fix** — grep `plan_id` lub `is_admin` w kontenerze

---

## Kolejność diagnostyczna

```
1. docker ps --format '{{.Names}}'           ← ustal nazwy kontenerów
2. docker exec [DB_CONTAINER] psql -U [USER] -d [DB] -c \
   "SELECT email, * FROM users WHERE email='tobroz@gmail.com';"  ← WSZYSTKIE kolumny
3. Przeczytaj api/models/user.py (GitHub MCP)  ← nazwa kolumny plan vs plan_id
4. Przeczytaj route.ts (GitHub MCP)            ← co jest w jwt callback TERAZ
5. Przeczytaj sidebar component (GitHub MCP)   ← skąd czyta plan
6. Napraw pełen łańcuch: DB kolumna → backend response → JWT callback → session → frontend
7. Deploy + verify
```

---

## SSH — wzorzec dla PowerShell

**Proste komendy** (bez cudzysłowów, zmiennych):
```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}}'"
```

**Złożone komendy** (SQL, zmienne, zagnieżdżone cudzysłowy) → write_to_file + scp + ssh:
```powershell
# 1. Napisz skrypt lokalnie
# 2. scp -i ~/.ssh/oracle-crimson.key script.py ubuntu@147.224.162.100:/tmp/
# 3. ssh ... "python3 /tmp/script.py"
```

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
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

*Supervisor 03 | sonic-void | 2026-06-16 19:05 | updated with dev-07 findings*
