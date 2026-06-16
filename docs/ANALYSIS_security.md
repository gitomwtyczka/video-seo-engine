# ANALYSIS_security.md — Video SEO Engine

> **Analityk:** `arch-sec-01` | **Data:** 2026-06-16 | **Standard:** OWASP 2024, FastAPI Security Best Practices
> **Zakres:** Kod produkcyjny — api/auth.py, api/routers/auth.py, api/routers/admin.py, api/models/user.py, api/main.py, web/route.ts

---

## Metodologia

Każde znalezisko zawiera:
- **Znalezisko** — opis podatności lub słabości
- **Lokalizacja** — plik + linia / kontekst
- **Ryzyko** — `Critical` / `High` / `Medium` / `Low`
- **Rekomendacja** — konkretny fix lub standard do wdrożenia

---

## 1. JWT — Strategia Tokenów

### SEC-001 — Domyślny secret key w kodzie produkcyjnym

**Znalezisko:**
```python
# api/auth.py
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
```
Jeśli `JWT_SECRET_KEY` nie zostanie ustawiony w `.env`, aplikacja startuje z kluczem literalnym `"CHANGE_ME_IN_PRODUCTION"`. Każdy może podpisać dowolny JWT tym kluczem.

**Ryzyko:** 🔴 **CRITICAL**

**Rekomendacja:**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is required. Set this env var before starting.")
```
Dodaj sprawdzenie przy starcie w `startup_event()` — fail fast, nie silent default.

---

### SEC-002 — Brak rotacji refresh tokenów (Token Rotation)

**Znalezisko:** Endpoint `POST /v1/auth/refresh` wydaje nową parę tokenów ale **nie unieważnia starego refresh tokenu**. Stary token pozostaje ważny przez 30 dni.

```python
# api/routers/auth.py — refresh_token()
return TokenResponse(
    access_token=create_access_token(str(user.id), user.email),
    refresh_token=create_refresh_token(str(user.id))  # stary token nadal działa!
)
```

**Ryzyko:** 🟠 **High** — token skradziony przez XSS/MITM może być używany przez atakującego równolegle z oryginalnym userem przez 30 dni bez wykrycia.

**Rekomendacja:** Implementacja jednej z opcji:
1. **Redis token store** — przechowuj `jti` (JWT ID) valid refresh tokenów, invaliduj przy rotacji
2. **DB token store** — tabela `refresh_tokens(token_hash, user_id, expires_at, revoked)`, unieważniaj stary przy wydaniu nowego
3. **Minimum:** Dodaj `jti` claim do każdego refresh tokenu, prowadź blacklistę w Redis z TTL = 30 dni

---

### SEC-003 — Brak rewokacji tokenów (Token Revocation)

**Znalezisko:** Nie istnieje mechanizm unieważnienia aktywnych tokenów. Scenariusz: admin dezaktywuje konto (`is_active=False`), ale aktywny access token pozostaje ważny przez 15 minut.

**Ryzyko:** 🟠 **High** — w SaaS kluczowe przy: chargeback fraud, zawieszeniu konta, zmianie hasła.

**Rekomendacja:**
- Endpoint `POST /v1/auth/logout` unieważniający refresh token w DB
- Przy zmianie hasła lub dezaktywacji konta: flush tokenów użytkownika
- Alternatywa: skróć access token do 5 minut, refresh do 7 dni (typowe dla produkcji)

---

### SEC-004 — Algorytm HS256 — współdzielony sekret

**Znalezisko:** JWT używa `HS256` (HMAC-SHA256) — algorytm z jednym kluczem do podpisywania i weryfikacji.

**Ryzyko:** 🟡 **Medium** — dla single-service OK. Staje się problemem gdy:
- Wiele serwisów musi weryfikować tokeny (bez dostępu do sekretu)
- W przyszłości pojawi się mikroserwisowa architektura

**Rekomendacja:** Rozważ migrację do `RS256` (asymetryczny) jeśli planowane jest rozdzielenie auth service od API. Na razie akceptowalne — dokumentuj jako tech debt.

---

## 2. OWASP Top 10 — Przegląd Kodu

### SEC-005 — SQL Injection: BRAK RYZYKA (SQLAlchemy ORM)

**Znalezisko:** Wszystkie zapytania bazodanowe używają SQLAlchemy async ORM z parametryzowanymi zapytaniami:
```python
result = await db.execute(select(User).where(User.email == payload.email))
```
Wyjątek: `_seed_plans()` używa `text()` z `:named_params` — parametryzowane, bezpieczne.

**Ryzyko:** 🟢 **Low** — standardowe użycie ORM chroni przed SQL injection.

**Rekomendacja:** Utrzymaj wzorzec ORM. Każde surowe `text()` query musi używać named params — nigdy f-string.

---

### SEC-006 — XSS: Wyciek tokenów przez URL (Google OAuth Callback)

**Znalezisko:** Endpoint `/v1/auth/google/callback` przekierowuje z tokenami w query string:
```python
# api/routers/auth.py
return RedirectResponse(
    f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
)
```

**Ryzyko:** 🔴 **CRITICAL** — tokeny w URL trafiają do:
- Browser history (widoczne przez `history.back()`)
- Serwer logs (Cloudflare, nginx, VPS access logs)
- Referer header przy redirect do zewnętrznych zasobów (analytics, CDN)
- Dostępne przez `document.referrer` dla skryptów third-party

To jest **OWASP A02:2021 Cryptographic Failures** — sensitive data exposure.

**Rekomendacja:**
```python
# OPCJA 1: Kod jednorazowy (Authorization Code Exchange Pattern)
# Backend generuje one-time code (np. random UUID w Redis z TTL 60s)
# Frontend wymienia code → tokeny przez POST /v1/auth/exchange?code=
return RedirectResponse(f"{frontend_url}/auth/callback?code={one_time_code}")

