## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

Przeczytaj protokół dispatch:
`sonic-void/.agents/protocols/dispatch-system-block.md` (GitHub MCP)

Przeczytaj raport diagnozy (kontekst obowiązkowy):
`video-seo-engine/.agents/reports/2026-06-29_vse-strateg-01_kurier-diagnoza.md`

---

# DISPATCH VSE-DEV-03A — Portal Management: Backend (DB + API + Pipeline + bugi)

**Callsign:** vse-dev (Pro High)  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 WYSOKI  
**Część:** A/2 — po tym dispatchu nastąpi DISPATCH-VSE-DEV-03B (Frontend)

---

## Cel

Zbudować backendową warstwę zarządzania portalami:
- DB: tabela `wp_portals` z kolumną `profile_id`
- API: CRUD portali
- Pipeline: inject używa portalu z DB, profil YAML przekazywany do `inject_video()`
- 3 bugi naprawione

Frontend (Dispatch B) startuje dopiero po Twoim raporcie.

---

## Kontekst

### Obecny stan DB:
```
Tabela wp_portals:
- id, name, url, wp_username, wp_app_password
- 1 rekord: Kurier365 | https://kurier365.pl | blastotoprowpku
- Prawy.pl: BRAK rekordu (credentials tylko z frontendu/localStorage)
```

### Obecny przepływ (zepsuty):
1. Generate: używa `profile_id` (np. `kurier365`) z frontendu
2. Inject: używa `site_config` z frontendu (osobny model, nie zna profilu)
3. Skutek: `inject_video()` nie dostaje profilu → brand = hardcoded "Prawy TV" dla każdego portalu

### Decyzja właściciela produktu:
- DB = jedyne źródło prawdy o portalach
- Stare rekordy: wyczyść (użytkownik doda portale przez UI po implementacji Frontendu)
- Prawy.pl i Kurier365 zostaną dodane przez formularz — NIE przez migrację

---

## Zakres

### 1. Migration DB

Użyj istniejącego mechanizmu migracji (sprawdź czy projekt używa alembic lub auto_migrate).

```sql
-- Dodaj kolumnę profile_id
ALTER TABLE wp_portals ADD COLUMN profile_id VARCHAR(100);

-- Wyczyść stare rekordy (użytkownik doda portale przez UI po Froncie)
DELETE FROM wp_portals;
```

**Uwaga:** NIE wpisuj credentials prawy.pl ani kurier365 do migracji. Użytkownik doda je sam.

### 2. Backend API — CRUD portali

Stworzony plik: `api/routers/portals.py` (lub dopisz do istniejącego)

#### GET /v1/portals
```python
# Zwraca listę portali. NIE zwraca wp_app_password.
class PortalResponse(BaseModel):
    id: int
    name: str
    url: str
    wp_username: str
    profile_id: Optional[str] = None
```

#### POST /v1/portals
```python
class PortalCreate(BaseModel):
    name: str            # "Prawy.pl"
    url: str             # "https://prawy.pl"
    wp_username: str
    wp_app_password: str
    profile_id: Optional[str] = None  # "prawy", "kurier365", None

# Walidacja: jeśli profile_id podany,
# sprawdź czy plik profiles/{profile_id}.yaml istnieje.
# Jeśli nie → HTTP 400 z informacją.
```

#### DELETE /v1/portals/{portal_id}
```python
# Usuń portal z DB. HTTP 404 jeśli nie istnieje.
```

#### GET /v1/portals/{portal_id}/full
```python
# TYLKO do użytku wewnętrznego (pipeline).
# Zwraca pełne dane WŁACZNIE z wp_app_password.
# NIE eksponuj tego endpointu bezpośrednio przez frontend.
class PortalFull(BaseModel):
    id: int
    name: str
    url: str
    wp_username: str
    wp_app_password: str
    profile_id: Optional[str] = None
```

Zarejestruj router w `api/main.py`.

### 3. Pipeline — połączenie Generate → Inject

Plik: `api/services/pipeline.py`

#### Zmiana w GenerateRequest
Zmień `profile_id: Optional[str]` na `portal_id: Optional[int]`.

W logice generate:
```python
# Jeśli portal_id podany:
# 1. Pobierz portal z DB: GET /v1/portals/{portal_id}/full (lub bezpośrednio z DB)
# 2. Wyciągnij profile_id z portalu
# 3. Załaduj profiles/{profile_id}.yaml
# 4. Użyj brand/settings z profilu jak dotychczas
# 5. Zapisz portal_id w job (do użytku przez inject)
```

