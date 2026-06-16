# DISPATCH — vse-dev-05 | Naprawa „Not Found” + plan upgrade

**ID:** DISPATCH-VSE-DEV-05-20260616-NOT-FOUND-FIX  
**Data:** 2026-06-16  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-05`  
**Priorytet:** P0 — blokuje core feature

---

## Kontekst — co zrobił poprzednik (vse-dev-04)

Przedtem system nie działał w ogóle (Oracle Cloud IP ban blokował transkrypty). Dev-04 wykonał:

### Commity DEV-04:
| Commit | Repo | Co |
|---|---|---|
| `dc3709f` | video-seo-engine | `local-runner/service.py` — pywin32 + Task Scheduler, Windows Service polling `/v1/jobs/pending` |
| `9fb1f85` | crimson-void | nginx: dodany `location /v1/` → proxy na FastAPI port 8085 |
| `125477c` | video-seo-engine | naprawa logowania (problem wystąpił po deploy DEV-04) |

### Stan po DEV-04:
- Logowanie: ✅ działa (125477c)
- `/v1/jobs/pending` przez HTTPS: ✅ 200 OK
- YouTube transcript lokalnie przez Local Runner: ✅ 85 553 chars
- `VSELocalRunner` Task Scheduler: ✅ Running, AtLogOn

---

## Zadanie 1 — Naprawa „Not Found” (P0)

**Symptom:** Na dashboardzie `vse.impresjapr.pl/dashboard` po wklejeniu URL YouTube i kliknięciu „Generuj SEO” — pojawia się:
```
⚠️ Wystąpił błąd
Not Found
```

**Hipoteza główna:** nginx change z DEV-04 (`location /v1/`) zepsuł routing dla głównego endpointu generowania SEO.

W crimson-void kolejność bloków w `nginx/default.conf` jest KRYTYCZNA:
- `/api/auth/` musi być PRZED `/api/` (NextAuth przed FastAPI)
- Jeśli DEV-04 dodał `/v1/` w złym miejscu — może zakłócać routing `/v1/generate` lub `/v1/inject`

**Alternatywna hipoteza:** Frontend wywołuje inny endpoint niż ten który istnieje w FastAPI.

### Kroki:
1. Przeczytaj `nginx/default.conf` z crimson-void (GitHub MCP, branch main)
2. Przeczytaj `api/routers/` — jakie endpointy istnieją?
3. Przeczytaj frontend — co wywołuje po kliknięciu „Generuj SEO”?
4. Porównaj routing — znajdź rozbiezność
5. Naprawa minimalna i precyzyjna
6. Deploy: `docker compose up -d --no-deps --force-recreate vse-api` i/lub `nginx`
7. Test: wklej URL YouTube → kliknij Generuj SEO → brak błędu

**Zasady nginx (KRYTYCZNE):**
```
/api/auth/  ZAWSZE PIERWSZE  (NextAuth)
/api/       ZAWSZE DRUGIE    (Next.js)
/v1/        TRZECIE          (FastAPI)
/           OSTATNIE         (Next.js fallback)
```

---

## Zadanie 2 — Upgrade planu użytkownika (P1)

**żądanie:** Użytkownik `tobroz@gmail.com` (loguje się przez Google OAuth) ma plan `Free`. Powinien mieć najwyższy dostępny plan.

### Kroki:
1. SSH na Oracle ARM:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100
```

2. Wejdź do bazy danych:
```bash
cd /home/ubuntu/video-seo-engine
docker compose exec db psql -U postgres -d vse_db
```

3. Znajdź użytkownika i sprawdź strukturę:
```sql
-- Sprawdź tabelę users
SELECT id, email, plan, created_at FROM users WHERE email = 'tobroz@gmail.com';

-- Sprawdź jakie plany istnieją w systemie
SELECT DISTINCT plan FROM users;
```

4. Upgrade planu:
```sql
-- Ustaw najwyższy plan (sprawdź nazwę planu w kodzie najpierw!)
-- Możliwe wartości: 'agency', 'pro', 'enterprise', 'admin' — sprawdź enum w modelu
UPDATE users SET plan = '[NAJWYŻSZY_PLAN]' WHERE email = 'tobroz@gmail.com';

-- Weryfikacja
SELECT id, email, plan FROM users WHERE email = 'tobroz@gmail.com';
```

5. Przed wykonaniem UPDATE — przeczytaj model User w `api/models/` żeby znać dostępne wartości enum planu.

**Po wykonaniu:** zaloguj się jako tobroz@gmail.com i sprawdź czy dashboard pokazuje zmieniony plan.

---

## Ważne zasady (nie łam!)

1. **Nie ruszaj** `dc3709f` — Local Runner działa, nie psuj
2. **Nie ruszaj** `125477c` — logowanie naprawione
3. Testuj po każdej zmianie nginx: `docker compose logs nginx --tail=20`
4. Backup przed UPDATE w bazie: `SELECT * FROM users WHERE email = 'tobroz@gmail.com';` zapisz wynik w raporcie

---

## Architektura (przypomnienie)

```
Browser → Cloudflare → nginx (crimson-void)
                              ├─ /api/auth/   → Next.js :3000 (NextAuth)
                              ├─ /api/        → Next.js :3000
                              ├─ /v1/         → FastAPI :8085
                              └─ /            → Next.js :3000

FastAPI :8085:
  POST /v1/generate    ← główny endpoint SEO
  GET  /v1/jobs/pending ← Local Runner polling
  POST /v1/jobs/{id}/result ← Local Runner callback
  POST /v1/inject      ← WordPress inject
```

---

## Zamknięcie sesji — Definition of Done

Twoja sesja jest kompletna gdy:
- [ ] Heartbeat `"status": "done"` z commit SHA
- [ ] Generuj SEO na `vse.impresjapr.pl/dashboard` działa bez błędu
- [ ] `tobroz@gmail.com` — plan ustawiony na najwyższy, widoczny na dashboardzie
- [ ] Raport w `video-seo-engine/.agents/reports/2026-06-16_vse-dev-05_not-found-fix.md`
- [ ] Raport w `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-05_not-found-fix.md`
- [ ] `project_status.json` w sonic-void zaktualizowany

---

*Supervisor 01 | sonic-void | 2026-06-16 14:15 (update: +plan upgrade tobroz@gmail.com)*