# OPCJA 2: Sesja po stronie backendu
# Zapisz tokeny w zaszyfrowanej sesji server-side, zwróć session_id w httpOnly cookie

# OPCJA 3 (minimum): POST + httpOnly cookie
# Zamiast redirect, zrób POST z tokenami jako httpOnly cookie
response = RedirectResponse(frontend_url + "/dashboard")
response.set_cookie("access_token", access_token, httponly=True, secure=True, samesite="lax")
response.set_cookie("refresh_token", refresh_token, httponly=True, secure=True, samesite="lax")
return response
```

---

### SEC-007 — IDOR: Brak weryfikacji własności zasobów w job endpoints

**Znalezisko:** Endpoint `GET /v1/jobs/{id}` — jeśli nie weryfikuje `user_id == current_user.id`, użytkownik A może odpytać job użytkownika B przez zgadywanie UUID.

**Lokalizacja:** `api/routers/jobs.py` — nie analizowany bezpośrednio, ale wzorzec IDOR w UUID-based routing jest typowy.

**Ryzyko:** 🟠 **High** — transcript_jobs mogą zawierać wrażliwe transkrypty, URL filmów klientów.

**Rekomendacja:**
```python
# Zawsze filtruj po user_id:
result = await db.execute(
    select(TranscriptJob)
    .where(TranscriptJob.id == job_id)
    .where(TranscriptJob.user_id == current_user.id)  # IDOR protection
)
```

---

### SEC-008 — Mass Assignment: Pydantic models chronią API

**Znalezisko:** API używa dedykowanych Pydantic input models (`RegisterRequest`, `LoginRequest`, etc.) — brak mass assignment. Pola wrażliwe (`is_admin`, `plan_id`) nie są częścią żadnego publicznego modelu wejścia.

**Ryzyko:** 🟢 **Low** — wzorzec Pydantic poprawnie zastosowany.

**Rekomendacja:** Utrzymaj separację modeli input/output. Nigdy nie używaj `**request.dict()` bezpośrednio do inicjalizacji ORM obiektów.

---

### SEC-009 — Brak walidacji siły hasła (Password Policy)

**Znalezisko:**
```python
# api/routers/auth.py
if len(payload.password) < 8:
    raise HTTPException(422, "Password must be at least 8 characters")
