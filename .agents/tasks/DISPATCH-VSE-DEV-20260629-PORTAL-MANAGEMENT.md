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
- Generate i Inject używają tego samego portalu → jedno źródło prawdy (DB)
- Po tej implementacji: dodanie nowego portalu = 1 rekord w UI, bez dotykania kodu

Przy okazji: naprawić 3 bugi z raportu diagnozy (BUG #1, #2, #5).

---

## Kontekst — co mamy teraz (WAŻNE przeczytaj)

### Obecny przepływ (zepsuty):
1. **Generate**: dropdown "Portal docelowy" ma hardcoded/localStorage wpisy (Kurier365.pl, Prawy.pl)
2. **Inject**: modal "Wyślij do portalu" wymaga ręcznego wpisania credentials każdorazowo
3. **Problem**: Generate nie przekazuje wybranego portalu do Inject → użytkownik musi wpisywać ręcznie
4. **Bug**: Inject nie zna `profile_id` → brand w alt-text = hardcoded "Prawy TV" dla każdego portalu

### Stan DB:
- Tabela `wp_portals`: ma kolumny `id`, `name`, `url`, `wp_username`, `wp_app_password`
- Ma 1 rekord: Kurier365 | https://kurier365.pl | blastotoprowpku
- Prawy.pl: **brak rekordu** — credentials w localStorage/hardcoded
- Brakuje kolumny: `profile_id`

### Decyzja właściciela produktu:
> "Czyścimy i dodajemy od nowa. Prawy.pl i Kurier365 zostaną dodane przez formularz po implementacji."

Oznacza to: **WSZYSTKIE hardcoded i localStorage wpisy portali mają być usunięte z frontendu.** DB jest jedynym źródłem prawdy.

---

## Zakres implementacji

### 1. Baza danych

**Migration: dodaj `profile_id` do `wp_portals`**
```sql
ALTER TABLE wp_portals ADD COLUMN profile_id VARCHAR(100);
```
Użyj istniejącego mechanizmu migracji projektu.

**Czyść istniejący rekord Kurier365** — zostanie ponownie dodany przez użytkownika przez UI:
```sql
DELETE FROM wp_portals;  -- lub TRUNCATE
```

Uwaga: App password dla kurier365 nie będzie potrzebny — użytkownik wpisze je sam przez formularz. Nie trzymaj credentials w kodzie ani migracjach.

### 2. Backend API — CRUD portali

#### GET /v1/portals
Zwróć listę portali z DB. **NIE zwracaj `wp_app_password`** (bezpieczeństwo).

```python
class PortalResponse(BaseModel):
    id: int
    name: str
    url: str
    wp_username: str
    profile_id: Optional[str]  # np. 'kurier365', 'prawy'
    # NIE: wp_app_password
```

#### POST /v1/portals
Utwórz nowy portal. Waliduj `profile_id` — plik `profiles/{profile_id}.yaml` musi istnieć.

```python
class PortalCreate(BaseModel):
    name: str           # "Prawy.pl"
    url: str            # "https://prawy.pl"
    wp_username: str    # "admin"
    wp_app_password: str  # Application Password z WP
    profile_id: Optional[str]  # "prawy", "kurier365", None
```

#### DELETE /v1/portals/{portal_id}
Usuń portal z DB.

#### GET /v1/portals/{portal_id}/full (TYLKO internal/backend)
Zwraca pełne dane z `wp_app_password`. Używany przez pipeline przy inject.

### 3. Frontend — nowy dropdown "Portal docelowy"

**Usunąć z frontendu:**
- Wszelkie hardcoded listy portali (Kurier365.pl, Prawy.pl)
- Wszelki kod czytający portale z localStorage
- Pola ręcznego wpisywania credentials w modalu "Wyślij do portalu" (URL, user, pass)

**Nowy dropdown "Portal docelowy":**
```
Portal docelowy ▼
─────────────────────────
  (lista portali z GET /v1/portals)
─────────────────────────
  + Dodaj nowy portal...
```

**Modal "Dodaj nowy portal"** (otwiera się z dropdown):
```
Nazwa portalu:       [________________]
URL WordPress:       [https://...      ]
Użytkownik WP:       [________________]
Application Password: [________________]
Profil treści:       [dropdown: prawy / kurier365 / (brak)]
                     [Zapisz portal]
```

Po zapisaniu:
- Portal pojawia się w dropdown
- Dropdown odświeża listę z DB
- Application Password nie jest wyświetlany w UI (••••••) — tylko podczas wpisywania

### 4. Powiązanie Generate → Inject (kluczowa zmiana)

**Wybranie portalu w kroku 1 (Generate) = automatyczny inject do tego portalu**

W `GenerateRequest`: już jest `profile_id` — zmień na `portal_id: int` (ID z DB). Backend sam wyciąga `profile_id` z portalu.

W pipeline przy inject (`_create_wp_post`):
1. Pobierz pełne dane portalu: `GET /v1/portals/{portal_id}/full` (z `wp_app_password`)
2. Załaduj profil YAML: `profiles/{profile_id}.yaml`
3. Przekaż profil dict do `inject_video(profile=profile_config)` — naprawia BUG #2
4. Użytkownik NIE musi wpisywać credentials ręcznie — są w DB

**Modal "Wyślij do portalu" po zmianach:**
- Brak pól credentials (usunięte)
- Widoczny: nazwa portalu, URL, status publikacji (Szkic/Publikuj), Format wpisu
- Przycisk "Opublikuj na portalu"

---

## Bug fixes (przy okazji — wymagane)

### BUG #1 — Graceful handling w update_rankmath_meta()

Plik: `core/injector.py` → funkcja `update_rankmath_meta()`

Fix:
```python
resp = requests.post(url, json=payload, auth=auth, timeout=20)
if not resp.text.strip():
    logger.error(
        "  RankMath FAIL WP#%s: empty response body (HTTP %s)",
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

Plik: `api/services/pipeline.py` → `_create_wp_post()`

Fix: załaduj `profiles/{profile_id}.yaml` i przekaż do `inject_video(profile=profile_config)`.  
Profil `profile_id` pochodzi teraz z portalu w DB.

### BUG #5 — json-repair

```
# requirements.txt — dodaj:
json-repair>=0.30.0
# + rebuild docker
```

---

## Test po implementacji (wykonuje właściciel produktu)

1. Otwórz dashboard VSE
2. Dropdown "Portal docelowy" → pusty (brak hardcoded)
3. Kliknij `+ Dodaj nowy portal` → dodaj **Prawy.pl** (url + user + pass + profil: prawy)
4. Kliknij `+ Dodaj nowy portal` → dodaj **Kurier365.pl** (url + user + pass + profil: kurier365)
5. Wygeneruj artykuł → wyświetlane portale: Prawy.pl, Kurier365.pl
6. Wybierz **Kurier365** → generuj → "Wyślij do portalu" (bez wpisywania credentials)
7. Sprawdź w WP admin kurier365:
   - Artykuł stworzony ✓
   - Fraza kluczowa w RankMath ustawiona ✓
   - Alt-text thumbnajla: `[keyphrase] | Kurier365` (nie "Prawy TV") ✓
   - Bloki Gutenberga renderują bez błędów ✓
8. Sprawdź RankMath score — cel: 70+

---

## Deliverable

- [ ] Migration: `ADD COLUMN profile_id` + `DELETE` starych rekordów
- [ ] API: `GET/POST /v1/portals` + `DELETE /v1/portals/{id}` + `GET /v1/portals/{id}/full`
- [ ] Frontend: dropdown z DB + modal dodawania portalu
- [ ] Frontend: usunięte hardcoded/localStorage portale
- [ ] Frontend: modal "Wyślij" bez pól credentials
- [ ] Pipeline: inject używa portalu z DB → profil YAML przekazywany
- [ ] BUG #1: graceful RankMath w `core/injector.py`
- [ ] BUG #2: profil przekazywany do `inject_video()`
- [ ] BUG #5: `json-repair` w requirements + rebuild
- [ ] Deploy na VPS + test E2E przez właściciela

**Dual-write raport:**
- `video-seo-engine/.agents/reports/YYYY-MM-DD_[callsign]_portal-management.md`
- `sonic-void/.agents/reports/inbox/YYYY-MM-DD_[callsign]_portal-management.md`

Heartbeat `status: done` po zakończeniu.

---

*[Supervisor 01 | sonic-void 29.06.2026 — v2 po decyzji właściciela produktu]*
