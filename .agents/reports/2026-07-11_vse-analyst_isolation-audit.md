# Isolation Audit — VSE Account Isolation
**Agent:** vse-analyst-isolation | **Data:** 2026-07-11 | **Status:** raport kompletny

---

## Podsumowanie wykonawcze

Audit obejmuje **9 plików routerów** (`youtube.py`, `inject.py`, `jobs.py`, `portals.py`, `generate.py`, `profiles.py`, `auth.py`, `process.py`, `sitemap.py`) oraz **3 live SSH queries** do bazy produkcyjnej.

**Krytyczne znaleziska:** 4 problemy, w tym 2 KRYTYCZNE wymagające naprawy PRZED wdrożeniem YT Publishing.

---

## Krok 1: Analiza routerów

### youtube.py — `GET /v1/youtube/channels` ✅ OK

```python
# Linia ~95 (list_user_channels)
result = await db.execute(
    select(YouTubeChannel)
    .where(YouTubeChannel.user_id == current_user.id)  # ✅ filtr user_id
    .where(YouTubeChannel.is_active == True)
    .order_by(YouTubeChannel.created_at)
)
```
- `GET /v1/youtube/channels` — **POPRAWNE** — filtruje po `user_id == current_user.id`
- `DELETE /v1/youtube/channels/{id}` — **POPRAWNE** — filtruje po `id AND user_id`
- OAuth callback — **POPRAWNE** — `user_id` pobierany z `OAuthState` (nie z requestu)

### inject.py — `POST /v1/inject` ⚠️ KRYTYCZNE

```python
# Linia ~28
@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
    # ❌ BRAK: current_user: User = Depends(get_current_user)
    # ❌ BRAK: weryfikacji że portal_id należy do zalogowanego usera
```

**Problem 1 — Brak autoryzacji na `/v1/inject`:**
- Endpoint nie przyjmuje `current_user` — każdy anonimowy request jest przyjmowany
- `portal_id` jest pobierany z request body, bez weryfikacji ownership
- Atak: User B podaje `portal_id` należący do Usera A → pipeline pobiera WP credentials Usera A
- Atak 2: Dowolny request (bez JWT!) może wywołać publish na cudzym portalu

**Problem 2 — `portal_id` bez auth check:**
```python
elif req.portal_id:
    async with AsyncSessionLocal() as db:
        uid = uuid.UUID(req.portal_id)
        portal = await db.get(WpPortal, uid)  # ❌ bez .where(user_id == current_user.id)
        if portal:
            site_config_dict = {
                "wp_base_url": portal.url,
                "wp_user": portal.wp_username,
                "wp_app_password": portal.wp_app_password  # ← hasło WP
            }
```

### portals.py — CRUD `/v1/portals` ✅ OK

- `GET /v1/portals` — filtruje `.where(WpPortal.user_id == current_user.id)` ✅
- `POST /v1/portals` — ustawia `user_id=current_user.id` ✅
- `GET /v1/portals/{id}/full` — filtruje `.where(WpPortal.id == uid).where(WpPortal.user_id == current_user.id)` ✅
- `PATCH /v1/portals/{id}` — filtruje `.where(WpPortal.user_id == current_user.id)` ✅
- `DELETE /v1/portals/{id}` — filtruje `.where(WpPortal.user_id == current_user.id)` ✅

### jobs.py — `/v1/jobs` ⚠️ ŚREDNIE (1 problem)

**`GET /v1/jobs/history`** ✅ OK (filtruje per user, admin widzi wszystko):
```python
query = select(TranscriptJob)
if not current_user.is_admin:
    query = query.where(TranscriptJob.user_id == current_user.id)  # ✅
```

**`POST /v1/jobs/` (create)** ✅ OK — przypisuje `user_id=current_user.id`

**`GET /v1/jobs/{job_id}` (get single job)** ✅ OK — sprawdza `job.user_id == current_user.id`

**`GET /v1/jobs/{job_id}/vtt`** ✅ OK — sprawdza `job.user_id == current_user.id`

**`GET /v1/jobs/pending`** — chroniony przez `LOCAL_RUNNER_TOKEN` (nie JWT) ✅ prawidłowe

**⚠️ Problem 3 — NULL user_id w transcript_jobs:**
W bazie produkcyjnej istnieją joby bez `user_id` (NULL):
```
 a55efddd | NULL | fetched | 2026-07-11 16:37  ← brak owner!
 e8aab67f | NULL | failed  | 2026-07-11 16:04
 409f5fb8 | NULL | fetched | 2026-07-10 16:05
 6d85cb39 | NULL | failed  | 2026-07-10 15:56
```
Kod w `jobs.py GET /{job_id}`: jeśli `job.user_id is None` → dostęp tylko dla admina (403 dla zwykłego usera). To jest poprawne zachowanie w kodzie. **Ale** `get_job` akceptuje dostęp jeśli `job.user_id == current_user.id` OR admin — NULL joby są zablokowane dla zwykłych userów.