```
Minimalny warunek — brak sprawdzenia: cyfry, znaki specjalne, popularne hasła.

**Ryzyko:** 🟡 **Medium** — SaaS z tysiącami userów to target brute-force i credential stuffing.

**Rekomendacja:**
```python
import re
PASSWORD_PATTERN = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{10,}$')
if not PASSWORD_PATTERN.match(payload.password):
    raise HTTPException(422, "Password must be 10+ chars, contain uppercase, digit, special char")
```
Alternatywnie: biblioteka `zxcvbn` do oceny entropii hasła.

---

## 3. Secrets Management

### SEC-010 — .env file jako jedyne zabezpieczenie sekretów

**Znalezisko:** Wszystkie sekrety (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `WP_APP_PASSWORD`) są w pliku `.env` na VPS. `.env.example` jest w repozytorium — w porządku. Ale `.env` produkcyjny nie ma żadnej dodatkowej warstwy szyfrowania.

**Ryzyko:** 🟠 **High** — jeden kompromis VPS = wyciek wszystkich sekretów:
- ANTHROPIC_API_KEY → koszty API
- POSTGRES_PASSWORD → bezpośredni dostęp do bazy
- WP_APP_PASSWORD → zapis do portali WordPress

**Rekomendacja — priorytetyzowane:**
1. **Minimum (teraz):** Upewnij się że `.env` ma `chmod 600` i należy do właściwego użytkownika
2. **Krótkoterminowe:** Docker secrets zamiast env vars dla `POSTGRES_PASSWORD` i `JWT_SECRET_KEY`:
   ```yaml
   # docker-compose.vse.yml
   secrets:
     jwt_secret:
       file: ./secrets/jwt_secret.txt
   services:
     vse-api:
       secrets:
         - jwt_secret
   ```
3. **Docelowo (Faza 3):** Google Cloud Secret Manager lub HashiCorp Vault — szczególnie dla kluczy WP portali klientów (które dziś są przesyłane inline w requestach)

---

### SEC-011 — WP App Password przesyłany inline w każdym request

**Znalezisko:**
```python
# api/models/request.py
class SiteConfig(BaseModel):
    wp_base_url: str
    wp_user: str
    wp_app_password: str  # plaintext w body każdego /v1/inject i /v1/process
```

**Ryzyko:** 🟠 **High** dla SaaS:
- HTTPS chroni w tranzycie, ale hasła trafiają do logów FastAPI/nginx jeśli logowanie body jest włączone
- Brak możliwości rotacji hasła bez aktualizacji wszystkich klientów
- W przyszłości: WordPress credentials powinny być przechowywane per-user w bazie danych (zaszyfrowane at-rest)

**Rekomendacja:**
- Faza 2: Tabela `wp_sites(user_id, wp_base_url, wp_user, wp_app_password_enc)` z AES-256 encryption at rest
- `/v1/inject` przyjmuje `site_id` (UUID) zamiast raw credentials
- Eliminuje transmisję kredencjali w każdym request

---

## 4. Rate Limiting

### SEC-012 — Brak rate limiting na endpointach auth

**Znalezisko:** Endpointy `POST /v1/auth/login`, `POST /v1/auth/register`, `POST /v1/auth/refresh` nie mają rate limiting. Umożliwia:
- Brute-force ataki na hasła (brak lockout)
- Credential stuffing
- Account enumeration przez różne kody odpowiedzi

```python
# api/routers/auth.py
@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Brak: slowdown, lockout, rate limit
```

**Ryzyko:** 🔴 **CRITICAL** dla produkcji SaaS

**Rekomendacja:**
```python
# Opcja 1: slowapi (FastAPI rate limiter)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # 5 prób/minutę per IP
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    ...
```

Priorytet rate limitów:
| Endpoint | Limit | Uzasadnienie |
|---|---|---|
| `POST /v1/auth/login` | 5/min per IP | Brute-force protection |
| `POST /v1/auth/register` | 3/hour per IP | Account farming |
| `POST /v1/auth/refresh` | 10/min per token | Token stuffing |
| `POST /v1/generate` | Per quota (check_quota) | Już zaimplementowane |
| `POST /v1/auth/google/token-exchange` | 5/min per IP | Google token abuse |

---

### SEC-013 — Brak rate limiting na /v1/auth/google/token-exchange

**Znalezisko:** Nowy endpoint `POST /v1/auth/google/token-exchange` wywołuje zewnętrzne API Google (`https://oauth2.googleapis.com/tokeninfo`) przy **każdym** request bez throttlingu. Umożliwia:
- Flood zewnętrznego API Google (ich rate limits nas ukarzeją)
- DoS samego endpointu przez wymuszenie kosztownych zewnętrznych calls

