# ANALYSIS_api_design.md — VSE API Design Analysis

> **Autor:** `arch-api-01` | **Data:** 2026-06-16  
> **Scope:** REST conventions, versioning, response envelope, pagination, webhooks, API keys, OpenAPI, rate limiting, inter-SaaS auth
> **Kontekst biznesowy:** VSE ↔ crimson-void inter-SaaS integracja + zewnętrzni klienci API (plan starter/pro/agency)

---

## 1. REST Conventions — Naming, HTTP Methods, Status Codes

### CO
Analiza zgodności VSE API z RFC 7231 (HTTP semantics) i REST best practices.

### PO CO
Niespójne konwencje to tech debt — generują błędy przy integracji z crimson-void i powodują nieoczekiwane zachowania dla klientów API. Poprawki teraz kosztują 1h, po GA kosztują breaking change.

### Wyniki audytu

#### ✅ Co działa dobrze

| Aspekt | Ocena | Komentarz |
|--------|-------|-----------|
| Resource naming | ✅ Dobre | `/v1/users`, `/v1/admin/users/{id}` — poprawny plural |
| Prefix versioning | ✅ Dobre | `/v1/` konsekwentnie przez wszystkie endpointy |
| HTTP 201 on create | ✅ Dobre | `POST /v1/auth/register` zwraca 201 |
| HTTP 409 on conflict | ✅ Dobre | Rejestracja z istniejącym emailem → 409 Conflict |
| HTTP 403 vs 401 | ✅ Dobre | 401 = brak auth, 403 = brak uprawnień (admin) — poprawnie |
| PATCH dla partial update | ✅ Dobre | `PATCH /v1/admin/users/{id}/plan` — semantycznie poprawny |

#### ⚠️ Problemy

**P1 — Akcja w URL zamiast resource: `/v1/jobs/{id}/result`**
```
POST /v1/jobs/{id}/result   ← ❌ "result" to akcja/sub-resource, nie rzeczownik
POST /v1/jobs/{id}/transcript  ← ✅ lepiej (co jest wysyłane)
PATCH /v1/jobs/{id}  ← ✅ najczystszy REST (patch stanu joba)
```
Ryzyko: niska, bo to internal endpoint (Local Runner), ale warto ustandaryzować.

**P2 — `/v1/monitor/start` — akcja w URL**
```
POST /v1/monitor/start  ← ❌ verb w URL
POST /v1/monitor/sessions  ← ✅ bardziej RESTful
POST /v1/monitors  ← ✅ alternatywnie
```

**P3 — `/v1/sitemap` — brak wzorca CRUD**
```
POST /v1/sitemap  ← ❓ generuje i zwraca? Czy tworzy zasób?
```
Jeśli endpoint zwraca XML w response body — OK jako RPC-style action. Jeśli ma być cacheable — warto rozważyć `GET /v1/sitemap.xml`.

**P4 — Błąd 422 z plain string zamiast RFC 7807**
```python
# generate.py:
raise HTTPException(status_code=422, detail=str(exc))
# inject.py:
raise HTTPException(status_code=422, detail=str(exc))
```
Klient inter-SaaS (crimson-void) dostaje:
```json
{"detail": "Cannot fetch transcript: video unavailable"}
```
Zamiast strukturalnego:
```json
{
  "error": "transcript_unavailable",
  "message": "Cannot fetch transcript: video unavailable",
  "context": {"video_id": "abc123"}
}
```

**P5 — Brak HTTP 404 na `/v1/jobs/{id}` gdy job nie istnieje**
Nie widziałem kodu `jobs.py` — do weryfikacji. Standard: 404 gdy resource nie znaleziony.

**P6 — `POST /v1/generate` i `POST /v1/inject` nie mają auth!**
```python
# generate.py — BRAK Depends(get_current_user)!
async def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
# inject.py — BRAK Depends(get_current_user)!
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
```
> ⚠️ **KRYTYCZNE:** Endpointy core pipeline są publicznie dostępne bez uwierzytelnienia!
> To jest problem bezpieczeństwa AND problem kontraktu API — każdy może zużywać Anthropic API kosztem właściciela VSE.
> ARCHITECTURE.md §8 opisuje JWT jako wymagany, ale implementacja tego nie wymusza.

---

## 2. Versioning Strategy — jak ewoluować v1?

