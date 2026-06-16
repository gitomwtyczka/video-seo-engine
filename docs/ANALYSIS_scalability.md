# ANALYSIS: Skalowalność VSE — Video SEO Engine

> **Autor:** `arch-scale-01` | **Data:** 2026-06-16  
> **Scope:** Analiza systemu pod kątem 1000 concurrent users  
> **Źródła:** `api/db.py`, `api/models/job.py`, `api/services/pipeline.py`, `requirements.txt`, `Dockerfile.api`, `docker-compose.vse.yml`, `ARCHITECTURE.md`

---

## TL;DR — Krytyczne bottlenecki (TOP 3)

| # | Problem | Severity | Gdzie eksploduje? |
|---|---------|----------|-------------------|
| 🔴 1 | **LLM call synchroniczny w wątku** — 50s blokuje connection | CRITICAL | ~20 concurrent `/v1/generate` |
| 🔴 2 | **Local Runner = single point of failure** — 1 Windows PC | CRITICAL | ≥2 parallel transcript jobs |
| 🔴 3 | **Brak rate limitingu** — niechroniony endpoint LLM | HIGH | DDoS → rachunek $$ Anthropic |

---

## 1. DB Connection Pooling

**CO:** SQLAlchemy async engine z asyncpg.

**Obecny stan:**
```python
# api/db.py
engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
```
- `pool_size=10` — stałe połączenia w puli
- `max_overflow=20` — dodatkowe połączenia przy szczycie
- **Łącznie max: 30 połączeń** do PostgreSQL
- Brak `pool_timeout` (domyślnie 30s) — możliwy hang przy wyczerpaniu puli
- Brak `pool_recycle` — długo żyjące połączenia mogą stać się stale

**Limit:**  
PostgreSQL domyślnie: `max_connections=100`.  
Przy 2 workerach Uvicorn (patrz Dockerfile.api) każdy worker ma własną pulę.  
Efektywnie: **2 workers × 30 connections = 60 połączeń** — bezpiecznie poniżej limitu 100.

Ale przy 1000 concurrent users i krótkich requestach (GET /health, GET /users/me),  
30 połączeń per worker jest **za mało**. Szybkie zapytania czekają w kolejce.

**Rekomendacja:**
```python
# Krótkookresowo — zwiększ pool:
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_timeout=10,         # fail-fast zamiast 30s hang
    pool_recycle=3600,       # recycle co godzinę
    pool_pre_ping=True,      # sprawdź żywotność połączeń
)
```

```bash
# Zwiększ PostgreSQL max_connections (docker-compose.vse.yml):
environment:
  - POSTGRES_EXTRA_OPTS=-c max_connections=200
```

**Długookresowo:** PgBouncer jako connection pooler przed PostgreSQL.  
PgBouncer transaction mode = setki klientów przez ~20 realnych połączeń PG.

**Effort:** 🟢 Niski (zmiana 3 linii w db.py) → 🟡 Średni (PgBouncer = nowy kontener)

---

## 2. Sync vs Async — Blocking Calls

**CO:** FastAPI działa async, ale wiele wywołań core/ jest synchronicznych.

**Obecny stan — DOBRA wiadomość:**  
`pipeline.py` używa `asyncio.to_thread()` dla wszystkich sync wywołań:
```python
# pipeline.py — poprawny pattern
meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)
seo = await asyncio.to_thread(generate_schema, ...)
result = await asyncio.to_thread(inject_video, ...)
```

**ZIDENTYFIKOWANE problemy:**

### 2A. `requests` w `_create_wp_post()` — synchroniczny HTTP
```python
# pipeline.py, _create_wp_post()
resp = requests.post(create_url, json=create_payload, auth=auth, timeout=20)
```
`requests` jest synchroniczna biblioteka. Wywołana przez `asyncio.to_thread()` — OK,  
ale jeśli ktoś kiedykolwiek wywoła ją bezpośrednio w async context → event loop blokada.

### 2B. `quota.py` — brak indeksowania (patrz sekcja 9)
```python
# quota.py — COUNT na UsageLog bez composite indexu
result = await db.execute(
    select(func.count(UsageLog.id))
    .where(UsageLog.user_id == current_user.id)
    .where(UsageLog.success == True)
    .where(UsageLog.created_at >= month_start)
)
```
Przy 1000 userów × 300 requestów/miesiąc = 300 000 wierszy w `usage_logs`.  
Bez composite indexu `(user_id, success, created_at)` → seq scan → blokada DB.