**Ryzyko:** 🟠 **High**

**Rekomendacja:** Rate limiting jak powyżej + caching wyników tokeninfo (Redis, TTL = exp tokenu).

---

## 5. Input Validation

### SEC-014 — Brak walidacji video_url (URL injection)

**Znalezisko:**
```python
# api/models/request.py
class GenerateRequest(BaseModel):
    video_url: str  # brak walidacji — akceptuje dowolny string
```

Core fetcher może próbować fetchować dowolny URL jeśli nie ma walidacji w routerze. SSRF (Server-Side Request Forgery) ryzyko jeśli fetcher nie waliduje domeny.

**Ryzyko:** 🟠 **High** — SSRF umożliwia:
- Skanowanie wewnętrznej sieci Docker (np. `http://vse-postgres:5432`)
- Dostęp do metadata service AWS/GCP/Oracle Cloud

**Rekomendacja:**
```python
from pydantic import AnyUrl, validator
import re

YOUTUBE_PATTERN = re.compile(
    r'^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]{11}'
)

class GenerateRequest(BaseModel):
    video_url: str
    
    @validator('video_url')
    def validate_youtube_url(cls, v):
        if not YOUTUBE_PATTERN.match(v):
            raise ValueError('video_url must be a valid YouTube URL')
        return v
```

---

### SEC-015 — InjectRequest.schema_data — dowolny dict

**Znalezisko:**
```python
class InjectRequest(BaseModel):
    schema_data: dict  # brak walidacji struktury
```

Klient może przekazać dowolny JSON — brak weryfikacji że schema_data ma poprawną strukturę VideoObject. Może prowadzić do błędów downstream lub injection do WordPressa.

**Ryzyko:** 🟡 **Medium**

**Rekomendacja:** Dodaj typed Pydantic model dla `schema_data`:
```python
class SchemaData(BaseModel):
    video_object: dict
    clips: list = []
    faq: Optional[dict] = None
    meta_description: Optional[str] = None
    title: Optional[str] = None

class InjectRequest(BaseModel):
    schema_data: SchemaData
```

---

## 6. CORS Policy

### SEC-016 — CORS: Poprawna konfiguracja, ale localhost w produkcji

**Znalezisko:**
```python
# api/main.py
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3001"],  # localhost hardcoded!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`http://localhost:3001` jest hardcoded w kodzie produkcyjnym. Umożliwia lokalnemu serwerowi deweloperycznemu atakującego wykonywanie credentialed requests do produkcyjnego API.

**Ryzyko:** 🟡 **Medium**

**Rekomendacja:**
```python
# Env-based CORS origins
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "https://vse.impresjapr.pl")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],  # nie wildcard
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)
```
W `.env.development`: `ALLOWED_ORIGINS=https://vse.impresjapr.pl,http://localhost:3001`
W `.env.production`: `ALLOWED_ORIGINS=https://vse.impresjapr.pl`

