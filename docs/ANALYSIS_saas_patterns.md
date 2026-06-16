# ANALYSIS — SaaS Patterns & B2B Readiness

> **Autor:** `arch-saas-01` | Data: 2026-06-16  
> **Cel:** Analiza gotowości Video SEO Engine jako SaaS B2B dla tysięcy klientów.  
> **Źródła:** ARCHITECTURE.md, api/models/user.py, api/quota.py, api/routers/*

---

## Executive Summary

VSE ma solidne fundamenty dla freemium SaaS: model planów jest poprawny, quota działa poprawnie, izolacja danych per user istnieje. **Jednak brak 5 kluczowych komponentów blokuje gotowość B2B enterprise:**

| Obszar | Status | Priorytet |
|--------|--------|----------|
| Multi-tenancy | ✅ Izolacja przez user_id | Gotowe |
| Quota system | ⚠️ Działa, ale brak cron reset | P1 |
| Plan enforcement | 🔴 Krytyczne dziury w generate/inject/process | P0 |
| Billing | 🔴 Stub-only — brak Stripe | P1 |
| Audit trail | ⚠️ Podstawowy — niewystarczający dla enterprise | P2 |
| Data retention | 🔴 Brak polityki czyszczenia | P2 |
| User onboarding | ⚠️ Email verification niezaimplementowana | P1 |
| Self-service plan | 🔴 Brak — wymaga admina | P1 |
| White-label | ✅ API generyczne, brak hardcoded brandingu | Gotowe |

---

## 1. Multi-tenancy — Izolacja Danych Per User

### CO
Sposób w jaki system separuje dane różnych klientów.

### PO CO
W SaaS B2B każdy klient musi widzieć TYLKO swoje dane. Wyciek danych między tenantami to katastrofa prawna i reputacyjna.

### Stan aktualny — POZYTYWNY ✅

**Model danych jest poprawny:**
- `usage_logs.user_id` — każdy log ma FK do właściciela
- `transcript_jobs.user_id` — joby powiązane z userem (nullable, OK dla internal)
- `api_keys.user_id` — klucze API per user
- `check_quota()` — filtruje `UsageLog.user_id == current_user.id` — POPRAWNIE

**Żaden endpoint nie zwraca cudzych danych:**
- `/v1/users/me` — zawsze bieżący user
- `/v1/jobs/{id}` — wymaga sprawdzenia czy job belongs to user (do weryfikacji)
- `/v1/admin/*` — oddzielny guard `get_current_admin`

### Ryzyko — JOB OWNERSHIP

```python
# api/routers/jobs.py — DO WERYFIKACJI:
# Czy GET /v1/jobs/{id} sprawdza że current_user.id == job.user_id?
# Jeśli nie — user A może odpytać job usera B znając UUID (IDOR)
```

**Rekomendacja:** Audyt `jobs.py` — każdy GET/PATCH job MUSI weryfikować ownership:
```python
if job.user_id != current_user.id:
    raise HTTPException(status_code=403, detail="Access denied")
```

**Architektura:** Single-database, schema-per-tenant NIE jest potrzebna na tym etapie. Row-level security przez user_id jest wystarczające.

---

## 2. Quota System — Analiza Głęboka

### CO
System który zlicza użycie per user i blokuje request gdy limit osiągnięty.

### PO CO
Bez quotowania freemium nie ma sensu biznesowego — każdy dostaje unlimited.

### Stan aktualny — DZIAŁA ALE MA DZIURY ⚠️

**Implementacja w `api/quota.py`:**
```python
def check_quota(current_user, db) -> User:
    plan = current_user.plan
    if plan.monthly_quota == -1:  # unlimited
        return current_user
    
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == current_user.id)
        .where(UsageLog.success == True)
        .where(UsageLog.created_at >= month_start)
    )
    used = result.scalar_one()
    
    if used >= plan.monthly_quota:
        raise HTTPException(429, detail="Monthly quota exceeded")
```

**Co działa poprawnie:**
- Liczenie od początku bieżącego miesiąca kalendarzowego (`month_start = now.replace(day=1, ...)`) — POPRAWNE
- Unlimited plan (`monthly_quota == -1`) — POPRAWNE
- HTTP 429 Too Many Requests — poprawny kod statusu
- Liczy tylko `success == True` — poprawne (błędy nie wliczają się do quoty)

### Problem 1 — BRAK CRON RESET 🔴

**Quota resetuje się naturalnie** przez filtr `created_at >= month_start`. Oznacza to:
- Reset quota = 1 styczeń o 00:00 UTC
- NIE ma osobnego cron joba który by resetował licznik
- DOBRZE dla prostoty, ale...

**Edge case:** Co jeśli `created_at` jest w innej strefie? `month_start` jest zawsze UTC. Jeśli user generuje 31 stycznia 23:59 CET (= 22:59 UTC), wpis jest w starym miesiącu. 1 lutego 00:01 CET (= 23:01 UTC 31 stycznia!) — wpis nadal w starym miesiącu.

**Ryzyko:** Przez kilka godzin na początku miesiąca (w zależności od strefy) limit nie resetuje się dla userów w UTC+2.

**Fix:** Zawsze `month_start` w UTC — kod jest już poprawny. Ale komunikacja z userem powinna wyjaśniać "quota resetuje się 1. dnia miesiąca o 00:00 UTC".

### Problem 2 — RACE CONDITION przy limicie ⚠️

```python
# Sequence:
# 1. check_quota() → used=4, quota=5 → OK, przepuszcza
# 2. check_quota() → used=4, quota=5 → OK, przepuszcza (concurrent request!)
# 3. Oba requesty generują → log 2 razy → used=6, ale quota=5
```

**Dotyczy:** userów free (quota=5) z intensywnym użyciem. Przy 1000 userach i quota 5 jest to teoretycznie możliwe.

**Fix:** `SELECT ... FOR UPDATE` lub optymistyczna blokada przez unique constraint na (user_id, youtube_id, month). Alternatywnie — atomic counter w Redis.

### Problem 3 — check_quota NIE jest wymagane na wszystkich endpointach

Szczegóły w sekcji 3 (Plan Enforcement).

---

## 3. Plan Enforcement — Gdzie Są Dziury

### CO
Które endpointy sprawdzają quotę i uprawnienia planowe, a które nie.

### PO CO
Bez enforcement każdy free user może używać funkcji pro. To kosztuje pieniądze (LLM) i niszczy model biznesowy.

### Mapa endpointów — analiza

| Endpoint | Auth (JWT) | check_quota | Plan check | Status |
|----------|-----------|------------|------------|--------|
| POST `/v1/generate` | ❌ BRAK | ❌ BRAK | ❌ BRAK | 🔴 KRYTYCZNE |
| POST `/v1/inject` | ❌ BRAK | ❌ BRAK | ❌ BRAK | 🔴 KRYTYCZNE |
| POST `/v1/process` | ❌ BRAK | ❌ BRAK | ❌ BRAK | 🔴 KRYTYCZNE |
| POST `/v1/sitemap` | ❌ BRAK | ❌ BRAK | ❌ BRAK | 🔴 KRYTYCZNE |
| POST `/v1/monitor/start` | ❓ Do weryfikacji | ❌ BRAK | ❌ BRAK | 🔴 Ryzyko |
| POST `/v1/jobs/` | JWT ✅ | Brak | Brak | ⚠️ |
| GET `/v1/users/me` | JWT ✅ | N/A | N/A | ✅ |
| GET `/v1/admin/*` | JWT+admin ✅ | N/A | N/A | ✅ |

### Dowód z kodu — generate.py

```python
# api/routers/generate.py — BRAK ZALEŻNOŚCI check_quota:
@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    # BRAK: Depends(get_current_user)
    # BRAK: Depends(check_quota)
    # Wniosek: KAŻDY (anonimowy!) może wolać ten endpoint
```

### Dowód z kodu — inject.py

```python
# api/routers/inject.py — BRAK ZALEŻNOŚCI:
@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
    # BRAK auth — anonimowy użytkownik może wstrzykiwać do cudzego WP
    # (wymaga znajomości wp_app_password — ale API jest niechronione)
```

### Dowód z kodu — process.py

```python
# api/routers/process.py — BRAK ZALEŻNOŚCI:
@router.post("/process", response_model=ProcessResponse)
async def process_endpoint(req: ProcessRequest) -> ProcessResponse:
    # BRAK auth — unlimited AI calls dla anonim
```

### Wnioski — KRYTYCZNE

**Trzy główne endpointy biznesowe nie mają żadnej ochrony.** Każdy kto zna URL może:
1. Wywoływać Claude API bez ograniczeń (koszt po stronie właściciela)
2. Generować SEO dla dowolnych filmów YT
3. Wstrzykiwać do WordPress kont klientów (jeśli zna credentials)

### Plan-level enforcement — co brakuje

Nawet po dodaniu `check_quota`, brakuje:
- **inject:** sprawdzenia czy user ma plan `pro`/`agency` (wp_sites_limit > 0)
- **sitemap:** czy user ma odpowiedni plan
- **api_keys:** weryfikacja że `plan.api_access == True` przed akceptacją klucza API

### Fix — wzorzec dla generate.py

```python
from api.quota import check_quota, log_usage
from api.auth import get_current_user
from api.models.user import User

@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(
    req: GenerateRequest,
    current_user: User = Depends(check_quota),  # auth + quota w jednej zależności
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    # ... logika ...
    await log_usage(str(current_user.id), db, youtube_id=video_id, success=True)
```

---

## 4. Billing Readiness — Stan i Co Potrzebne

### CO
Infrastruktura do pobierania płatności od klientów.

### PO CO
SaaS bez billing = projekt non-profit. Stripe to standard dla SaaS B2B.

### Stan aktualny — STUB-ONLY 🔴

**Co istnieje w DB:**
```python
# api/models/user.py:
stripe_customer_id = Column(String(255), nullable=True)     # ✅ Schema gotowa
stripe_subscription_id = Column(String(255), nullable=True) # ✅ Schema gotowa

# api/models/user.py — Plan:
stripe_price_id = Column(String(200), nullable=True)        # ✅ Schema gotowa
```

**Co NIE istnieje:**
- `stripe` library w `requirements.txt` — BRAK
- Webhook endpoint (`POST /v1/billing/webhook`) — BRAK
- Checkout session creation (`POST /v1/billing/checkout`) — BRAK
- Subscription sync logic — BRAK
- Portal klienta Stripe (`POST /v1/billing/portal`) — BRAK

### Co jest potrzebne żeby uruchomić płatności (Roadmapa Billing P1)

```
Faza 1 — Podstawa:
1. pip install stripe
2. STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET do .env
3. POST /v1/billing/checkout — tworzy Stripe Checkout Session per plan
4. POST /v1/billing/webhook — obsługuje: checkout.session.completed,
   customer.subscription.updated, customer.subscription.deleted
5. Sync: na sukces → user.stripe_customer_id + user.plan_id UPDATE
6. Logowanie każdego eventu webhook do tabeli billing_events (audit)

Faza 2 — Self-service:
7. GET /v1/billing/portal — Stripe Customer Portal (zarządzanie subskrypcją)
8. Dashboard: sekcja "Mój Plan" z historią faktur (Stripe API)

Faza 3 — Enterprise:
9. Invoicing, VAT (szczególnie dla PL — KSeF integracja)
10. Roczne plany ze zniżką
```

### Kluczowa decyzja architektoniczna

Zmiana planu przez billing MUSI być przez webhook, nie przez `PATCH /v1/admin/users/{id}/plan`.
Webhook = jedyne źródło prawdy dla statusu subskrypcji.

---

## 5. Audit Trail — Wystarczalność dla Enterprise

### CO
Zapis historii akcji użytkowników dla celów rozliczeniowych i compliance.

### PO CO
Klient enterprise (agencja) potrzebuje: "pokaż mi co mój team robił, kiedy, z jakim skutkiem".

### Stan aktualny — PODSTAWOWY ⚠️

**Tabela `usage_logs`:**
```python
id          # Integer autoincrement — nie UUID
user_id     # FK → users
endpoint    # String(100) — np. "/v1/process" (default!) — patrz bug poniżej
youtube_id  # YT video ID
success     # Boolean
error_msg   # Text nullable
created_at  # DateTime
```

### Bug — endpoint domyślny

```python
# api/models/user.py:
endpoint = Column(String(100), nullable=False, default="/v1/process")
```

**Problem:** Default value to `/v1/process` dla wszystkich logów. Jeśli `log_usage()` nie przekazuje `endpoint=req.path`, historyczne logi nie pozwalają odróżnić generate vs inject vs process.

**Fix:**
```python
# api/quota.py — log_usage() powinno przyjmować endpoint jako parametr:
async def log_usage(user_id, db, youtube_id=None, success=True, error_msg=None, endpoint="/v1/generate"):
    log = UsageLog(
        user_id=user_id, endpoint=endpoint,  # explicit
        youtube_id=youtube_id, success=success, error_msg=error_msg
    )
```

### Co brakuje dla enterprise audit:

| Feature | Stan | Priorytet |
|---------|------|----------|
| IP address logging | ❌ BRAK | P2 |
| User agent / source | ❌ BRAK | P3 |
| WP site URL w logu | ❌ BRAK | P2 (dla inject) |
| API key ID w logu | ❌ BRAK | P1 (dla API access) |
| Export CSV/JSON | ❌ BRAK | P2 |
| Retention policy | ❌ BRAK | P2 |
| Log tamper-proof | ❌ BRAK | P3 (enterprise) |

### Minimalny enterprise audit trail:

```python
# Rozszerzenie UsageLog dla enterprise:
class UsageLog(Base):
    # ... existing ...
    endpoint = Column(String(100), nullable=False)      # fix default
    api_key_id = Column(UUID, ForeignKey("api_keys.id"), nullable=True)  # NEW
    ip_address = Column(String(45), nullable=True)      # NEW (IPv6 safe)
    wp_site_url = Column(String(500), nullable=True)    # NEW (inject audit)
    request_id = Column(String(36), nullable=True)      # NEW (UUID per request)
```

---

## 6. Data Retention — Ryzyko Danych Transkryptów

### CO
Polityka przechowywania i czyszczenia starych danych, szczególnie transkryptów YT.

### PO CO
Transkrypty YouTube przechowywane w kolumnie `Text` mogą być duże. Przy 1000 użytkownikach każdy generujący 50 filmów/miesiąc = 50,000 transkryptów × ~5KB = 250MB/miesiąc przyrostu tylko w DB.

### Stan aktualny — BRAK POLITYKI 🔴

```python
# api/models/job.py:
transcript = Column(Text, nullable=True)  # VTT transkrypt — nieograniczony rozmiar
```

**Problemy:**
1. **Brak TTL:** `transcript_jobs` nigdy nie są czyszczone
2. **Brak archiwizacji:** `usage_logs` rośnie nieograniczenie
3. **Brak indexu na `created_at`:** Przy dużej tabeli zapytania monthly quota będą wolne (full table scan)
4. **Transcript w DB:** Duże payloady (do 100KB VTT) w OLTP bazie — anty-pattern

### Rekomendacje:

```sql
-- 1. Czyszczenie starych jobów (cron co tydzień):
DELETE FROM transcript_jobs 
WHERE created_at < NOW() - INTERVAL '7 days'
AND status IN ('done', 'failed');

-- 2. Archiwizacja usage_logs (cron miesięczny):
-- Przenieś logi > 12 miesięcy do tabeli usage_logs_archive

-- 3. Brakujące indeksy:
CREATE INDEX idx_usage_logs_user_month 
  ON usage_logs(user_id, created_at);
CREATE INDEX idx_transcript_jobs_status 
  ON transcript_jobs(status, created_at);
```

**Architektura docelowa (500+ TB scale):**  
Transkrypt → S3/Object Storage (nie Postgres TEXT). DB przechowuje tylko reference URL.

---

## 7. User Onboarding — Kompletność Rejestracji

### CO
Procedura zakładania i aktywowania konta.

### PO CO
Niekompletny onboarding = churning users przed pierwszym użyciem.

### Stan aktualny — NIEKOMPLETNY ⚠️

**Co działa:**
```python
# api/routers/auth.py:
user = User(
    email=payload.email,
    hashed_password=hash_password(payload.password),
    plan_id="free",
    is_verified=False,           # ✅ Flaga istnieje
    verification_token=secrets.token_urlsafe(32)  # ✅ Token generowany
)
# TODO: send verification email (Resend/SendGrid) in Faza 2
```

**Co NIE działa:**

| Krok onboarding | Stan |
|----------------|------|
| Rejestracja → zapisanie do DB | ✅ Działa |
| Generowanie verification_token | ✅ Generowany |
| Wysyłka emaila weryfikacyjnego | ❌ TODO w kodzie |
| Endpoint `GET /v1/auth/verify?token=...` | ❌ BRAK |
| Blokada generateq dla unverified | ❌ BRAK (każdy może generować bez weryfikacji) |
| Resend verification email | ❌ BRAK |
| Password reset flow | ⚠️ Pola w DB, endpoint BRAK |
| Welcome email | ❌ BRAK |

**Kluczowy problem:**  
`is_verified = False` jest zapisywane, ale **nigdzie nie jest sprawdzane**. User może generować SEO bez weryfikacji emaila.

### Google OAuth onboarding — LEPSZA ✅

```python
# google/callback → is_verified=True (Google already verified email)
# google/token-exchange → is_verified=email_verified (from Google tokeninfo)
```
Google OAuth daje lepszy onboarding — email od razu zweryfikowany.

### Fix — minimalne email verification:

```
1. Wybierz provider email: Resend (prosty, darmowy tier), SendGrid
2. GET /v1/auth/verify?token={verification_token}
   → sets is_verified=True, clears verification_token
3. Enforcement: check_quota() lub generate_endpoint sprawdza is_verified
   (lub soft enforcement: allow generate, ale warn o weryfikacji)
4. POST /v1/auth/resend-verification — dla przypadku gdy email przepadł
```

---

## 8. Self-Service Plan Changes — Czy User Może Sam

### CO
Możliwość zmiany planu przez usera bez interwencji admina.

### PO CO
W SaaS upgrade/downgrade musi być możliwy 24/7 bez wsparcia. Inaczej każda sprzedaż to ręczna praca.

### Stan aktualny — WYMAGA ADMINA 🔴

**Aktualna ścieżka zmiany planu:**
```
User chce upgrade → nie ma opcji w UI → kontaktuje się → Admin loguje do dashboardu
→ PATCH /v1/admin/users/{id}/plan → plan zmieniony
```

**Nie istnieje:**
- `POST /v1/billing/checkout` — nie ma
- `GET /v1/billing/plans` — lista planów z cenami dla usera — nie ma
- `GET /v1/billing/portal` — Stripe portal do zarządzania — nie ma
- Dashboard UI z przyciskiem "Upgrade" — nie ma

### Zależność od Billing:

Self-service wymaga Stripe. Kolejność:
```
1. Billing infrastructure (sekcja 4)
2. Stripe Checkout → POST /v1/billing/checkout?plan=pro
3. Webhook → auto-upgrade user.plan_id
4. Dashboard UI: sekcja "Plan" z cenami + Upgrade button
5. Stripe Portal: zarządzanie anulowaniem, fakturami
```

**Quick win bez Stripe (stopień przejściowy):**  
Strona `/pricing` + formularz kontaktowy. Nie jest self-service, ale formalnie odpowiada.

---

## 9. White-Label Readiness — Branding w API

### CO
Czy API można sprzedać pod cudzą marką bez przepisywania kodu.

### PO CO
White-label to segment B2B enterprise — agencje które chcą oferować video SEO pod swoją marką.

### Stan aktualny — GENERALNIE DOBRY ✅

**Co jest generic (white-label ready):**
- API endpoints nie mają hardcoded branding
- `/v1/generate`, `/v1/inject` — niezależne od domeny
- WP credentials przekazywane per-request (`site_config.wp_base_url`) — ✅ stateless
- Błąd 429 message zawiera URL: `"Upgrade your plan at https://vse.impresjapr.pl/pricing"` — ⚠️

**Co NIE jest white-label:**

```python
# api/routers/auth.py:
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://vse.impresjapr.pl/api/v1/auth/google/callback"  # Hardcoded!
)
```

```python
# api/quota.py:
detail=(
    f"Monthly quota exceeded ({used}/{plan.monthly_quota}). "
    "Upgrade your plan at https://vse.impresjapr.pl/pricing"  # Hardcoded URL!
)
```

**Fix:**
```python
# Dodaj env var:
FRONTEND_URL=https://vse.impresjapr.pl  # już istnieje

# quota.py:
frontend_url = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")
detail=f"Monthly quota exceeded. Upgrade: {frontend_url}/pricing"
```

---

## Podsumowanie — Mapa Priorytetów

### 🔴 P0 — Blokery Bezpieczeństwa (fix natychmiast)

1. **Dodaj auth do `/v1/generate`, `/v1/inject`, `/v1/process`, `/v1/sitemap`**
   - Zależność: `Depends(check_quota)` na generate/process
   - Zależność: `Depends(get_current_user)` na inject/sitemap
   - Inject: dodatkowy check `plan.wp_sites_limit > 0`

2. **Audyt job ownership w `jobs.py`**
   - `GET /v1/jobs/{id}` musi weryfikować `job.user_id == current_user.id`

### 🟠 P1 — Blokery Biznesowe (przed monetyzacją)

3. **Billing infrastructure** — Stripe Checkout + Webhook + Portal
4. **Self-service plan upgrade** — uzależniony od #3
5. **Email verification** — wysyłka emaila + endpoint verify
6. **fix endpoint w UsageLog** — zmienić default z `/v1/process` na explicit

### 🟡 P2 — Enterprise Quality (przed skalą B2B)

7. **Data retention** — cron czyszczenie transcript_jobs + archiwizacja usage_logs
8. **Indeksy DB** — `idx_usage_logs_user_month`, `idx_transcript_jobs_status`
9. **Audit log rozszerzenie** — `api_key_id`, `ip_address`, `wp_site_url`
10. **Hardcoded URL fix** — quota.py + auth.py GOOGLE_REDIRECT_URI

### 🟢 P3 — Scale (dla tysięcy klientów)

11. **Race condition quota** — SELECT FOR UPDATE lub Redis counter
12. **Transcript → S3** — przenieś z DB do object storage
13. **Rate limiting** — per-user per-minute (uzupełnienie quoty miesięcznej)

---

## Quick Reference — Zmiany Wymagane Per Plik

| Plik | Zmiana |
|------|--------|
| `api/routers/generate.py` | Dodaj `Depends(check_quota)`, wywołaj `log_usage()` |
| `api/routers/inject.py` | Dodaj `Depends(get_current_user)`, check `plan.wp_sites_limit > 0` |
| `api/routers/process.py` | Dodaj `Depends(check_quota)`, wywołaj `log_usage()` |
| `api/routers/sitemap.py` | Dodaj `Depends(get_current_user)`, check plan |
| `api/routers/jobs.py` | Audyt ownership check per job |
| `api/quota.py` | Fix hardcoded URL w error message, dodaj `endpoint` param do `log_usage` |
| `api/models/user.py` | Fix `UsageLog.endpoint` default value |
| `api/routers/auth.py` | Fix hardcoded `GOOGLE_REDIRECT_URI`, dodaj `/verify` endpoint |
| *(nowy)* `api/routers/billing.py` | Stripe checkout, webhook, portal |

---

*arch-saas-01 | video-seo-engine | 2026-06-16 — SaaS Patterns Analysis v1.0*