#### Zmiana w `_create_wp_post()` (inject)
```python
async def _create_wp_post(job_id, schema_data, ...):
    # Pobierz portal_id z job
    portal = await get_portal_full(portal_id)  # z DB
    
    # Załaduj profil YAML
    profile_config = load_yaml(f"profiles/{portal.profile_id}.yaml") if portal.profile_id else {}
    
    # Przekaż do inject_video -- naprawia BUG #2
    await inject_video(
        wp_base_url=portal.url,
        wp_user=portal.wp_username,
        wp_app_pass=portal.wp_app_password,
        profile=profile_config,  # <-- kluczowe
        ...
    )
```

Jeśli `portal_id` niedostępny w job — fallback na dotychczasowy `site_config` z requestu (backward compat dla "Wpisz ręcznie" które zostanie w Froncie).

---

## Bug fixes

### BUG #1 — Graceful handling RankMath (KRYTYCZNY)

Plik: `core/injector.py` → funkcja `update_rankmath_meta()`

```python
# PRZED (crash):
resp = requests.post(url, json=payload, auth=auth, timeout=20)
data = resp.json()  # JSONDecodeError gdy body puste

# PO (graceful):
resp = requests.post(url, json=payload, auth=auth, timeout=20)
if not resp.text.strip():
    logger.error(
        "  RankMath FAIL WP#%s: empty response body (HTTP %s) "
        "\u2014 sprawdź czy endpoint rankmath/v1/updateMeta jest aktywny na tym portalu",
        wp_id, resp.status_code
    )
    return False
try:
    data = resp.json()
except ValueError as exc:
    logger.error(
        "  RankMath FAIL WP#%s: invalid JSON — %s | body: %r",
        wp_id, exc, resp.text[:200]
    )
    return False
```

### BUG #2 — Brand "Prawy TV" w alt-text

Naprawiony przez zmianę pipeline (pkt 3 powyżej) — profil jest teraz przekazywany.  
Sprawdź że `inject_video()` faktycznie używa `profile.get("display_name", "VSE")` jako fallback (nie "Prawy TV").

W `core/injector.py` zmień fallback:
```python
# PRZED:
portal_name = (profile or {}).get("display_name", "Prawy TV")
# PO:
portal_name = (profile or {}).get("display_name", "Portal")
```

### BUG #5 — json-repair

```
# requirements.txt — dodaj linię:
json-repair>=0.30.0
```

Po dodaniu — rebuild i restart kontenera:
```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  "cd /home/ubuntu/video-seo-engine && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api"
```

---

## Weryfikacja backendu

Po deploy — sprawdź lokalnie (lub przez SSH curl):

```bash
# Lista portali (pusta po DELETE)
curl https://vse.impresjapr.pl/api/v1/portals
# Oczekiwane: []

# Dodaj portal testowy
curl -X POST https://vse.impresjapr.pl/api/v1/portals \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","url":"https://test.pl","wp_username":"admin","wp_app_password":"test","profile_id":"prawy"}'
# Oczekiwane: {"id":1, "name":"Test", ...} (bez wp_app_password)

# Usuń testowy rekord
curl -X DELETE https://vse.impresjapr.pl/api/v1/portals/1
```

---

## Deliverable

- [ ] Migration: `ADD COLUMN profile_id` + `DELETE` stare rekordy
- [ ] API: `GET/POST/DELETE /v1/portals` + `GET /v1/portals/{id}/full`
- [ ] Pipeline: `portal_id` w GenerateRequest, inject pobiera portal z DB
- [ ] Pipeline: profil YAML przekazywany do `inject_video()`
- [ ] BUG #1: graceful RankMath w `core/injector.py`
- [ ] BUG #2: fallback brand zmieniony z "Prawy TV" na "Portal"
- [ ] BUG #5: `json-repair` w requirements + rebuild
- [ ] Deploy na VPS
- [ ] Weryfikacja API (curl testy)

**Dual-write raport:**
- `video-seo-engine/.agents/reports/2026-06-29_vse-dev_portal-backend.md`
- `sonic-void/.agents/reports/inbox/2026-06-29_vse-dev_portal-backend.md`

Heartbeat `status: done` po zakończeniu.  
Następny dispatch: **DISPATCH-VSE-DEV-03B** (Frontend) — startuje po zatwierdzeniu przez Supervisora.

---

*[Supervisor 01 | sonic-void 29.06.2026]*