---

### SEC-017 — allow_methods=["*"] i allow_headers=["*"]

**Znalezisko:** Wildcard w methods i headers jest zbyt permisywny — otwiera możliwości pre-flight bypass i header injection.

**Ryzyko:** 🟡 **Medium**

**Rekomendacja:** Ogranicz do konkretnych metod i headerów jak w SEC-016.

---

## 7. Admin Endpoints

### SEC-018 — Admin protection: get_current_admin jako dependency — wystarczające

**Znalezisko:**
```python
# api/auth.py
async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# api/routers/admin.py
@router.get("/users")
async def list_users(admin: User = Depends(get_current_admin), ...):
```

Mechanizm jest poprawny: get_current_admin wywołuje get_current_user (weryfikacja JWT + is_active) a następnie sprawdza is_admin. Wzorzec FastAPI dependency injection — bezpieczny.

**Ryzyko:** 🟢 **Low** — baseline poprawny.

**Rekomendacja:** Wzmocnienie:
1. **Audit log** — każda akcja admin powinna być logowana:
   ```python
   logger.warning(f"ADMIN_ACTION: {admin.email} changed plan {user.id}: {old_plan}→{payload.plan_id}")
   ```
2. **IP allowlist** dla `/v1/admin/*` — tylko z IP admina (nginx `allow` directive)
3. **Pagination limit** — `limit: int = 100` bez max cap → admin może pobrać unlimited data:
   ```python
   limit: int = Query(default=50, le=200)  # max 200
   ```

---

### SEC-019 — Admin: Brak dwuskładnikowego uwierzytelnienia

**Znalezisko:** Admin panel dostępny wyłącznie przez JWT + `is_admin` flag. Brak MFA/2FA.

**Ryzyko:** 🟠 **High** dla SaaS — kompromis konta admin = pełna kontrola nad planami wszystkich userów.

**Rekomendacja:**
- Faza 2: TOTP (Google Authenticator) jako dodatkowy factor dla kont `is_admin=True`
- Minimum teraz: Strong password policy + IP restriction w nginx

---

## 8. API Keys

### SEC-020 — API Keys: bcrypt hash — poprawne

**Znalezisko:**
```python
# api/models/user.py
class ApiKey(Base):
    key_hash = Column(String(255), nullable=False, unique=True)  # bcrypt hash
```

Architektura zakłada bcrypt hashing kluczy API — identycznie jak hasła. To jest poprawny wzorzec (analogiczny do GitHub PAT). Niemożliwe odwrócenie nawet przy wycieku bazy.

**Ryzyko:** 🟢 **Low** — architektura poprawna.

**Rekomendacja:** Sprawdź czy `api/routers/users.py` poprawnie tworzy i weryfikuje klucze:
1. Klucz pokazać userowi **jednorazowo** przy tworzeniu (plain text)
2. Przechowywać tylko `key_hash`
3. Przy weryfikacji: `bcrypt.checkpw(provided_key, stored_hash)`
4. Formatowanie klucza: prefix + random → `vse_prod_[random(32)]` (identyfikowalność w logach)

---

### SEC-021 — Brak rotacji i expiry dla API Keys

**Znalezisko:** Model `ApiKey` nie ma pola `expires_at`. Klucze API są wieczne (dopóki `is_active=True`).

**Ryzyko:** 🟡 **Medium** — skradziony klucz API pozostaje ważny bez limitu czasowego.

**Rekomendacja:**
```python
class ApiKey(Base):
    expires_at = Column(DateTime(timezone=True), nullable=True)  # None = no expiry
    last_used_at = Column(DateTime(timezone=True), nullable=True)  # już jest ✅
```
W `get_current_user` (lub osobna dependency dla API key auth): sprawdzaj `expires_at`.

---

## 9. Google OAuth — Token Storage Security

### SEC-022 — Google OAuth: Tokens w NextAuth JWT cookie — akceptowalne

