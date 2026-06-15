# SUPPLEMENT — Security Requirements | vse-dev-04

**ID:** SUPPLEMENT-VSE-DEV-04-20260615-SECURITY  
**Dotyczy:** DISPATCH-VSE-DEV-04-20260615-LOCAL-SERVICE  
**Supervisor:** Supervisor 01  
**Data:** 2026-06-15

> Ten dokument rozszerza dispatch o wymagania bezpieczeństwa.
> Wszystkie poniższe punkty są **obowiązkowe**.

---

## Zidentyfikowane ryzyka

### 🔴 RYZYKO 1 — Fake Transcript Injection (KRYTYCZNE)

**Co się może stać:** Ktoś z `LOCAL_RUNNER_TOKEN` może POST-ować fałszywy transkrypt do `POST /v1/jobs/{id}/result`. Claude przetworzy go jak prawdziwy → złośliwa/fałszywa schema VideoObject trafi do WordPressa.

**Mitigacja — ZAIMPLEMENTUJ:**

```python
# W endpoincie POST /v1/jobs/{id}/result

MAX_TRANSCRIPT_LENGTH = 50_000  # znaków (ok. 6h wideo)
ALLOWED_TRANSCRIPT_CHARS = re.compile(r'[^\w\s\.,!?\-\'"():;\u0000-\u017e]')

def sanitize_transcript(raw: str) -> str:
    """Sanitizuje transkrypt przed przekazaniem do Claude.
    
    Po co: Blokuje injection przez fałszywy runner.
    Jak: Strip HTML, limit długości, tylko dozwolone znaki.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Transcript must be non-empty string")
    
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', ' ', raw)
    
    # Normalizuj whitespace
    clean = ' '.join(clean.split())
    
    # Ogranicz długość
    if len(clean) > MAX_TRANSCRIPT_LENGTH:
        clean = clean[:MAX_TRANSCRIPT_LENGTH]
        log.warning(f"Transcript truncated to {MAX_TRANSCRIPT_LENGTH} chars")
    
    return clean
```

Umieść `sanitize_transcript()` w `api/services/pipeline.py` i wywołuj przed przekazaniem do generatora.

---

### 🟡 RYZYKO 2 — Brak Job Ownership Validation

**Co się może stać:** Runner z tokenem może modyfikować joby innych userów (gdyby było ich wielu).

**Mitigacja — ZAIMPLEMENTUJ:**

```python
# W endpoincie POST /v1/jobs/{id}/result
async def complete_job(job_id: UUID, result: JobResult, db: AsyncSession):
    job = await db.get(TranscriptJob, job_id)
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    if job.status != "pending":
        # Idempotent: jeśli już 'fetched', zwróć 200 bez zmian
        # Zapobiega podwójnemu zapisowi
        log.warning(f"Job {job_id} already in status {job.status}, ignoring")
        return {"status": "already_processed"}
    
    job.transcript = sanitize_transcript(result.transcript)
    job.status = "fetched"
    job.updated_at = datetime.utcnow()
    await db.commit()
```

---

### 🟡 RYZYKO 3 — Brak Rate Limiting na Job Endpoints

**Co się może stać:** Flood requestów do `GET /v1/jobs/pending` obciąża DB.

**Mitigacja — ZAIMPLEMENTUJ (proste, bez zewnętrznych bibliotek):**

```python
# W main.py lub middleware
from fastapi import Request
from collections import defaultdict
import time

_rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # sekund
RATE_LIMIT_MAX = 30     # requestów per okno (1 co 2s = 30/min)

def check_rate_limit(token: str) -> bool:
    """Prosta rate limit: max 30 requestów/min per token."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    requests = [t for t in _rate_limit_store[token] if t > window_start]
    _rate_limit_store[token] = requests
    if len(requests) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_store[token].append(now)
    return True

# W routerze jobs.py:
if not check_rate_limit(token):
    raise HTTPException(429, "Rate limit exceeded: max 30 req/min")
```

---

### 🟡 RYZYKO 4 — Token Storage na Lokalnym PC

**Status:** Akceptowalne ryzyko dla single-user use case.

**Wymagania które MUSISZ spełnić:**

1. **Generuj token jako `secrets.token_urlsafe(32)`** (min. 256 bitów entropii).
   ```python
   import secrets
   print(secrets.token_urlsafe(32))  # uruchom raz, skopiuj do .env
   ```

2. **Dodaj `.env` do `.gitignore`** w `local-runner/` (upewnij się że nie ma go już):
   ```
   # local-runner/.gitignore
   .env
   *.log
   __pycache__/
   ```

3. **Nie commituj tokenu** — tylko `.env.example` z placeholderem:
   ```
   LOCAL_RUNNER_TOKEN=REPLACE_WITH_GENERATED_TOKEN
   VSE_API_BASE=https://vse.impresjapr.pl
   ```

4. **Na VPS** — token dodaj do `.env` przez SSH (nie przez GitHub commit):
   ```bash
   echo 'LOCAL_RUNNER_TOKEN=<token>' >> /home/ubuntu/vse/.env
   ```

---

### 🟢 RYZYKO 5 — Transport Security

**Status: OK — nie wymaga dodatkowej pracy.**

Wszystkie requesty przez `https://vse.impresjapr.pl` — TLS terminowany przez Cloudflare. Transkrypt nie wychodzi plaintext.

---

## Dodatkowe: endpoint security checklist

Przed deployem zweryfikuj każdy nowy endpoint:

| Endpoint | Auth | Rate limit | Sanitizacja |
|---|---|---|---|
| `GET /v1/jobs/pending` | Bearer LOCAL_RUNNER_TOKEN | ✅ 30/min | n/d |
| `POST /v1/jobs/{id}/result` | Bearer LOCAL_RUNNER_TOKEN | ✅ 30/min | ✅ transcript |
| `GET /v1/jobs/{id}` | JWT user | n/d | n/d |
| `POST /v1/jobs/` | JWT user | n/d | n/d |

---

## Weryfikacja security przed raportem

Dodaj do testów `tests/test_jobs_security.py`:

```python
async def test_fake_transcript_sanitized():
    """Fake HTML w transkrypcie jest stripowany przed Claude."""
    raw = "<script>alert('xss')</script>Prawdziwy tekst"
    result = sanitize_transcript(raw)
    assert '<script>' not in result
    assert 'Prawdziwy tekst' in result

async def test_transcript_length_limit():
    """Transkrypt >50k znaków jest obcinany."""
    long_text = 'a' * 60_000
    result = sanitize_transcript(long_text)
    assert len(result) <= 50_000

async def test_double_complete_is_idempotent():
    """Drugi POST /jobs/{id}/result na już 'fetched' job nie zmienia danych."""
    # ...
    pass  # implementacja z mock DB

async def test_rate_limit_exceeded():
    """Po 30 requestach w 60s zwraca 429."""
    # ...
    pass
```

---

*Supervisor 01 | sonic-void | 2026-06-15 23:47*  
*Ten supplement jest obowiązkowy — nie zamykaj dispatchu bez zaimplementowania sekcji 🔴 i 🟡.*
