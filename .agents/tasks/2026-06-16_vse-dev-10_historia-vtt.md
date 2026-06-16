## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**Twój callsign:** `[vse-dev-10 | video-seo-engine]`  
**Workspace:** video-seo-engine  
**Sugerowany model:** Claude Sonnet

---

# TASK: vse-dev-10 — Historia UX + VTT Timestamps Fix

**Data:** 2026-06-16  
**Dispatch from:** Supervisor 03  
**Priorytet:** 🔴 PILNE

---

## 📚 KROK 0b — Przeczytaj kontekst projektu (OBOWIĄZKOWE)

Przed czymkolwiek przeczytaj przez GitHub MCP:
1. `docs/ARCHITECTURE.md` — stack, kontenery, porty
2. `ROADMAP.md` — co zrobione, co w toku

---

## Twój deliverable:

1. **Historia UX** — kliknięcie wpisu historii ładuje pełne wyniki (schema, artykuł, rozdziały)
2. **VTT Timestamps fix** — rozdziały mają prawdziwe czasy zamiast `[00:00]`
3. **Jeden rebuild** na końcu

---

## ETAP 1 — Historia: dostęp do treści (UX fix)

### Problem:
Strona `/historia` pokazuje tylko link do video i status. Użytkownik nie może wrócić do wygenerowanego artykułu/schematu z poprzedniej sesji.

### Oczekiwane zachowanie:
```
/historia:
  [link video] [tytuł] [data] [status] [🔍 Otwórz wyniki →]
  [link video] [tytuł] [data] [status] [🔍 Otwórz wyniki →]

  Klik „Otwórz wyniki” → /dashboard?job_id=X
  Dashboard wykrywa ?job_id i ładuje dane z DB zamiast czekać na nowe generowanie
```

### Implementacja:

**Krok 1:** Sprawdź `api/routers/jobs.py` (GitHub MCP) — czy endpoint `GET /v1/jobs/{job_id}` zwraca pełne `schema_data`.

**Krok 2:** Dodaj link `Otwórz wyniki` w `web/src/app/historia/page.tsx` — każdy wiersz historii ma przycisk:
```tsx
<Link href={`/dashboard?job_id=${job.id}`}>Otwórz wyniki →</Link>
```

**Krok 3:** W `web/src/app/dashboard/page.tsx` obsłuż `?job_id` w URL:
```tsx
// useSearchParams() — jeśli job_id w URL, fetch z /v1/jobs/{job_id}
// i wyświetl wyniki bezpośrednio zamiast formularza
```

**Krok 4:** Status w historii — jeśli myliący, popraw label:
- `completed` → `✅ Gotowe`
- `processing` → `⏳ W trakcie`
- `pending` → `⏳ W kolejce`
- `failed` → `❌ Błąd`

---

## ETAP 2 — VTT Timestamps = 0 (diagnoza i fix)

### Problem:
Rozdziały zawsze pokazują `[00:00] Tytuł` zamiast prawdziwych timestampów.

DEV-06 miał to naprawić (runner zwraca `__VTT__\n[MM:SS] tekst`). Sprawdź gdzie się gubią.

### Diagnoza — kolejność:

**Krok 1:** Sprawdź ostatni job w bazie:
```powershell
# Znajdź nazwy kontenerów:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker ps --format '{{.Names}}'"

# Sprawdź ostatni job i jego schema_data.chapters:
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "docker exec [DB_CONTAINER] psql -U [USER] -d [DB] -c \"SELECT id, status, schema_data->'chapters' FROM transcript_jobs ORDER BY created_at DESC LIMIT 3;\""
```

**Jeśli chapters w DB ma prawidłowe timestamps** → bug jest w `page.tsx` (frontend nie parsuje poprawnie)

**Jeśli chapters w DB ma `start_time: 0`** → bug jest w backendzie:
- Sprawdź `api/services/pipeline.py` (GitHub MCP) — sekcja parsowania `__VTT__`
- Sprawdź `api/routers/jobs.py` — czy wynik runnera jest zapisywany z oryginalnym VTT

**Krok 2:** Sprawdź format który wysyła runner (znany, nie odkrywaj):
```
__VTT__
00:15 Wstęp do tematu
02:30 Główna część
05:45 Podsumowanie
```

Format czasów może być `MM:SS` lub `HH:MM:SS` — parser musi obsłużyć oba.

**Krok 3:** Napraw w znalezionym miejscu.

---

## ETAP 3 — Deploy

```powershell
ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100 "cd /opt/vse && git pull origin main && docker compose -f docker-compose.vse.yml up -d --build vse-web vse-api"
```

Jeśli fix był tylko w backendzie (`pipeline.py`) — rebuild tylko `vse-api`.
Jeśli był też w frontendzie (`page.tsx`) — rebuild `vse-web` też.

### Weryfikacja:
1. `/historia` — czy przycisk `Otwórz wyniki` jest i prowadzi do dashboardu z danymi
2. Nowe generowanie: rozdziały mają timestamp `[02:30]` zamiast `[00:00]`

---

## Dostęp

- GitHub MCP: `gitomwtyczka/video-seo-engine` branch `main`
- SSH VPS: `ssh -i ~/.ssh/oracle-crimson.key ubuntu@147.224.162.100`
- **FILE BRIDGE / Wetty: ZAKAZ**

---

## Raport po wykonaniu

1. `video-seo-engine/.agents/reports/2026-06-16_vse-dev-10_historia-vtt.md`
2. `sonic-void/.agents/reports/inbox/2026-06-16_vse-dev-10_historia-vtt.md`

**Dual-write OBOWIĄZKOWY.**

---

## Protokół callsign

```
[vse-dev-10 | video-seo-engine DD.MM.YYYY HH:MM] online
...
[vse-dev-10 | video-seo-engine DD.MM.YYYY HH:MM] — status
```

---

*Supervisor 03 | sonic-void | 2026-06-16 20:48*