### CO
Analiza strategii wersjonowania pod kątem long-term API stability.

### PO CO
crimson-void będzie konsumentem VSE API. Każdy breaking change w v1 = praca po stronie crimson-void. Dobra strategia wersjonowania chroni kontrakt.

### Aktualna sytuacja

- **Strategia:** URL path versioning (`/v1/`) — ✅ dobry wybór, widoczny i łatwy do routowania
- **Wersja aplikacji:** `2.0.0` (w `/health`), ale prefix URL = `v1` — brak korelacji
- **Brak changelog:** Nie ma formalnego rekordu co zmieniło się w v1

### Rekomendacje

**R1 — Zasada Semantic Break:**
```
v1 → v2  gdy:
  - zmiana struktury response_body (pole usunięte, zmiana typu)
  - zmiana wymaganego parametru wejścia (dodanie required field)
  - zmiana semantyki endpointu

v1 może zmienić się bez bumpa:
  - dodanie nowego opcjonalnego pola w response (backwards compatible)
  - dodanie nowego endpointu
  - zmiana błędu z 500 na 422 (poprawka semantyki)
```

**R2 — API Changelog (rekomendowany format):**
```
# docs/CHANGELOG_api.md
## v1 — 2026-06-15
- POST /v1/generate — initial
- POST /v1/inject — initial (wp_post_id nullable = create mode)
- POST /v1/auth/google/token-exchange — added 2026-06-16
```

**R3 — Deprecation header strategy (przyszłość):**
```http
Deprecation: Sat, 01 Jan 2027 00:00:00 GMT
Sunset: Mon, 01 Jul 2027 00:00:00 GMT
Link: <https://vse.impresjapr.pl/docs/migration/v1-v2>; rel="deprecation"
```

**R4 — Nie używaj Header versioning:**
```
# ❌ Nie: Accept: application/vnd.vse.v2+json
# ✅ Tak: /v2/generate
```
URL versioning jest lepszy dla naszego use-case (proxy nginx, CDN caching, human-readable).

---

## 3. API Response Envelope — Spójność Formatu

### CO
Analiza spójności struktury odpowiedzi API.

### PO CO
Klient inter-SaaS (crimson-void) musi parsować odpowiedzi programatycznie. Niespójny format = dodatkowa warstwa adapter code po stronie klienta.

### Aktualna analiza

**Endpoint → response shape:**

| Endpoint | Envelope | Uwagi |
|----------|----------|-------|
| `POST /v1/generate` | `{status, video_id, processing_time_s, schema_data, error}` | Własna struktura |
| `POST /v1/inject` | `{status, wp_post_id, video_id, rankmath_ok, ...}` | Własna struktura |
| `POST /v1/auth/login` | `{access_token, refresh_token, token_type, user_id}` | TokenResponse |
| `POST /v1/auth/register` | `{message, user_id}` | Nieformalny dict |
| `GET /v1/users/me` | `{id, email, ..., plan, usage}` | UserProfile |
| `GET /v1/admin/users` | `{users: [...], total: int}` | UserListResponse |
| `GET /health` | `{status, version, llm_default}` | HealthResponse |
| Błędy (FastAPI default) | `{detail: "..."}` | FastAPI default |

**Problem:** Brak wspólnego envelope.

```
❌ generate → {status: "ok", data: {...}}
❌ register → {message: "...", user_id: "..."}
❌ users → {users: [...], total: 5}
❌ błędy → {detail: "..."}
```

**Rekomendowany standard dla VSE v1.1:**

```json
// Sukces:
{
  "ok": true,
  "data": { ... },   
  "meta": { "processing_time_s": 47.3 }  // opcjonalne
}

// Błąd:
{
  "ok": false,
  "error": {
    "code": "transcript_unavailable",     // machine-readable
    "message": "Cannot fetch transcript",  // human-readable
    "context": {"video_id": "abc123"}      // opcjonalne
  }
}
```

**Ocena ryzyka:** Zmiana envelope = breaking change v2. Na potrzeby inter-SaaS z crimson-void warto **udokumentować obecny kontrakt** i napisać adapter po stronie crimson-void. Zmiana formatu → v2.

---

## 4. Pagination — GET /v1/admin/users

### CO
Analiza implementacji paginacji w endpointach listowania.

