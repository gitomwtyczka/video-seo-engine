## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-analyst-01 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet

---

# TASK: vse-analyst-01 — Admin Panel Audit (zniknął po deployach)

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Rola:** Analityk — NIE implementujesz, tylko diagnozujesz i raportujesz

---

## Twój deliverable:

Raport diagnostyczny: dlaczego admin panel nie działa i co konkretnie trzeba naprawić.

---

## Kontekst

Admin panel został zaimplementowany przez `vse-dev-07` (commits `e13651e`, `f73e8a9`, `bd36dee`, `b151371`).

Co było zrobione:
- `/admin` — panel z listą użytkowników + zmianą planu
- `api/routers/admin.py` — 4 endpointy
- `middleware.ts` — ochrona trasy `/admin`
- `admin/page.tsx` — UI panelu

Weryfikacja z tamtej sesji działała:
- `GET /admin` bez sesji → 307 → /login ✅
- `GET /v1/admin/users` bez tokenu → 401 ✅

**Teraz:** Użytkownik mówi że panel "przepadł" po kolejnych deployach.

---

## Co zbadać

### 1. Czy kod jest w repo?

```
GitHub MCP — sprawdź czy pliki istnieją:
- web/src/app/admin/page.tsx
- web/src/middleware.ts
- api/routers/admin.py
- api/main.py (czy router admin jest zarejestrowany?)
```

### 2. Czy na VPS działają endpointy?

```powershell
# Test bez auth (powinno 401):
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "curl -s -o /dev/null -w '%{http_code}' https://vse.impresjapr.pl/v1/admin/users"

# Test strony /admin (powinno redirect do /login):
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "curl -s -o /dev/null -w '%{http_code}' https://vse.impresjapr.pl/admin"
```

### 3. Czy middleware jest aktywny?

Sprawdź `web/src/middleware.ts` w repo — czy chroni trasy `/admin`?

### 4. Czy `is_admin` jest ustawione?

```powershell
# Ustal nazwę kontenera DB:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}}'"

# Sprawdź is_admin dla tobroz@gmail.com:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker exec [NAZWA_KONTENERA] psql -U [USER] -c 'SELECT email, plan, is_admin FROM users WHERE email=\'tobroz@gmail.com\';'"
```

### 5. Czy JWT token zawiera `is_admin`?

Sprawdź `web/src/app/api/auth/[...nextauth]/route.ts` — czy `is_admin` jest w session callback (może ten sam problem co z `plan`).

---

## Format raportu

```markdown
# Diagnoza Admin Panel

## Status
- Kod w repo: TAK/NIE (lista plików)
- Endpoint /v1/admin/users: [HTTP status]
- Endpoint /admin: [HTTP status]
- is_admin w DB: TAK/NIE
- is_admin w JWT token: TAK/NIE

## Root Cause
[Co konkretnie nie działa]

## Wymagane działania
[Lista konkretnych fixów do wykonania przez dev]
```

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **FILE BRIDGE / Wetty: ZAKAZ**
- **NIE naprawiasz — tylko diagnozujesz**

---

## Raport po wykonaniu

1. `video-seo-engine/.agents/reports/2026-06-16_vse-analyst-01_admin-panel-audit.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-analyst-01_admin-panel-audit.md`

**Dual-write OBOWIĄZKOWY.**

---

## Protokół callsign

```
[vse-analyst-01 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-analyst-01 | video-seo-engine DD.MM.YYYY HH:MM] — raport kompletny
```

---

*Supervisor 03 | sonic-void | 2026-06-16 19:15*