### 2C. Polling `_wait_for_transcript()` — trzyma wątek/worker przez 120s
```python
# pipeline.py — async polling OK, ale goroutine żyje 120s
async def _wait_for_transcript(job_id: str) -> str:
    deadline = time.time() + LOCAL_RUNNER_POLL_TIMEOUT  # 120s!
    while time.time() < deadline:
        async with AsyncSessionLocal() as db:
            job = await db.get(TranscriptJob, job_uuid)
            ...
        await asyncio.sleep(LOCAL_RUNNER_POLL_INTERVAL)  # 2s
```
Każdy `/v1/generate` w LOCAL_RUNNER_MODE trzyma goroutynę przez max 120s.  
Przy 50 concurrent users = 50 goroutyn × 120s = **hog puli DB** (60 połączeń/2 = 30 na workera).  
To jest de facto bottleneck przy 50+ concurrent w trybie LOCAL_RUNNER.

**Rekomendacja:**
- Zastąp `requests` przez `httpx.AsyncClient` w `_create_wp_post`
- Dodaj composite index na `usage_logs` (patrz sekcja 9)
- Polling transkryptu: webhookiem/SSE zamiast busy-wait (długookresowo)

**Effort:** 🟡 Średni (`requests` → `httpx` = ~30 minut)

---

## 3. Local Runner — Single Point of Failure

**CO:** Windows Service na jednym PC fetchuje transkrypty YouTube.

**PO CO:** Oracle Cloud VPS ma zbanowane IP przez YouTube. Lokalny PC ma normalne IP.

**Obecny stan:**
```
1 Windows PC → 1 Local Runner → poll co 10s → fetch 1 transkrypt naraz
```

**Limity:**

| Scenariusz | Skutek |
|-----------|--------|
| PC się wyłącza / reboot | Wszystkie pending joby czekają w nieskończoność |
| Antywirusowy skan w tle | YouTube rate limit hit |
| 10+ concurrent generate | Queue rośnie, użytkownicy czekają 120s+ |
| 1 użytkownik wkleja 5 URLi | Serial processing — ostatni czeka 5×~50s |
| Internet na PC padnie | Cały pipeline zatrzymany |

**Brak mechanizmów:**
- Brak health check runnera z perspektywy API
- Brak retry przy timeout (po 120s zwraca error, job wisi w `pending`)
- Brak cleanup stale pending jobs
- Brak monitoringu: API nie wie czy runner żyje

**Rekomendacja (stopniowa):**

**Krok 1 (łatwy):** Dodaj heartbeat endpoint — runner pinguje `/v1/jobs/runner-health` co 30s.  
API wie czy runner żyje. Dashboard pokazuje status runnera.

**Krok 2 (średni):** Cleanup job — cron co 5 minut resetuje `pending` joby starsze niż 5 minut do `failed`.

**Krok 3 (docelowy):** Proxy do transkryptów przez residential IP (np. Brightdata) lub dedykowany VPS z innym IP niż Oracle Cloud ARM.

**Dla 1000 users:** Minimum 10-20 równoległych runner instancji (różne IPs). Architektura musi wspierać multi-runner.

**Effort:** 🔴 Wysoki (multi-runner = redesign job queue)

---

## 4. LLM API Latency — Claude Calls

**CO:** `core/generator.py` wywołuje Anthropic Claude API — synchronicznie.

**Obecny stan:**
```python
# pipeline.py — opakowane w to_thread, ale:
seo = await asyncio.to_thread(
    generate_schema,      # Wewnątrz: anthropic.Anthropic().messages.create(...)
    ...
    0,  # sleep_between — 0s (produkcja bez throttlingu)
)
```

**Zmierzone czasy (z ARCHITECTURE.md):** ~50s per request.

**Limity Anthropic API (Claude Sonnet 4):**
- Tier 1 (default): **50 RPM** (requests per minute), **40 000 TPM**
- Tier 2: 1000 RPM (wymaga $40 spend)

**Analiza przy 1000 users:**

