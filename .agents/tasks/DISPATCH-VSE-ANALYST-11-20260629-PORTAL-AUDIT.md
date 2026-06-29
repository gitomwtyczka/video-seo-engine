# DISPATCH VSE-ANALYST-11 — Audyt kodu portali: co zrobiono vs co działa na produkcji

**Callsign:** vse-analyst (Pro High)
**Projekt:** video-seo-engine
**Data:** 2026-06-29
**Priorytet:** 🔴 WYSOKI
**Typ:** CODE AUDIT — tylko analiza, zero zmian w kodzie

---

## Kontekst (obowiązkowy)

W sesji 29.06.2026 wykonano dwa dispatche:
- **DISPATCH-03A** — backend portali (commit `bc0fe988`)
- **DISPATCH-03B** — frontend portali (commit przez gh api, brak SHA)

Deploy wykonał Supervisor (nie worker) przez docker compose na VPS.
Migracja DB wykonana ręcznie przez Supervisora (ALTER TABLE + DELETE FROM).

**Obserwowany symptom:** Kliknięcie `+ Dodaj nowy portal` na produkcji (`https://vse.impresjapr.pl/dashboard`) **nic nie robi** — brak modalu, brak rekcji UI.

**Cel tego dispatcha:** Ustalić DOKŁADNIE co jest nie tak i gdzie — żeby następny worker dostał precyzyjny jednopunktowy fix, nie szeroką weryfikację.

---

## Stan VPS (zweryfikowany przez SSH przez Supervisora)

```
vse-web     Up 24 min    0.0.0.0:3001->3001/tcp
vse-api     Up 49 min    0.0.0.0:8085->8085/tcp
vse-postgres Healthy      127.0.0.1:5434->5432/tcp
```

`GET http://localhost:8085/v1/portals` → **HTTP 401** (endpoint ISTNIEJE, auth działa)

Frontend: `https://vse.impresjapr.pl/dashboard` ładuje się poprawnie, dropdown pokazuje "Brak portali — dodaj pierwszy portal".

---

## Znana rozbieżność #1 do weryfikacji

Supervisor zauważył:

**`use-portals.ts` (frontend) wywołuje:**
```
GET /v1/portals/${portalId}/credentials
```

**`api/routers/portals.py` (backend) definiuje:**
```python
@router.get("/{portal_id}/full", response_model=PortalFull)
```

→ Endpoint `/credentials` nie istnieje. Frontend dostanie 404 przy próbie pobrania hasła do publikacji.
→ **Nie blokuje to dodawania portalu** — blokuje publikację. Ale wymaga naprawy.

---

## Twoje zadania (TYLKO ANALIZA)

### Zadanie A: Sprawdź `dashboard-inner.tsx` — handler `+ Dodaj nowy portal`

Plik: `gitomwtyczka/video-seo-engine/main: web/src/app/dashboard/dashboard-inner.tsx`

Szukaj:
1. Gdzie jest opcja `+ Dodaj nowy portal` w dropdownie?
2. Czy ma `onClick` handler? Czy jest zdefiniowany?
3. Czy jest stan `showAddPortalModal` lub podobny? Czy jest `useState`?
4. Czy modal `AddPortalModal` (lub podobny komponent) w ogóle istnieje w pliku?
5. Czy jest gdzieś importowany zewnętrzny komponent modalu?

Oczekiwany pattern z DISPATCH-03B:
```tsx
// Dropdown option:
{ value: '__add__', label: '+ Dodaj nowy portal...' }
// onClick should open modal state:
if (value === '__add__') setShowAddPortalModal(true)
// Modal component should render AddPortalForm or similar
```

Jeśli `setShowAddPortalModal` nie istnieje lub modal nie jest renderowany → **to jest przyczyna bugа**.

### Zadanie B: Sprawdź połączenie `usePortals` z komponentem

1. Czy `usePortals()` jest wywołany w `dashboard-inner.tsx`?
2. Czy `createPortal` z hooka jest użyty?
3. Czy `portals` z hooka trafia do dropdown?

### Zadanie C: Potwierdź rozbieżność `/credentials` vs `/full`

1. W `use-portals.ts` linia `getCredentials`: potwierdź że wywołuje `/credentials`
2. W `api/routers/portals.py`: potwierdź że endpoint to `/full`
3. Sprawdź czy `/credentials` gdziekolwiek istnieje w backendzie

Polecenie sprawdzające (GitHub MCP search w repo):
```
web/src/app/dashboard/use-portals.ts → linia getCredentials
api/routers/portals.py → wszystkie @router.get
```

### Zadanie D: Sprawdź `api/models/portal.py` — model ORM

Plik: `api/models/portal.py`

Sprawdź:
1. Czy model `WpPortal` ma pole `portal_id` jako UUID (nie int)?
2. Dispatch-03B mówi o `portal_id` jako `int` — czy jest niezgodność typów z modelem?
3. Czy kolumna `profile_id` istnieje w modelu?

### Zadanie E: Commit history — co faktycznie weszło

Sprawdź ostatnie 10 commitów na branchu `main`:
```
gitomwtyczka/video-seo-engine — list_commits, branch: main, limit: 10
```

Ustal:
- Które pliki zmieniły się w commicie `bc0fe988` (DISPATCH-03A)?
- Czy istnieje commit z DISPATCH-03B (frontend)? Jeśli tak — które pliki?
- Czy `dashboard-inner.tsx` był modyfikowany?

---

## Format raportu

Raport musi być precyzyjny — format:

```markdown
## BUG #1: [nazwa]
**Plik:** web/src/app/dashboard/dashboard-inner.tsx (linia X)
**Symptom:** Kliknięcie + Dodaj nowy portal nic nie robi
**Przyczyna:** [konkretna linia/brak kodu]
**Fix:** [co dokładnie dodać/zmienić — z linią kodu]

## BUG #2: /credentials vs /full
**Plik:** use-portals.ts linia Y + portals.py
**Symptom:** Publikacja nie działa (credentials 404)
**Fix:** [zmień w use-portals.ts lub portals.py]

## Potwierdzenia OK
- [ ] Router portals zarejestrowany w main.py ✅
- [ ] usePortals hook istnieje ✅
- [ ] ...
```

---

## Deliverable

- [ ] Precyzyjna lista bugów z linią kodu i proponowanym fixem
- [ ] Ocena: czy to 1 fix czy 2+ osobne dispatche
- [ ] Gotowy prompt dla workera-fixera (skopiuj-wklej)

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-analyst_portal-audit.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-analyst_portal-audit.md`

Heartbeat `status: done` po zakończeniu.

---

## Dane startowe (nie musisz szukać — masz je tu)

### `use-portals.ts` — getCredentials (linia ~65):
```ts
const res = await fetch(`${apiUrl}/v1/portals/${portalId}/credentials`, {
```

### `portals.py` — endpoint który istnieje:
```python
@router.get("/{portal_id}/full", response_model=PortalFull)
async def get_portal_full(...):
```

### `main.py` — portals router JEST zarejestrowany:
```python
from api.routers.portals import router as portals_router
# ...
app.include_router(portals_router)  # linia ~87
```
✅ Router OK — to nie jest problem.

### `dashboard-inner.tsx` — 67KB, musisz przeszukać pod kątem:
- `__add__` lub `Dodaj nowy portal`
- `showAddPortal` lub `addPortalModal`
- `usePortals` lub `usePortals()`
- `createPortal`

---

*[Supervisor 01 | sonic-void 29.06.2026]*