**Znalezisko:**
```typescript
// web/src/app/api/auth/[...nextauth]/route.ts
async jwt({ token, user, account }) {
  token.accessToken = user.accessToken   // JWT cookie (NextAuth)
  token.refreshToken = user.refreshToken
}
```

NextAuth przechowuje tokeny w zaszyfrowanym JWT cookie (AES-256-GCM przez `NEXTAUTH_SECRET`). Cookie jest HttpOnly i Secure w produkcji.

**Ryzyko:** 🟢 **Low** — NextAuth domyślny mechanizm jest bezpieczny.

**Rekomendacja:** Upewnij się że `NEXTAUTH_SECRET` jest silny (min. 32 chars entropy):
```bash
openssl rand -base64 32  # generuj dla produkcji
```

---

### SEC-023 — Google OAuth Callback: Brak PKCE i state verification

**Znalezisko:**
```python
# api/routers/auth.py
@router.get("/google")
async def google_oauth_start():
    params = (
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        # Brak: &state= (CSRF protection)
        # Brak: &code_challenge= (PKCE)
    )
```

Brak `state` parametru w OAuth flow — podatność na **OAuth CSRF attack**.

**Ryzyko:** 🟠 **High**

**Rekomendacja:**
```python
import secrets
from fastapi import Response

@router.get("/google")
async def google_oauth_start(response: Response):
    state = secrets.token_urlsafe(32)
    # Zapisz state w HttpOnly cookie (lub Redis z TTL=600s)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, max_age=600)
    params = (
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        f"&state={state}"  # CSRF protection
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str, request: Request, ...):
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid OAuth state — possible CSRF attack")
```

> **Uwaga:** Jeśli OAuth obsługiwane jest **wyłącznie przez NextAuth** (`GoogleProvider`), to NextAuth automatycznie implementuje state + PKCE. Backend `/v1/auth/google/callback` powinien być usunięty lub chroniony jeśli nie jest używany przez frontend.

---

### SEC-024 — Swagger /docs dostępny publicznie

**Znalezisko:**
```python
# api/main.py
app = FastAPI(
    docs_url="/docs",    # dostępny bez auth
    redoc_url="/redoc",  # dostępny bez auth
)
```

Swagger UI na produkcji ujawnia pełną mapę API, schematy requestów, przykłady — ułatwia ataki.

**Ryzyko:** 🟡 **Medium**

**Rekomendacja:**
```python
# Wyłącz w produkcji lub chroń:
import os
docs_url = "/docs" if os.getenv("ENABLE_SWAGGER", "false") == "true" else None

app = FastAPI(
    docs_url=docs_url,
    redoc_url=None,  # wyłącz w produkcji
)
```
Alternatywnie: nginx `location /docs { allow 10.0.0.0/8; deny all; }` — tylko VPN/localhost.

---

## Podsumowanie Ryzyk