| Scenariusz | RPM do API | Status |
|-----------|-----------|--------|
| 10 concurrent generate | ~12 RPM | ✅ OK |
| 50 concurrent generate | ~60 RPM | ❌ Rate limit |
| 100 concurrent generate | ~120 RPM | ❌ 429 errors |

Przy 1000 userów nawet 1% aktywnych jednocześnie = 10 requestów/min → OK.  
Ale 5% aktywnych = 50 RPM → **rate limit hit**.

**Brak mechanizmów:**
- Brak retry przy 429 (Anthropic rate limit)
- Brak timeout dla LLM call (może wisieć bez odpowiedzi)
- Brak circuit breaker
- Brak caching wyników (ten sam URL = powtórne wywołanie LLM)

**Rekomendacja:**

```python
# Dodaj timeout:
client = anthropic.Anthropic(timeout=60.0)  # max 60s

# Dodaj retry przy 429:
import tenacity
@tenacity.retry(
    retry=tenacity.retry_if_exception_type(anthropic.RateLimitError),
    wait=tenacity.wait_exponential(multiplier=1, min=5, max=60),
    stop=tenacity.stop_after_attempt(3),
)
def _call_claude(...):
    ...
```

**Cache LLM wyników** (HIGH VALUE): Ten sam video_url → ten sam wynik Claude.  
Redis cache `video_id → schema_data` z TTL 24h → przy ponownym zapytaniu: instant response.

**Effort:** 🟡 Średni (retry + timeout = ~1h), 🔴 Wysoki (Redis cache = nowy serwis)

---

## 5. Job Queue — transcript_jobs vs Redis/Celery/ARQ

**CO:** Tabela `transcript_jobs` działa jako message queue dla Local Runnera.

**Obecny stan:**
```sql
-- transcript_jobs jako queue:
SELECT * FROM transcript_jobs WHERE status = 'pending' ORDER BY created_at ASC
-- Pollowane co 10s przez runnera i co 2s przez pipeline
```

**Analiza — czy to wystarczy?**

Dla **obecnej skali** (1 runner, ~50 requestów/dzień): **TAK, wystarczy.**

Tabela jako queue to uznany pattern ("Poor Man's Queue"). PostgreSQL z indexem na `status`  
(już istnieje — `index=True` w modelu) obsłuży setki jobów bez problemu.

**Kiedy tabela przestaje wystarczać:**

| Skalowanie | Problem |
|-----------|--------|
| 10+ runnerów pollujących równocześnie | Race condition — dwa runnery pobiorą ten sam job |
| 1000+ jobów w kolejce | `SELECT WHERE status='pending'` staje się wolny |
| Priorytety (pro > free) | Tabela nie ma wbudowanego priority scheduling |
| Dead letter queue | Brak — failed jobs są finalne |
| Retry mechanizm | Brak — trzeba implementować ręcznie |

**Race condition przy multi-runner** (KRITYCZNY przy skalowaniu):
```sql
-- Dwa runnery mogą pobrać ten sam job:
SELECT * FROM transcript_jobs WHERE status = 'pending' LIMIT 1
-- Runner A i Runner B widzą ten sam row → obaj go przetwarzają
```
Fix: `SELECT ... FOR UPDATE SKIP LOCKED` — PostgreSQL-native queue pattern.

**Rekomendacja:**

**Krok 1 (teraz):** Dodaj `SELECT ... FOR UPDATE SKIP LOCKED` do `GET /v1/jobs/pending`.

```sql
-- Atomowy pickup — żaden runner nie weźmie tego samego joba
SELECT id, video_url FROM transcript_jobs
WHERE status = 'pending'
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1
```

**Krok 2 (przy 10+ runnerach):** Zostań przy PostgreSQL queue (SKIP LOCKED) — Redis/Celery  
wprowadzają dodatkową infrastrukturę bez proporcjonalnych korzyści na tej skali.

**Krok 3 (przy 100+ runnerach, 10 000+ jobów/dzień):** ARQ (async Redis Queue) lub Celery.

**Effort:** 🟢 Niski (SKIP LOCKED = 5 linii kodu)

---

## 6. Caching — Obecny Stan i Rekomendacje

**CO:** Analiza co jest cachowane (nic) i co warto cachować.

**Obecny stan: Brak jakiegokolwiek cache.**

