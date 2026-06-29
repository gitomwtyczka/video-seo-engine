## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

Przeczytaj protokół dispatch:
`sonic-void/.agents/protocols/dispatch-system-block.md` (GitHub MCP)

Przeczytaj raport diagnozy (kontekst obowiązkowy):
`video-seo-engine/.agents/reports/2026-06-29_vse-strateg-01_kurier-diagnoza.md`

---

# DISPATCH VSE-DEV-02 — Portal Management: credentials + profil powiązany

**Callsign:** vse-dev (Flash High)  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 WYSOKI — blokuje multi-portal i RankMath 80+

---

## Cel sesji

Zaimplementować pełny system zarządzania portalami WordPress:
- portal = credentials (url, user, pass) + powiązany profil YAML (`profile_id`)
- Generate i Inject używają tego samego portalu → jedno źródło prawdy
- Po tej implementacji: dodanie nowego portalu (np. nowy-portal.pl) = 1 rekord w UI, bez dotykania kodu

Przy okazji: naprawić 3 bugi z raportu diagnozy (BUG #1, #2, #5).

---

## Kontekst — co mamy teraz (WAŻNE przeczytaj)

### Obecny przepływ (zepsuty):
1. **Generate**: używa `profile_id` z request → OK, brand/chapters poprawne
2. **Inject**: używa `site_config` z frontendu (url + user + pass) → osobny model, nie zna `profile_id`
3. **Skutek**: Inject nie wie dla jakiego portalu generował → bug "Prawy TV" w alt-text, brak profilu w `inject_video()`

### Tabela `wp_portals` w DB:
Ma już kolumny: `id`, `name`, `url`, `wp_username`, `wp_app_password`  
Brakuje: `profile_id` (link do YAML profilu)

### Zmienne środowiskowe:
`.env` na VPS **NIE MA** żadnych `WP_*` zmiennych. Credentials wpisywane ręcznie przez frontend. To nie zmienia się w tej implementacji — DB będzie nowym źródłem prawdy.

### Stan DB (zbadany):
Tabela `wp_portals` ma 1 rekord: Kurier365 | https://kurier365.pl | blastotoprowpku  
Prawy.pl: **brak rekordu** — credentials przychodzą tylko z frontendu

---

## Zakres implementacji

### 1. Migration DB — dodać `profile_id` do `wp_portals`

```sql
ALTER TABLE wp_portals ADD COLUMN profile_id VARCHAR(100);
-- Przykład: 'kurier365', 'prawy', 'nowy-portal'
-- NULL = portal bez przypisanego profilu YAML (fallback na defaults)
```

Użyj istniejącego mechanizmu migracji projektu (auto_migrate lub alembic — sprawdź co projekt używa).

Po migracji uzupełnij istniejący rekord:
```sql
UPDATE wp_portals SET profile_id = 'kurier365' WHERE name = 'Kurier365';
```

Dodaj rekord dla prawy.pl (przenieś z "nigdzie" do DB):
```sql
INSERT INTO wp_portals (name, url, wp_username, wp_app_password, profile_id)
VALUES ('Prawy.pl', 'https://prawy.pl', '[wp_user_prawy]', '[wp_app_pass_prawy]', 'prawy');
-- UWAGA: credentials prawy.pl weź z aktualnej konfiguracji frontendu/localStorage
-- Zapytaj właściciela jeśli nie masz dostępu do tych credentials
```

### 2. Backend API — CRUD portali

#### GET /v1/portals
Zwróć listę portali z DB. **NIE zwracaj `wp_app_password` w response** (bezpieczeństwo).

```python
# Response model
class PortalResponse(BaseModel):
    id: int
    name: str
    url: str
    wp_username: str
    profile_id: Optional[str]
    # NIE: wp_app_password
```

#### POST /v1/portals
Utwórz nowy portal. Przyjmij credentials, zapisz do DB.

```python
class PortalCreate(BaseModel):
    name: str          # "Mój Portal"
    url: str           # "https://moj-portal.pl"
    wp_username: str   # "admin"
    wp_app_password: str  # Application Password z WP
    profile_id: Optional[str]  # "kurier365", "prawy", None
```

Walidacja: sprawdź czy `profile_id` odpowiada istniejącemu plikowi w `profiles/{profile_id}.yaml`. Jeśli plik nie istnieje i `profile_id` nie jest None → error 400.

#### GET /v1/portals/{portal_id}/full
Endpoint **tylko dla backendu** (nie frontendowy) — zwraca pełne dane włącznie z `wp_app_password`. Używany przez pipeline przy inject.

### 3. Pipeline — połączenie Generate + Inject przez portal

W `api/services/pipeline.py`:

**Generate:** przy `profile_id` z request → sprawdź czy istnieje portal z tym `profile_id` w DB → jeśli tak, załaduj dane portalu do kontekstu generowania (brand, display_name).

**Inject (`_create_wp_post`):** 
- Zmień sygnaturę: dodaj `portal_id: Optional[int]` lub `profile_id: Optional[str]`
- Jeśli `portal_id` dostępny → pobierz pełne dane portalu z DB (credentials + profile_id)
- Przekaż `profile` dict (z YAML) do `inject_video()` — to naprawi BUG #2

Model łączący:
```python
# Przy GenerateRequest z profile_id
# → znajdź portal w DB po profile_id
# → zapisz portal_id w job/sesji
# → Inject używa tego portal_id
```

### 4. Frontend — dropdown portali

Obecny dropdown: `"Wpisz ręcznie..."` + pola ręczne.

Nowy dropdown:
- `GET /v1/portals` → lista portali z DB
- Opcje: `[Prawy.pl] [Kurier365] [+ Dodaj portal] [Wpisz ręcznie...]`
- Wybór portalu z listy: auto-wypełnia URL i username (ale NIE hasło — to pobierane z DB przez backend)
- `Wpisz ręcznie`: jak dotychczas (fallback)

Modal `+ Dodaj portal`:
```
Nazwa portalu: [________________]
URL WordPress: [https://...      ]
Użytkownik WP: [________________]
Application Password: [__________]
Profil treści: [dropdown: kurier365 / prawy / (brak)]
[Zapisz portal]
```

Po zapisaniu: dropdown odświeża listę, nowy portal dostępny do wyboru.

**Ważne**: Application Password nie jest wyświetlane po zapisaniu — tylko `●●●●●●●●`. Credentials są przechowywane w DB (backend), nie w localStorage.

### 5. Powiązanie portalu z generowaniem

When user selects portal from dropdown:
- Frontend: wysyła `portal_id` (lub `profile_id`) w `GenerateRequest`
- Backend: ładuje profil YAML dla tego portalu (brand, SEO settings, chapter_class)
- Inject: automatycznie używa credentials z DB dla tego portalu

**Użytkownik nie musi już wpisywać niczego ręcznie** — raz dodany portal = zawsze dostępny.

---

## Bug fixes (przy okazji — wymagane)

### BUG #1 — Graceful handling w update_rankmath_meta()

Plik: `core/injector.py` → funkcja `update_rankmath_meta()`

Aktualny kod (crash):
```python
resp = requests.post(url, json=payload, auth=auth, timeout=20)
data = resp.json()  # JSONDecodeError gdy body puste
```

Fix:
```python
resp = requests.post(url, json=payload, auth=auth, timeout=20)
if not resp.text.strip():
    logger.error(
        "  RankMath FAIL WP#%s: empty response body (HTTP %s) — endpoint może być niedostępny",
        wp_id, resp.status_code
    )
    return False
try:
    data = resp.json()
except ValueError as e:
    logger.error("  RankMath FAIL WP#%s: invalid JSON — %s | body: %r", wp_id, e, resp.text[:200])
    return False
```

### BUG #2 — Brand "Prawy TV" w alt-text

Plik: `api/services/pipeline.py` → `_create_wp_post()` lub `inject_video()` call

Aktualny problem: `inject_video()` wywoływane bez `profile` dict → fallback `"Prawy TV"`

Fix: przekazać `profile_config` (dict z YAML) do `inject_video(profile=profile_config)`.  
Jeśli portal ma `profile_id` → załaduj `profiles/{profile_id}.yaml` i przekaż.

### BUG #5 — json-repair

```
# requirements.txt — dodaj:
json-repair>=0.30.0

# Następnie rebuild Docker:
docker compose -f docker-compose.vse.yml build vse-api
docker compose -f docker-compose.vse.yml up -d vse-api
```

---

## Test po implementacji

1. Wejdź do dashboard VSE
2. `+ Dodaj portal` → wpisz dane kurier365 (url, user, app_pass, profil: kurier365)
3. Wygeneruj artykuł → wybierz portal `Kurier365` z dropdown
4. Opublikuj
5. Sprawdź w WP admin kurier365:
   - Artykuł stworzony ✓
   - Fraza kluczowa w RankMath ustawiona ✓
   - Alt-text thumbnajla: `[keyphrase] | Kurier365` (nie "Prawy TV") ✓
   - Bloki Gutenberga renderują bez błędów ✓
6. Sprawdź RankMath score — cel: 70+

---

## Deliverable

- [ ] Migration: kolumna `profile_id` w `wp_portals`
- [ ] API: GET/POST `/v1/portals` + GET `/v1/portals/{id}/full`
- [ ] Pipeline: inject używa portalu z DB → profil przekazywany
- [ ] Frontend: dropdown z listą portali + modal dodawania
- [ ] BUG #1: graceful RankMath w `core/injector.py`
- [ ] BUG #2: profil przekazywany do `inject_video()`
- [ ] BUG #5: `json-repair` w requirements + rebuild
- [ ] Deploy na VPS + test E2E

**Dual-write raport:**
- `video-seo-engine/.agents/reports/YYYY-MM-DD_[callsign]_portal-management.md`
- `sonic-void/.agents/reports/inbox/YYYY-MM-DD_[callsign]_portal-management.md`

Heartbeat `status: done` po zakończeniu.

---

*[Supervisor 01 | sonic-void 29.06.2026]*