### PO CO
Bez pagination endpoint z 10,000 userów zwróci 10MB response i zawiesi bazę. To bloker dla skalowalności.

### Aktualna implementacja

```python
# admin.py:
@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,  # ← domyślnie 100
    ...
):
    result = await db.execute(
        select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    return UserListResponse(users=user_views, total=total)
```

**Response:**
```json
{"users": [...], "total": 1234}
```

**Ocena:** ✅ Podstawowa paginacja działa (`skip`/`limit` + `total`). Ale:

| Problem | Poziom | Opis |
|---------|--------|------|
| Brak `page` param | ⚠️ Kosmetyczny | Klientom łatwiej `?page=2&per_page=20` niż `?skip=20&limit=20` |
| Brak `next_page` w response | ⚠️ Minor | Klient musi liczyć sam |
| Limit bez górnej granicy | 🔴 Risk | `?limit=99999` może zatopić bazę |
| N+1 query per user | 🔴 Risk | `_count_usage_this_month()` per user = N queries |

**Rekomendowany response (minimal fix):**
```json
{
  "users": [...],
  "total": 1234,
  "page": 1,
  "per_page": 50,
  "pages": 25
}
```

**Fix limit guard:**
```python
limit: int = Query(default=50, ge=1, le=200)  # max 200 per page
```

**Fix N+1 (batch count):**
```python
# Zamiast N queries: jeden GROUP BY
result = await db.execute(
    select(UsageLog.user_id, func.count())
    .where(UsageLog.created_at >= month_start)
    .group_by(UsageLog.user_id)
)
usage_map = {row[0]: row[1] for row in result}
```

---

## 5. Webhook Architecture — VSE → crimson-void notifications

### CO
Ocena możliwości i blueprint architektury webhookowej dla VSE.

### PO CO
crimson-void chce wiedzieć kiedy generacja SEO jest gotowa (aby automatycznie pobrać wyniki lub wyzwolić kolejny krok workflow). Bez webhooków crimson-void musi pollować — co jest nieefektywne i nie skaluje.

### Aktualna sytuacja

**Webhooks: NIE ISTNIEJĄ.** VSE nie ma żadnej infrastruktury notyfikacyjnej.

### Blueprint — Webhook Architecture v1

**Model:** Outbound webhooks (VSE push → crimson-void endpoint)

**Zdarzenia kandydujące:**

| Event | Kiedy | Payload |
|-------|-------|---------|
| `generate.completed` | Po udanym `/v1/generate` | `{video_id, schema_data, user_id, timestamp}` |
| `generate.failed` | Po błędzie generacji | `{video_id, error_code, user_id, timestamp}` |
| `inject.completed` | Po udanym `/v1/inject` | `{wp_post_id, post_url, video_id, user_id, timestamp}` |
| `quota.exceeded` | Przekroczenie limitu | `{user_id, plan_id, used, quota, timestamp}` |
| `monitor.found` | Nowy film na kanale | `{channel_id, video_id, video_url, timestamp}` |

**Tabela DB (do dodania):**
```sql
CREATE TABLE webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    url TEXT NOT NULL,
    events TEXT[] NOT NULL,          -- ["generate.completed", "inject.completed"]
    secret TEXT NOT NULL,            -- HMAC-SHA256 signing key
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Delivery model:**
```python
# Po każdym generate.completed:
await dispatch_webhook(
    user_id=user.id,
    event="generate.completed",
    payload={"video_id": ..., "schema_data": ...}
)