Każde żądanie trafia do DB / zewnętrznego API:
- `/v1/users/me` → SELECT do DB (plan, usage)
- `check_quota()` → COUNT(*) na `usage_logs` przy każdym generowaniu
- `/v1/generate` → YouTube API + Claude → ~50s, zawsze
- `/v1/admin/stats` → aggregate queries za każdym razem

**Priorytety cachowania:**

### Cache Tier 1 — IN-MEMORY (bez Redis, gotowe dziś)

| Co cachować | TTL | Zysk |
|------------|-----|------|
| `plans` tabela | Process lifetime | 4 plany, nigdy się nie zmieniają mid-session |
| JWT decode result | Token lifetime | Każdy request dekoduje JWT — można cachować per-token |

```python
# Prosty LRU cache dla planów
from functools import lru_cache

@lru_cache(maxsize=10)
def get_plan_cached(plan_id: str) -> dict:
    ...
```

### Cache Tier 2 — APPLICATION-LEVEL (bez Redis)

| Co cachować | TTL | Zysk |
|------------|-----|------|
| User plan + quota | 60s per user | Eliminuje 1 DB query per request |
| `/v1/admin/stats` | 5 min | Heavy aggregate query, tylko admini |

### Cache Tier 3 — REDIS (wymaga nowego serwisu)

| Co cachować | TTL | Zysk |
|------------|-----|------|
| LLM wyniki (video_id → schema_data) | 24h | Ten sam URL = instant odpowiedź, ~$0 LLM cost |
| Quota count per user | 60s | Eliminuje COUNT(*) per request |
| YouTube metadata | 1h | yt-dlp fetch = powolny |

**Najwyższa wartość — cache LLM wyników:**  
Ponowne generowanie tego samego video_id = identyczny wynik Claude.  
Redis cache eliminuje ~50s latency i koszt API.

**Effort:** 🟢 Niski (lru_cache) → 🔴 Wysoki (Redis = nowy kontener + logika invalidacji)

---

## 7. Stateless API — Skalowalność Horyzontalna

**CO:** Czy API jest bezstanowe i może być replikowane?

**Obecny stan: CZĘŚCIOWO stateless.**

**✅ Co jest bezstanowe:**
- FastAPI handlers — nie trzymają stanu w pamięci
- JWT auth — token niesie stan użytkownika
- DB connections — przez pool, współdzielone
- LLM calls — bezstanowe (każdy request niezależny)

**❌ Co NIE jest bezstanowe:**

### 7A. Pliki tymczasowe — `tempfile.TemporaryDirectory()`
```python
# pipeline.py
with tempfile.TemporaryDirectory() as tmp_dir:
    meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)
    # vtt_path = tmp_dir/video_id.vtt
    seo = await asyncio.to_thread(generate_schema, ..., vtt_path, ...)
```
Pliki VTT są tworzone na lokalnym dysku instancji. Przy 2 instancjach API  
(horizontal scale) instancja A stworzy job, ale instancja B może pollować rezultat  
i nie mieć pliku VTT. W praktyce: `run_generate` jest jedną funkcją — plik jest  
tworzony i konsumowany w tej samej instancji w tym samym request. **OK dla teraz.**

### 7B. `LOCAL_RUNNER_MODE` + DB polling — kurierowany do konkretnej instancji
Kiedy runner wysyła `POST /v1/jobs/{id}/result` przez nginx → może trafić  
na inną instancję API niż ta która polluje. Pipeline `_wait_for_transcript`  
polluje DB (nie pamięć), więc **to jest OK** — DB jest wspólny.

### 7C. In-memory state przy multi-worker Uvicorn (obecnie 2 workers)
```bash
# Dockerfile.api
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8085", "--workers", "2"]
```
`--workers 2` = 2 osobne procesy. Każdy ma własną pamięć.  
LRU cache (jeśli dodany) NIE będzie współdzielony między workerami.  
→ Redis wymagany dla shared cache.

**Ocena skalowalności horyzontalnej:**  
API *może* być replikowane (N instancji za load balancerem), ale:  
1. Każda instancja ma własną pulę DB — konieczne monitorowanie max_connections  
2. Cache musi być Redis-based  
3. Sesje JWT są bezstanowe — OK