Natomiast `generate.py._save_schema_to_job()` może przypisać `user_id` do istniejącego job po wygenerowaniu:
```python
if user_id and job.user_id is None:
    job.user_id = user_id  # ← propagacja user_id
```

### generate.py — `POST /v1/generate` ✅ OK

```python
@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(req: GenerateRequest, current_user: User = Depends(get_current_user)):
```
- Wymaga JWT ✅
- Zapisuje `user_id=current_user.id` do job ✅

### profiles.py — `GET/POST /v1/profiles` ⚠️ NISKIE

**`GET /v1/profiles`** — **brak auth!** Zwraca listę YAML profili serwera. Nie zawiera credentials (hasła są jako `${ENV_VAR}`) ale ujawnia:
- Nazwy portali, URL, brand, typy publikacji
- Dostępne endpointy dla wszystkich bez JWT

**Problem 4 — `POST /v1/profiles` — brak auth:**
```python
@router.post("/profiles", response_model=ProfileInfo, status_code=201)
async def create_profile(req: CreateProfileRequest) -> ProfileInfo:
    # ❌ BRAK: current_user: User = Depends(get_current_user)
```
Każdy bez JWT może tworzyć pliki YAML na serwerze (path traversal ryzko przez `portal_id` jest ograniczone przez regex walidację — tylko `[a-z0-9_-]{3-50}`, bez `/`). Ryzyko niskie ale nienormalne.

---

## Krok 2: Live SSH — wyniki z bazy produkcyjnej

### youtube_channels

```
                  id                  |               user_id                |    youtube_channel_id    |       title
--------------------------------------+--------------------------------------+--------------------------+-------------------
 9ec1c7b8-... | 4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | UCIBzmtDQ1SrE0r7jtWbiTNw | Tomasz Brzozowski
 1d1f5783-... | ee7a677b-7e11-4c65-b67e-3d8f85fcbb85 | UCJGgMtUhG1ILuyOKcL6JA_g | VeriNarrMundo
```

**Obserwacje:**
- Tabela zawiera `user_id` (kolumna istnieje) ✅
- 2 różnych userów z różnymi kanałami — dane są fizycznie izolowane w DB ✅
- Kolumna `refresh_token_encrypted` (bytea) — tokeny szyfrowane ✅
- `GET /channels` filtruje po `user_id` — izolacja działa na poziomie kodu ✅

### wp_portals

```
                  id                  |               user_id                |     name     |         url
--------------------------------------+--------------------------------------+--------------+----------------------
 d99854d6-... | 4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | prawy.pl     | https://prawy.pl
 b99f7106-... | 4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | Kurier365.pl | https://kurier365.pl
```

**Obserwacje:**
- Tylko 1 user ma portale w DB (testy) ✅
- Portale izolowane per `user_id` w DB ✅
- `portals.py` — filtruje poprawnie ✅
- **Problem:** `inject.py POST /v1/inject` może pobrać credentials dowolnego portalu bez auth!

### transcript_jobs

```
 id         | user_id                              | status  | created_at
-----------+--------------------------------------+---------+------------------------------
 fdba0cbe  | 4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | done    | 2026-07-11 16:38:44
 a55efddd  | NULL                                 | fetched | 2026-07-11 16:37:14  ← NULL!
 7002eb47  | 4b97ab0c-98ee-46c6-9be8-d86adc4cb38a | done    | 2026-07-11 16:05:39
 e8aab67f  | NULL                                 | failed  | 2026-07-11 16:04:57  ← NULL!
```

**Obserwacje:**
- Joby z NULL user_id istnieją — są to joby stworzone przez Local Runner lub przed implementacją auth
- Kod w `jobs.py` blokuje dostęp do NULL jobów dla zwykłych userów (403) ✅
- Historia (`/v1/jobs/history`) filtruje po `user_id` — NULL joby nie pojawiają się w historii ✅

---

## Krok 3: Tabela ryzyka

