# DISPATCH — vse-dev-05 | Naprawa „Not Found” przy generowaniu SEO

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

## Problem do naprawy

**Symptom:** Na dashboardzie `vse.impresjapr.pl/dashboard` po wklejeniu URL YouTube i kliknięciu „Generuj SEO” — pojawia się:
```
⚠️ Wystąpił błąd
Not Found
```

**Hipoteza główna:** nginx change z DEV-04 (`location /v1/`) zepsuł routing dla głównego endpointu generowania SEO.

W crimson-void kolejność bloków w `nginx/default.conf` jest KRYTYCZNA:
- `/api/auth/` musi być PRZED `/api/` (NextAuth przed FastAPI)
- Jeśli DEV-04 dodał `/v1/` w złym miejscu — może zakłócać routing `/v1/generate` lub `/v1/inject`

**Alternatywna hipoteza:** Frontend wywołuje inny endpoint niż ten który istnieje w FastAPI (np. `/v1/generate` vs `/api/v1/generate`).

---

## Twoje zadanie

### Krok 1 — Diagnoza

Przed jakimikolwiek zmianami:

1. Przeczytaj aktualny `nginx/default.conf` z crimson-void (GitHub MCP, branch main)
2. Przeczytaj aktualny `api/routers/` — jakie endpointy istnieją?
3. Przeczytaj frontend — co wywołuje po kliknięciu „Generuj SEO”? Sprawdz `web/src/` lub `frontend/` — fetch/axios call do jakiego URL?
4. Porównaj: czy nginx ma location dla tego endpointu? Czy proxy_pass jest na właściwy port?

### Krok 2 — Fix

Naprawa musi być minimalna i precyzyjna:
- Jeśli problem w nginx: popraw tylko kolejność lub brakujący `location` block
- Jeśli problem w froncie: popraw URL endpointu
- Jeśli problem w FastAPI: dodaj brakujący router/endpoint

### Krok 3 — Deploy i weryfikacja

```bash
# SSH na oracle
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100

# Rebuild tylko niezbędnych kontenerów
cd /home/ubuntu/video-seo-engine
git pull origin main
docker compose up -d --no-deps --force-recreate vse-api
# i/lub
docker compose up -d --no-deps --force-recreate nginx
```

**Test weryfikacyjny:**
- Wklej URL YouTube na `vse.impresjapr.pl/dashboard`
- Kliknij „Generuj SEO”
- Oczekiwany wynik: generowanie działa (może zwrócić transcript pending — to OK)

---

## Ważne zasady (nie łam!)

1. **nginx kolejność:** `/api/auth/` ZAWSZE przed `/api/` ZAWSZE przed `/v1/` ZAWSZE przed `/` (location specificity)
2. **Nie ruszaj** `dc3709f` — Local Runner działa, nie psuj
3. **Nie ruszaj** `125477c` — logowanie naprawione
4. Testuj na SSH po każdej zmianie nginx: `docker compose logs nginx --tail=20`

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
- [ ] Raport w `video-seo-engine/.agents/reports/2026-06-16_vse-dev-05_not-found-fix.md`
- [ ] Raport w `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-05_not-found-fix.md`
- [ ] `project_status.json` w sonic-void zaktualizowany (pole `video-seo-engine`)

---

*Supervisor 01 | sonic-void | 2026-06-16 14:14*
