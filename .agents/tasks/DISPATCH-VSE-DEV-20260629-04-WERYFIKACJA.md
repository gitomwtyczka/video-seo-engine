# DISPATCH VSE-DEV-04 — Weryfikacja + E2E test po Portal Management

**Callsign:** vse-dev (Pro High)
**Projekt:** video-seo-engine
**Data:** 2026-06-29
**Priorytet:** 🔴 WYSOKI

---

## Kontekst (obowiązkowy do przeczytania)

W tej sesji zostały wdrożone 2 duże dispatche:
- **03A** (Backend): API portali, migracja DB, bugfixy RankMath/brand/json-repair
- **03B** (Frontend): Nowy dropdown portali z DB, modal dodawania, usunięte hardcoded

Deploy wykonał Supervisor (niezgodnie z rolą) i ręcznie wykonał migrację SQL:
```sql
ALTER TABLE transcript_jobs ADD COLUMN IF NOT EXISTS portal_id INTEGER;
ALTER TABLE wp_portals ADD COLUMN IF NOT EXISTS profile_id VARCHAR(100);
DELETE FROM wp_portals;  -- wyczyszczone, użytkownik doda portale przez UI
```

Status kontenerów na VPS (147.224.162.100):
- `vse-api` — **Uruchomiony** po rebuild
- `vse-web` — **Uruchomiony** po rebuild
- `vse-postgres` — **Healthy**

---

## Twój cel

**Krok 1:** Zweryfikuj że backend działa poprawnie
**Krok 2:** Jeśli coś nie działa — napraw i deployuj
**Krok 3:** Raport do Supervisora z wynikami

---

## Weryfikacja backendu (zrób SSH)

```bash
# Połącz się z VPS:
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100

# Test 1: api /v1/portals zwraca []
curl -s http://localhost:8000/v1/portals
# Oczekiwane: [] lub wynik z JWT jeśli endpoint jest chroniony

# Jeśli 404 lub błąd — sprawdź logi:
docker logs vse-api --tail 50

# Test 2: sprawdzić czy router portals jest w app
docker exec vse-api grep -r 'portals' /app/api/routers/ 2>/dev/null | head -5

# Test 3: czy kolumna portal_id istnieje w DB
docker exec vse-postgres psql -U vse -d vse -c "SELECT column_name FROM information_schema.columns WHERE table_name='transcript_jobs' AND column_name='portal_id'"

# Test 4: czy wp_portals ma profile_id
docker exec vse-postgres psql -U vse -d vse -c "SELECT column_name FROM information_schema.columns WHERE table_name='wp_portals'"
```

## Weryfikacja frontendu

```bash
# Sprawdź logi frontendu
docker logs vse-web --tail 30

# Curl do strony dashboard
curl -s -o /dev/null -w "%{http_code}" https://vse.impresjapr.pl/dashboard
# Oczekiwane: 200
```

---

## Znane problemy do naprawy

Jeśli weryfikacja wyżuwa błędy, napraw i deployuj. Najczęścej spotykane problemy:

### Problem A: Router portals nie zarejestrowany w main.py
```python
# api/main.py — sprawdź czy jest:
from api.routers import portals
app.include_router(portals.router, prefix="/v1")
```

### Problem B: JWT auth blokuje /v1/portals
Jeśli endpoint wymaga autoryzacji a fronted wysyła zapytanie bez tokenu:
- Sprawdź czy w nowym `use-portals.ts` (frontend) token JWT jest załączany w headerze
- Lub dodaj `/v1/portals` do whitelist publicznych endpointów jeśli była taka decyzja

### Problem C: Model PortalResponse nie ma wymaganych pól
- Sprawdź `api/models/portal.py` lub równoważny plik z Pydantic modelem

---

## Wymagane pliki do sprawdzenia (GitHub MCP)

```
gitomwtyczka/video-seo-engine/main:
- api/main.py (czy router portals włączony)
- api/routers/portals.py (czy istnieje)
- web/src/app/dashboard/dashboard-inner.tsx (nowy dropdown)
- web/src/app/dashboard/use-portals.ts (hook do /v1/portals)
```

---

## Deliverable

- [ ] Weryfikacja: API /v1/portals zwraca poprawną odpowiedź
- [ ] Weryfikacja: Frontend dashboard się ładuje bez błędów
- [ ] Fix + deploy jeśli coś nie działa
- [ ] Raport: wyniki weryfikacji + lista naprawionych rzeczy

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-dev_weryfikacja-portal.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-dev_weryfikacja-portal.md`

Heartbeat `status: done`.

---

*[Supervisor 01 | sonic-void 29.06.2026]*
