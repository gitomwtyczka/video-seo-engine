# DISPATCH VSE-DEV-36 — Portal bugs fix + comprehensive API tests

**Callsign:** vse-dev
**Data:** 2026-06-30
**Zlecający:** Supervisor 01
**Priorytet:** 🔴 KRYTYCZNY (blokuje generowanie na wszystkich portalach)
**Model:** Gemini Pro
**Workspace:** video-seo-engine

---

## Kontekst — co się zepsuło po D35

User przetestował D35 (inline profile creation) i znalazł dwa krytyczne błędy produkcyjne:

### Bug 1 — Nowy profil (biznesciti): `Input should be a valid string`

- Portal: biznesciti.com (nowo utworzony przez D35)
- Błąd: natychmiastowy, przy próbie generowania
- Prawdopodobna przyczyna: nowy profil YAML ma brakujące lub None pole wymagane przez endpoint generowania (np. `wp_user`, `wp_app_password`, lub inne pole które D33-34 zakłada jako string)
- Zbadaj: co generator dostaje z nowego profilu vs istniejącego (prawy/kurier365)

### Bug 2 — Istniejący portal (kurier365): DB schema mismatch

```
(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
column "portal_id" is of type integer but expression is of type character varying
SQL: INSERT INTO transcript_jobs (..., portal_id, ...) VALUES (..., $6::VARCHAR, ...)
```

- Portal: kurier365.pl (istniejący przed D35)
- Błąd: po fetch YT pojawia się przy próbie zapisu do DB
- Root cause: `transcript_jobs.portal_id` w DB to INTEGER (FK do portals.id), ale kod teraz wysyła string (np. `"kurier365"`)
- Likely regression z D34 lub D35 — sprawdź co zmieniło się w generowaniu/zapisie transcript_jobs

---

## Zadanie

### Krok 1: Diagnoza i fix Bug 1

1. Pobierz istniejący profil prawy.yaml i nowy biznesciti.yaml — porównaj strukturę
2. Znajdź gdzie generator rzuca `Input should be a valid string` — Pydantic validation
3. Fix: upewnij się że nowy profil ma wszystkie wymagane pola (lub generator gracefully obsługuje None)
4. Nie zmieniaj istniejących profili prawy.yaml i kurier365.yaml

### Krok 2: Diagnoza i fix Bug 2

1. Sprawdź schemat tabeli `transcript_jobs` — jaki typ ma `portal_id`
2. Sprawdź gdzie w kodzie `portal_id` jest przekazywany do INSERT — znajdź gdzie string zamiast int
3. Fix opcja A: jeśli portals.id jest integer → przekazuj integer FK (portal.id) nie string
4. Fix opcja B: jeśli to migration drift → napisz migration ALTER COLUMN portal_id TYPE INTEGER
5. Sprawdź czy ten sam bug dotyczy innych tabel korzystających z portal_id

### Krok 3: Comprehensive API tests

Napisz skrypt testowy `tests/test_api_integration.py` (lub `scripts/api_smoke_test.py` jeśli brak pytest na VPS).

**Testy do pokrycia:**

```python
# 1. Health
GET /health → 200

# 2. Profiles
GET /v1/profiles → 200, lista profili zawiera prawy + kurier365
POST /v1/profiles → 201, tworzy nowy profil (użyj portal_id: testportal_{timestamp})
POST /v1/profiles (duplikat) → 409
POST /v1/profiles (zły default_type) → 422
POST /v1/profiles (zły portal_id: spacje, wielkie litery) → 422

# 3. Portals (DB-backed)
GET /v1/portals → 200, lista portali
POST /v1/portals → 201 (jeśli endpoint istnieje)

# 4. Generate flow
POST /v1/generate z istniejącym profilem (prawy) → job started lub content returned
POST /v1/generate z nowym profilem → NIE powoduje "Input should be a valid string"
POST /v1/generate z brakującym portal_id → 422
POST /v1/generate z nieistniejącym portal_id → 404 lub sensowny błąd

# 5. Transcript jobs
Sprawdź że INSERT do transcript_jobs nie rzuca DatatypeMismatchError
```

Skrypt powinien:
- Działać przez `python scripts/api_smoke_test.py https://vse.impresjapr.pl`
- Drukować PASS/FAIL per test
- Nie wymagać autoryzacji (testy publicznych endpointów)
- Cleanupować testowe dane (usuwać testportal_{timestamp}.yaml po teście)

### Krok 4: Deploy i weryfikacja

```bash
git pull origin main && docker compose ... up -d vse-api
```

Uruchom smoke test na produkcji. Obydwa błędy muszą być GONE.

---

## Uwaga od Supervisora — SEO external link

User zgłosił: `seo_external_link` w profilu jest zbędne — VSE jest wpięty w **PressAI** który automatycznie obsługuje linki wewnętrzne i zewnętrzne przy generowaniu artykułu. To pole nie powinno być wymagane ani promowane w UI.

**Akcja:** W tym dispatchu — nie usuwaj pola (backward compat), ale oznacz je jako `deprecated` w komentarzu YAML i ukryj z formularza inline profile creation w AddPortalModal (jeśli jest tam widoczne).

---

## Deliverable

- [ ] Bug 1 fixed — nowe profile generują bez błędu
- [ ] Bug 2 fixed — portal_id type mismatch resolved
- [ ] `scripts/api_smoke_test.py` napisany i działa
- [ ] Deploy na produkcję
- [ ] Testy przechodzą na produkcji
- [ ] Raport dual-write

---

## Zasady

- Nie dotykaj prawy.yaml ani kurier365.yaml
- TypeScript build MUSI przejść bez błędów jeśli dotykasz frontendu
- Każdy fix musi mieć commit z opisem bug ID

---

*[Supervisor 01 | sonic-void 30.06.2026]*