| ID | Znalezisko | Ryzyko | Priorytet Fix |
|---|---|---|---|
| SEC-001 | Domyślny JWT secret `CHANGE_ME_IN_PRODUCTION` | 🔴 Critical | P0 — natychmiast |
| SEC-006 | Tokeny OAuth w URL (query string) | 🔴 Critical | P0 — natychmiast |
| SEC-012 | Brak rate limiting na /auth/login i /register | 🔴 Critical | P0 — przed scale-up |
| SEC-002 | Brak rotacji refresh tokenów | 🟠 High | P1 — sprint 1 |
| SEC-003 | Brak rewokacji tokenów (logout) | 🟠 High | P1 — sprint 1 |
| SEC-007 | IDOR w job endpoints | 🟠 High | P1 — sprint 1 |
| SEC-010 | Sekrety wyłącznie w .env | 🟠 High | P1 — sprint 1 |
| SEC-011 | WP credentials inline w requestach | 🟠 High | P2 — Faza 2 |
| SEC-013 | Brak rate limit na token-exchange | 🟠 High | P1 — sprint 1 |
| SEC-019 | Brak MFA dla admin accounts | 🟠 High | P2 — Faza 2 |
| SEC-023 | Brak OAuth state/CSRF w Google flow | 🟠 High | P1 — sprint 1 |
| SEC-009 | Słaba polityka haseł | 🟡 Medium | P2 |
| SEC-014 | Brak walidacji video_url (SSRF) | 🟠 High | P1 — sprint 1 |
| SEC-015 | schema_data — dowolny dict | 🟡 Medium | P2 |
| SEC-016 | localhost w CORS origins (produkcja) | 🟡 Medium | P1 |
| SEC-017 | CORS wildcard methods/headers | 🟡 Medium | P1 |
| SEC-021 | API Keys bez expiry | 🟡 Medium | P2 |
| SEC-024 | Swagger /docs publiczny | 🟡 Medium | P2 |
| SEC-004 | HS256 vs RS256 | 🟡 Medium | P3 — tech debt |
| SEC-005 | SQL Injection — ORM chroni | 🟢 Low | N/A — OK |
| SEC-008 | Mass Assignment — Pydantic chroni | 🟢 Low | N/A — OK |
| SEC-018 | Admin dependency — baseline OK | 🟢 Low | Wzmocnij audit log |
| SEC-020 | API Keys bcrypt hash — OK | 🟢 Low | N/A — OK |
| SEC-022 | OAuth tokens w NextAuth cookie — OK | 🟢 Low | N/A — OK |

---

## Plan Naprawczy — Priorytety

### 🚨 P0 — Natychmiastowe (przed scale-up do 1000 userów)

1. **SEC-001** — Fail-fast przy braku `JWT_SECRET_KEY`. Sprawdź czy w `.env` produkcyjnym jest ustawiony silny secret.
2. **SEC-006** — Zamień token-in-URL na one-time code lub httpOnly cookie w `/v1/auth/google/callback`.
3. **SEC-012** — Zainstaluj `slowapi` lub skonfiguruj rate limiting w nginx (`limit_req_zone`).

### 🟠 P1 — Sprint 1 (przed 1000 userów)

4. **SEC-023** — Dodaj `state` do Google OAuth flow (CSRF protection).
5. **SEC-007** — Audyt `api/routers/jobs.py` pod IDOR.
6. **SEC-013** — Rate limit na `/v1/auth/google/token-exchange`.
7. **SEC-014** — YouTube URL validator w `GenerateRequest`.
8. **SEC-016/017** — Env-based CORS origins + ograniczone metody.
9. **SEC-002/003** — Token revocation: tabela `refresh_tokens` lub Redis jti blacklist.

### 🟡 P2 — Faza 2

10. **SEC-011** — WP credentials w bazie danych (zaszyfrowane at-rest).
11. **SEC-019** — TOTP/MFA dla admin accounts.
12. **SEC-009** — Silna polityka haseł.
13. **SEC-024** — Wyłącz `/docs` w produkcji lub chroń przez nginx allow/deny.

---

## Pozytywne Obserwacje

✅ **bcrypt** — hasła i API keys hashowane bcrypt (poprawnie)
✅ **SQLAlchemy ORM** — brak SQL injection
✅ **Pydantic v2** — mass assignment protection
✅ **get_current_admin dependency** — poprawna architektura
✅ **is_active check** — dezaktywowane konta nie mogą się logować
✅ **HTTPS** — Cloudflare + nginx TLS
✅ **NextAuth httpOnly cookies** — tokeny niewidoczne dla JS
✅ **UUID primary keys** — trudniejsze do zgadnięcia niż sequential ints
✅ **quota.check_quota** — pipeline chroniony przez plan limits
✅ **Audit log podstawowy** — `UsageLog` rejestruje operacje

---

*arch-sec-01 | video-seo-engine | 2026-06-16 — Security Analysis v1.0*
*Standard: OWASP Top 10 2024, FastAPI Security Best Practices, NIST SP 800-63B*