# dispatch_webhook:
async def dispatch_webhook(user_id, event, payload):
    subs = await get_active_subscriptions(user_id, event)
    for sub in subs:
        body = json.dumps({"event": event, "data": payload, "timestamp": now()})
        signature = hmac.new(sub.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers = {
            "X-VSE-Signature": f"sha256={signature}",
            "X-VSE-Event": event,
            "Content-Type": "application/json"
        }
        # fire-and-forget (background task)
        asyncio.create_task(httpx.post(sub.url, content=body, headers=headers))
```

**Inter-SaaS (crimson-void specifics):**
```
crimson-void rejestruje webhook:
POST /v1/webhooks
{ "url": "https://api.crimson.impresjapr.pl/hooks/vse",
  "events": ["generate.completed"],
  "secret": "shared_secret_from_crimson" }

VSE (każde generate.completed) → POST crimson webhook → crimson przetwarza
```

**Priorytet implementacji:** Faza 2 — po wdrożeniu API key auth.

---

## 6. API Keys — Tabela `api_keys` i Model SaaS

### CO
Analiza tabeli `api_keys` i brakującej infrastruktury do obsługi klientów SaaS przez API key.

### PO CO
Plan `starter`, `pro`, `agency` mają `api_access=True`. Klienci SaaS chcą wywoływać VSE przez API key (curl, Postman, integracje), nie przez JWT z przeglądarki. Bez tego funkcjonalność jest blokowana.

### Aktualna sytuacja

**Tabela `api_keys` EXISTS** (w `api/models/user.py`):
```python
class ApiKey(Base):
    id: UUID
    user_id: UUID FK
    key_hash: str  # bcrypt
    name: str
    is_active: bool
    last_used_at: datetime
    created_at: datetime
```

**Problem: ŻADNE endpointy nie obsługują API keys!**

| Co brakuje | Opis |
|-----------|------|
| `POST /v1/api-keys` | Tworzenie nowego API key |
| `GET /v1/api-keys` | Lista kluczy usera |
| `DELETE /v1/api-keys/{id}` | Revoke klucza |
| Auth dependency | `get_current_user_or_apikey` — sprawdza Bearer JWT OR `X-API-Key` header |
| Key generation | Bezpieczny format `vse_live_xxxxx` (prefix + 32 hex) |

**Rekomendowany format klucza:**
```
vse_live_a1b2c3d4e5f6...  (prefix + 32 random hex)
```
Prefix `vse_live_` pozwala:
- automatycznie wykryć że to VSE key (np. GitHub secret scanning)
- odróżnić środowisko (live vs test)

**Auth dependency do implementacji:**
```python
async def get_current_user_or_apikey(
    credentials = Depends(bearer_scheme),
    x_api_key: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    if x_api_key:
        # Hash x_api_key, szukaj w api_keys, sprawdź plan.api_access
        ...
    elif credentials:
        return await get_current_user(credentials, db)
    else:
        raise HTTPException(401, ...)
```

**Plan enforcement:**
```python
# Przed API key auth — sprawdź uprawnienie:
if not user.plan.api_access:
    raise HTTPException(403, detail="API access requires starter plan or higher")
```

---

## 7. OpenAPI Spec — Swagger /docs Kompletność

### CO
Ocena jakości i kompletności automatycznie generowanej specyfikacji OpenAPI (Swagger).

### PO CO
Klient inter-SaaS (crimson-void) lub zewnętrzny developer może generować SDK z OpenAPI spec. Braki w spec = SDK z dziurami lub konieczność ręcznej dokumentacji.

### Aktualna sytuacja

```python
# main.py:
app = FastAPI(
    title="VSE API",
    description="PressAI Video SEO Engine — multi-tenant FastAPI service",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

**Pozytywne:** `docs_url` i `redoc_url` są publiczne — dostępne bez auth na `/docs`.

**Problemy w spec:**

| Problem | Wpływ |
|---------|-------|
| Brak `SecurityScheme` (HTTPBearer) zadeklarowanego globalnie | ⚠️ Swagger UI nie pokazuje kłódki i nie pozwala wkleić tokenu |
| Brak `tags` descriptions | Minor — tags są, ale brak opisów |
| Brak `examples` w Pydantic schematach | Minor — brak example values w Swagger |
| Brak `summary` na kilku endpointach | Minor |
| Brak `contact` i `license` w FastAPI() | Minor dla public API |

**Fix SecurityScheme:**
```python
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer

# Dodaj globalnie do app:
app = FastAPI(
    ...,
    openapi_tags=[
        {"name": "auth", "description": "Registration, login, token refresh, Google OAuth"},
        {"name": "generate", "description": "YouTube → SEO schema generation"},
        {"name": "inject", "description": "Push schema to WordPress"},
        {"name": "admin", "description": "User and plan management (admin only)"},
        {"name": "system", "description": "Health check"},
    ]
)

# Security scheme jest automatycznie wykrywany przez FastAPI gdy
# Depends(get_current_user) używa HTTPBearer — sprawdzić czy Swagger
# pokazuje lock icon przy chronionych endpointach.
```

---

## 8. Rate Limiting Per API Key

### CO
Analiza obecnej implementacji rate limiting i egzekucji limitów planów.

### PO CO
Bez rate limiting użytkownik `free` (limit 5/miesiąc) może callować API w nieskończoność dopóki ktoś ręcznie nie sprawdzi `usage_logs`. Plan enforcement nie działa bez middleware.

### Aktualna sytuacja

```python
# quota.py — referenced in ARCHITECTURE.md but not imported in generate.py!
# generate.py nie wywołuje quota.check()!
async def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    result = await run_generate(...)  # bez quota check!
```

**Dwie warstwy rate limiting (brakujące obie):**

#### Warstwa 1 — Monthly quota enforcement (business logic)
```python
# Powinno być w generate.py przed run_generate():
async def check_and_record_quota(user: User, endpoint: str, db: AsyncSession):
    if user.plan.monthly_quota == -1:
        return  # unlimited
    
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    count_result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == user.id)
        .where(UsageLog.success == True)
        .where(UsageLog.created_at >= month_start)
    )
    used = count_result.scalar_one()
    
    if used >= user.plan.monthly_quota:
        raise HTTPException(429, detail={
            "error": "quota_exceeded",
            "used": used,
            "quota": user.plan.monthly_quota,
            "reset_at": (month_start + timedelta(days=32)).replace(day=1).isoformat()
        })
```

#### Warstwa 2 — Request rate limiting (infrastruktura)
```
Opcja A: nginx rate limit (najprostsza dla MVP):
limit_req_zone $http_x_api_key zone=api_keys:10m rate=10r/m;
limit_req zone=api_keys burst=5 nodelay;

Opcja B: slowapi (Redis-based, per API key):
from slowapi import Limiter
limiter = Limiter(key_func=get_api_key)
@app.get("/v1/generate")
@limiter.limit("10/minute")
async def generate_endpoint(...):

Opcja C: Cloudflare Rate Limiting Rules (bez zmian w kodzie)
```

**Rekomendacja dla Fazy 1.5:** Opcja A (nginx) + quota enforcement w generate.py. Minimalny koszt, maksymalny efekt.

---

## 9. Inter-SaaS Auth — Bearer JWT vs API Key

### CO
Analiza strategii autentykacji machine-to-machine między VSE ↔ crimson-void.

### PO CO
M2M auth różni się od user auth — tokeny nie wygasają po 15min, nie ma refresh flow przez przeglądarkę, potrzeba trwałych credentials. Błędny model = problemy z integracją na produkcji.

### Rekomendacja: API Key dla M2M

```
❌ Bearer JWT (user token) dla M2M — DLA
   - Token wygasa co 15 min
   - Refresh wymaga store'owania refresh_token
   - JWT jest user-bound (konkretny user)
   - Nie nadaje się dla service-to-service

✅ API Key dla M2M — DLACZEGO
   - Stały, nie wygasa (tylko manual revoke)
   - Łatwy do rotowania (delete + create new)
   - Audytowalny (last_used_at w tabeli)
   - Bezpieczny z HTTPS
   - Standard dla SaaS M2M (Stripe, Twilio, OpenAI)
```

### Model integracji VSE ↔ crimson-void

```
Szema integracji:

crimson-void (instancja Supervisor/Worker):
  1. Posiada API key VSE: X-API-Key: vse_live_xxxx
     (plan: agency — unlimited quota, api_access=True)
  2. POST https://vse.impresjapr.pl/api/v1/generate
     X-API-Key: vse_live_xxxx
     Body: {video_url: ..., llm_provider: "claude", lang: "pl"}
  3. Otrzymuje schema_data
  4. Opcjonalnie: POST /v1/inject (jeśli auto-publish)

VSE (przyszłość — konsumuje crimson-void API):
  → crimson-void dostarcza API key dla VSE
  → VSE woła np. crimson-void /v1/articles/publish
```

### Shared API Key management

```
Konfiguracja (obie strony):

crimson-void env:
  VSE_API_KEY=vse_live_xxxxxxxxxxxxxxxxxx
  VSE_BASE_URL=https://vse.impresjapr.pl/api

VSE env (przyszłość, gdy konsumuje crimson-void):
  CRIMSON_API_KEY=cv_live_xxxxxxxxxxxxxxxxxx  
  CRIMSON_BASE_URL=https://api.crimson.impresjapr.pl
```

### Rotacja kluczy (SLA)

```
Procedura rotacji:
1. crimson-void: POST /v1/api-keys {name: "crimson-void-prod-2026-07"}
2. crimson-void: zaktualizuj env VSE_API_KEY na nowy
3. Deploy crimson-void z nowym kluczem
4. crimson-void: DELETE /v1/api-keys/{old_id}
Downtime: 0 (rolling update)
```

---

## 10. Podsumowanie — Priority Matrix

### 🔴 KRYTYCZNE (blokuje produkcję / bezpieczeństwo)

| # | Problem | Ryzyko | Fix |
|---|---------|--------|-----|
| K1 | `POST /v1/generate` bez auth | Darmowe API kosztem właściciela | Dodaj `Depends(get_current_user)` |
| K2 | `POST /v1/inject` bez auth | j.w. + zapisuje do WP dowolna osoba | j.w. |
| K3 | Quota enforcement brak | free user = unlimited | Implementuj `check_and_record_quota()` |

### 🟡 WYSOKI (blokuje inter-SaaS integrację)

| # | Problem | Wpływ | Fix |
|---|---------|-------|-----|
| W1 | Brak API key endpointów | crimson-void nie może się auth jako M2M | Zaimplementuj CRUD /v1/api-keys |
| W2 | Brak `X-API-Key` auth support | M2M zawsze przez user JWT | Rozszerz `get_current_user` dependency |
| W3 | Niespójny error format | Parsing po stronie crimson-void | Ustandaryzuj na `{ok, error: {code, message}}` |
| W4 | N+1 query w admin/users | Powolna lista przy 100+ userach | Batch usage count query |

### 🟢 NISKI (tech debt, nie blokuje)

| # | Problem | Fix |
|---|---------|-----|
| L1 | Akcje w URL (/monitor/start, /jobs/{id}/result) | Rename przy v2 |
| L2 | Brak API Changelog | Stwórz docs/CHANGELOG_api.md |
| L3 | Brak webhook infrastructure | Faza 2 dispatch |
| L4 | OpenAPI brak SecurityScheme display | Fix w FastAPI app init |
| L5 | Pagination brak `pages`/`per_page` | Minor UX improvement |
| L6 | Limit bez max guard w pagination | `Query(le=200)` |

---

## 11. Rekomendowany Plan Działania

### Sprint 1 (Tydzień 1) — Security & Auth
```
1. generate.py + inject.py → dodaj Depends(get_current_user)
2. quota.py → zaimplementuj check + record w generate.py
3. api/routers/api_keys.py → CRUD dla kluczy API
4. api/auth.py → rozszerz o X-API-Key header support
```

### Sprint 2 (Tydzień 2) — Inter-SaaS
```
1. Ustandaryzuj error response format
2. Stwórz VSE API key dla crimson-void (plan: agency)
3. Testuj integrację: crimson-void → POST /v1/generate z X-API-Key
4. Dokumentuj kontrakt w docs/INTEGRATION_crimson-void.md
```

### Sprint 3 (Tydzień 3-4) — Webhooks
```
1. Tabela webhook_subscriptions w DB
2. POST/GET/DELETE /v1/webhooks endpointy
3. Webhook dispatch (HMAC-signed, async)
4. crimson-void webhook receiver endpoint
```

---

## 12. Inter-SaaS Integration Contract (Draft)

```yaml
# docs/INTEGRATION_crimson-void.yaml
name: VSE → crimson-void integration
version: draft-2026-06-16

auth:
  type: api-key
  header: X-API-Key
  format: "vse_live_*"
  plan_required: agency

endpoints_used_by_crimson:
  - POST /v1/generate
  - POST /v1/inject  # opcjonalnie, Plan B

events_pushed_by_vse:
  - generate.completed  # webhook (Faza 2)
  - generate.failed     # webhook (Faza 2)

rate_limits:
  agency_plan: 9999/month
  per_minute: TBD (po implementacji)

sla:
  generate_latency_p95: ~60s (LLM dependent)
  generate_latency_p50: ~45s
  availability: best-effort (single VPS)

base_url: https://vse.impresjapr.pl/api
```

---

*arch-api-01 | video-seo-engine | 2026-06-16 — v1.0*