| Endpoint / Query | Filtr user_id? | Ryzyko | Priorytet Fix |
|---|---|---|---|
| `GET /v1/youtube/channels` | ✅ TAK | Niskie | Brak |
| `DELETE /v1/youtube/channels/{id}` | ✅ TAK | Niskie | Brak |
| `GET /v1/portals` | ✅ TAK | Niskie | Brak |
| `POST /v1/portals` | ✅ TAK (user_id z JWT) | Niskie | Brak |
| `GET /v1/portals/{id}/full` | ✅ TAK | Niskie | Brak |
| `PATCH /v1/portals/{id}` | ✅ TAK | Niskie | Brak |
| `DELETE /v1/portals/{id}` | ✅ TAK | Niskie | Brak |
| **`POST /v1/inject`** | **❌ NIE** | **🔴 KRYTYCZNE** | **BLOKUJE YT Publishing** |
| **`portal_id` lookup w inject.py** | **❌ NIE** | **🔴 KRYTYCZNE** | **BLOKUJE YT Publishing** |
| `POST /v1/jobs/` | ✅ TAK | Niskie | Brak |
| `GET /v1/jobs/history` | ✅ TAK | Niskie | Brak |
| `GET /v1/jobs/{id}` | ✅ TAK | Niskie | Brak |
| `GET /v1/jobs/{id}/vtt` | ✅ TAK | Niskie | Brak |
| `POST /v1/generate` | ✅ TAK | Niskie | Brak |
| `GET /v1/profiles` | ❌ NIE (publiczny) | 🟡 Niskie | Opcjonalne |
| `POST /v1/profiles` | ❌ NIE (brak auth) | 🟡 Niskie | Po YT Publishing |
| `NULL user_id` w transcript_jobs | N/A | 🟡 Informacyjne | Cleanup opcjonalny |

---

## Krok 4: Proponowane fixy

### FIX 1 (KRYTYCZNE) — inject.py: Dodaj auth + ownership check

**Plik:** `api/routers/inject.py`

```python
# PRZED:
from fastapi import APIRouter, HTTPException

@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
```

```python
# PO:
from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from api.models.user import User

@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(
    req: InjectRequest,
    current_user: User = Depends(get_current_user),  # ← DODAJ
) -> InjectResponse:
```

**Dodatkowo** — ownership check dla `portal_id`:

```python
# W bloku elif req.portal_id: zamień:
# PRZED:
portal = await db.get(WpPortal, uid)
if portal:
    ...

# PO:
result = await db.execute(
    select(WpPortal).where(
        WpPortal.id == uid,
        WpPortal.user_id == current_user.id  # ← DODAJ
    )
)
portal = result.scalar_one_or_none()
if not portal:
    raise ValueError(f"Portal not found or access denied: {req.portal_id}")
```

**Import do dodania na początku pliku:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.db import get_db
```

### FIX 2 (NISKIE) — profiles.py: Dodaj auth na POST /v1/profiles

**Plik:** `api/routers/profiles.py`

```python
# PRZED:
@router.post("/profiles", response_model=ProfileInfo, status_code=201)
async def create_profile(req: CreateProfileRequest) -> ProfileInfo:

# PO:
from fastapi import Depends
from api.auth import get_current_user
from api.models.user import User

@router.post("/profiles", response_model=ProfileInfo, status_code=201)
async def create_profile(
    req: CreateProfileRequest,
    current_user: User = Depends(get_current_user),  # ← DODAJ
) -> ProfileInfo:
```

Dodatkowo warto ograniczyć `GET /v1/profiles` do zalogowanych userów (opcjonalne — bez credentials nie jest wrażliwe).

---

## Analiza architektury auth

`api/auth.py` — `get_current_user`:
- JWT w Bearer header → decode → `user_id = payload.get("sub")` → SELECT User WHERE id
- Poprawna implementacja JWT ✅
- `current_user.id` to UUID — bezpieczne dla filtrowania SQL ✅
- `is_admin` flag kontroluje dostęp do admin-only zasobów ✅

**Słaby punkt:** Endpointy które NIE używają `Depends(get_current_user)` są de facto publiczne. Inject i profiles/POST to jedyne znalezione przypadki.

---

## Priorytet działań

| # | Action | Pilność | Blokuje |
|---|---|---|---|
| 1 | Fix inject.py — dodaj `Depends(get_current_user)` | 🔴 Przed YT Publishing | YT token publish |
| 2 | Fix inject.py — dodaj `user_id` do portal_id lookup | 🔴 Przed YT Publishing | Credentials leak |
| 3 | Fix profiles.py — auth na POST /v1/profiles | 🟡 Po YT Publishing | Arbitrary file create |
| 4 | Opcjonalnie: auth na GET /v1/profiles | 🟢 Kiedyś | Info leak |
| 5 | Opcjonalnie: cleanup NULL user_id jobs | 🟢 Kiedyś | Brak ryzyka w kodzie |

---

*[vse-analyst-isolation | video-seo-engine 2026-07-11 20:10] raport kompletny*