**Rekomendacja:**  
Dla 1000 users: **wystarczy 1 instancja z 4-8 workers** (Oracle ARM ma 4 CPU).  
`uvicorn --workers 4` zamiast 2.

**Effort:** 🟢 Niski (workers: 2→4 = zmiana 1 cyfry w Dockerfile)

---

## 8. Docker Compose vs Kubernetes — Mapa Migracji

**Obecny stan:** Docker Compose na 1 VPS (Oracle ARM, shared resources).

**Analiza progów migracji:**

| Próg | Metrika | Akcja |
|------|---------|-------|
| **Teraz** | <100 users, <10 req/min | Docker Compose — OK |
| **Faza 1A** | 100-500 users | Docker Compose + zasoby CPU/RAM |
| **Faza 1B** | 500-1000 users | Docker Swarm lub 2 VPS (API + DB osobno) |
| **Faza 2** | 1000-5000 users | Kubernetes (GKE/EKS) + managed DB (Cloud SQL) |
| **Faza 3** | 5000+ users | K8s + autoscaling + CDN + read replicas |

**Co wymaga migracji PRZED Kubernetes:**
1. Baza danych musi wyjść z Docker Compose → managed PostgreSQL (Cloud SQL, Supabase)
2. Redis jako osobny serwis (nie w compose)
3. Secrets management (nie .env file) → Vault lub Cloud Secret Manager
4. CI/CD pipeline (nie ręczny git pull)

**Kiedy NIE migrować do K8s:**
- <5000 concurrent users → overhead K8s > korzyści
- Brak DevOps zasobów → trudny w utrzymaniu
- Oracle ARM nie ma managed K8s → trzeba migrować cloud

**Rekomendacja dla VSE:**  
Obecny próg migracji: **gdy użytkownicy płacą i generują >500 req/dzień**.  
Do 500 users: Docker Compose z 4 workers Uvicorn + PgBouncer.

**Effort:** 🔴 Bardzo wysoki (K8s = multi-tydzień projektu)

---

## 9. Database Indexy

**CO:** Analiza istniejących indexów i brakujących.

**Istniejące indexy (z kodu ORM):**

```python
# api/models/job.py
status = Column(String(20), nullable=False, default="pending", index=True)   # ✅
user_id = Column(UUID, ForeignKey("users.id"), nullable=True, index=True)     # ✅

# api/models/user.py (z ARCHITECTURE.md)
email = Column(String(255), unique=True)   # ✅ unique = implicit index
google_id = Column(String(255), unique=True)  # ✅
```

**transcript_jobs.status** — indeks ✅ ISTNIEJE (potwierdzono z kodu).  
Zapytanie `WHERE status='pending'` jest efektywne.

**BRAKUJĄCE indexy — krytyczne przy skali:**

### 9A. `usage_logs` — brak composite indexu
```python
# Obecne zapytanie w quota.py:
SELECT COUNT(*) FROM usage_logs
WHERE user_id = ? AND success = TRUE AND created_at >= ?
```
Brak indexu na `(user_id, success, created_at)` → **full table scan** przy dużej tabeli.  
Przy 1000 userów × 300 req/miesiąc = 300 000 wierszy.

```python
# Fix w api/models/user.py (UsageLog model):
from sqlalchemy import Index

class UsageLog(Base):
    ...
    __table_args__ = (
        Index('ix_usage_logs_user_month', 'user_id', 'success', 'created_at'),
    )
```

### 9B. `transcript_jobs` — brak composite indexu dla cleanup
```sql
-- Potrzebne dla cleanup stale jobs:
SELECT * FROM transcript_jobs
WHERE status = 'pending' AND created_at < NOW() - INTERVAL '5 minutes'
```
Indeks na `status` istnieje, ale `(status, created_at)` byłby szybszy.

### 9C. `usage_logs.user_id` — brak prostego indexu
Z ARCHITECTURE.md wiadomo że `user_id` jest FK, ale nie widać `index=True` w schemacie.  
Uzupełnić.

**Rekomendacja:**
```python
# Natychmiast dodaj do UsageLog:
__table_args__ = (
    Index('ix_usage_logs_user_month', 'user_id', 'success', 'created_at'),
)

# Natychmiast dodaj do TranscriptJob:
__table_args__ = (
    Index('ix_transcript_jobs_status_created', 'status', 'created_at'),
)
```

