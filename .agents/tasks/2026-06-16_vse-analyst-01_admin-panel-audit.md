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

## 📚 KROK 0b — Przeczytaj kontekst projektu (OBOWIĄZKOWE PRZED ANALIZĄ)

Przed czymkolwiek przeczytaj przez GitHub MCP:

1. **Architektura** — `docs/ARCHITECTURE.md`  
   *Zawiera: stack, kontenery Docker, nazwy serwisów, porty, strukturę katalogów*

2. **Roadmap** — `ROADMAP.md`  
   *Zawiera: co już zrobione, co w toku, fazy, commity które wdrożyły admin panel*

Bez znajomości tych dokumentów ryzykujesz odkrywanie rzeczy które są już udokumentowane.

---

## Twój deliverable:

Raport diagnostyczny: dlaczego admin panel nie działa i co konkretnie trzeba naprawić.

---

## Kontekst znany (nie odkrywaj ponownie)

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

**Znany problem pokrewny:** `vse-dev-08` aktywnie naprawia JWT callback — `is_admin` i `plan` mogą nie być w sesji NextAuth. To jest prawdopodobny wspólny mianownik.

---

## Co zbadać

### 1. Nazwy kontenerów (zanim cokolwiek innego)

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}} {{.Status}}'"
```

Nie zakładaj nazw (`vse-db`, `vse-postgres`) — ustal je empirycznie.

### 2. Czy kod admin jest w repo?

GitHub MCP — sprawdź czy pliki istnieją:
- `web/src/app/admin/page.tsx`
- `web/src/middleware.ts`
- `api/routers/admin.py`
- `api/main.py` (czy router admin jest zarejestrowany)

### 3. Czy endpointy odpowiadają?

```powershell
# Powinno 401:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "curl -s -o /dev/null -w '%{http_code}' https://vse.impresjapr.pl/v1/admin/users"

# Powinno redirect do /login:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "curl -s -o /dev/null -w '%{http_code}' https://vse.impresjapr.pl/admin"
```

### 4. Stan bazy danych

```powershell
# Po ustaleniu nazwy kontenera DB:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker exec [KONTENER_DB] psql -U [USER] -d [DB] -c 'SELECT email, plan, is_admin FROM users LIMIT 5;'"
```

### 5. JWT session — czy is_admin trafia do frontendu?

Sprawdź `web/src/app/api/auth/[...nextauth]/route.ts` (GitHub MCP) — czy `is_admin` jest w session callback. To prawdopodobnie ten sam błąd co z `plan` (fixowany przez vse-dev-08).

---

## Format raportu

```markdown
# Diagnoza Admin Panel

## Status
- Kod w repo: TAK/NIE (lista plików)
- Endpoint /v1/admin/users: [HTTP status]
- Endpoint /admin: [HTTP status]
- is_admin w DB: TAK/NIE (wartość)
- is_admin w JWT session callback: TAK/NIE

## Root Cause
[Co konkretnie nie działa]

## Wymagane działania
[Lista konkretnych fixów do wykonania przez dev]

## Zależności
[Czy fix wymaga wyniku vse-dev-08?]
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

*Supervisor 03 | sonic-void | 2026-06-16 19:32 | updated: KROK 0b architektura+roadmap*