**Effort:** 🟢 Niski (dodanie 3 linii + restart API → auto-create)

---

## Matryca Rekomendacji — Priorytet × Effort

| # | Problem | Priorytet | Effort | Akcja |
|---|---------|-----------|--------|-------|
| 1 | **Composite index `usage_logs`** | 🔴 CRITICAL | 🟢 Niski | Dodaj teraz — zmiana 3 linii |
| 2 | **`SELECT FOR UPDATE SKIP LOCKED`** w jobs queue | 🔴 CRITICAL | 🟢 Niski | Dodaj teraz — 5 linii SQL |
| 3 | **Uvicorn workers: 2→4** | 🔴 CRITICAL | 🟢 Niski | Zmień 1 cyfra w Dockerfile |
| 4 | **pool_pre_ping + pool_recycle** w db.py | 🟠 HIGH | 🟢 Niski | Dodaj teraz — 2 linie |
| 5 | **Rate limiting** na `/v1/generate` | 🟠 HIGH | 🟢 Niski | slowapi lub nginx limit_req |
| 6 | **Runner health check** endpoint | 🟠 HIGH | 🟡 Średni | Nowy endpoint + runner ping |
| 7 | **Cleanup stale jobs** cron | 🟠 HIGH | 🟡 Średni | Background task w FastAPI |
| 8 | **LLM timeout + retry** (tenacity) | 🟠 HIGH | 🟡 Średni | ~1h implementacji |
| 9 | **`requests`→`httpx`** w pipeline | 🟡 MEDIUM | 🟡 Średni | Refactor _create_wp_post |
| 10 | **Redis cache** LLM wyników | 🟡 MEDIUM | 🔴 Wysoki | Nowy serwis + logika |
| 11 | **PgBouncer** connection pooler | 🟡 MEDIUM | 🔴 Wysoki | Nowy kontener |
| 12 | **Multi-runner** architektura | 🟡 MEDIUM | 🔴 Wysoki | Redesign job queue |
| 13 | **Kubernetes** migracja | 🟢 LOW | 🔴 Wysoki | >500 users aktywnych |

---

## Architektura Docelowa — 1000 Users

```
[Cloudflare CDN]
    ↓
[nginx — rate limiting, SSL termination]
    ↓                    ↓
[Next.js :3001]    [FastAPI :8085 — 4 workers]
                         ↓          ↓
                   [PostgreSQL]  [Redis]
                      + PgBouncer   ↑
                                 [LLM cache]
                         ↓
                   [transcript_jobs queue]
                   (SELECT FOR UPDATE SKIP LOCKED)
                         ↓
              [Runner A]  [Runner B]  [Runner C]
              (3+ instancje na różnych IP)
```

---

## Szybkie Wygrane — Do Zrobienia Teraz (Quick Wins)

### QW1: Uvicorn workers 2→4 (5 minut)
```dockerfile
# Dockerfile.api — zmień:
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8085", "--workers", "4"]
```

### QW2: DB pool hardening (10 minut)
```python
# api/db.py — dodaj:
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_timeout=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

### QW3: Composite index usage_logs (15 minut)
```python
# api/models/user.py — w UsageLog:
__table_args__ = (
    Index('ix_usage_logs_user_month', 'user_id', 'success', 'created_at'),
)
```

### QW4: Rate limiting (20 minut)
```bash
pip install slowapi
```
```python
# api/main.py:
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

# api/routers/generate.py:
@router.post("/generate")
@limiter.limit("10/minute")  # max 10 generate/min per IP
async def generate_endpoint(request: Request, req: GenerateRequest):
    ...
```

### QW5: SELECT FOR UPDATE SKIP LOCKED (30 minut)
```python
# api/routers/jobs.py — GET /v1/jobs/pending:
from sqlalchemy import update

# Atomowy pickup:
result = await db.execute(
    select(TranscriptJob)
    .where(TranscriptJob.status == "pending")
    .order_by(TranscriptJob.created_at.asc())
    .limit(10)
    .with_for_update(skip_locked=True)
)
```

---

*arch-scale-01 | video-seo-engine | 2026-06-16 — v1.0 — analiza skalowalności*
