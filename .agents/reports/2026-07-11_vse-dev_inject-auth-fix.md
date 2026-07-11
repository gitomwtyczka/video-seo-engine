# Security Fix Report: POST /v1/inject Auth + User Isolation
**Agent:** vse-dev-inject-fix | **Data:** 2026-07-11 | **Status:** DONE ✅

## Co zostało naprawione

### Fix A — Dodanie autentykacji do endpointu

**PRZED:**
```python
from fastapi import APIRouter, HTTPException
# brak importu get_current_user, User

@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
    # brak weryfikacji użytkownika!
```

**PO:**
```python
from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from api.models.user import User

@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(
    req: InjectRequest,
    current_user: User = Depends(get_current_user),  # DODANE
) -> InjectResponse:
    # current_user.id dostępne do filtrowania
```

### Fix B — Dodanie user_id isolation do portal lookup

**PRZED:**
```python
portal = await db.get(WpPortal, uid)
# każdy zalogowany/niezalogowany mógł użyć cudzego portal_id!
```

**PO:**
```python
from sqlalchemy.future import select

result = await db.execute(
    select(WpPortal).where(
        WpPortal.id == uid,
        WpPortal.user_id == current_user.id,  # DODANE
    )
)
portal = result.scalar_one_or_none()
if portal:
    site_config_dict = { ... }
else:
    raise HTTPException(
        status_code=403,
        detail="Portal not found or access denied",  # 403 zamiast ValueError
    )
```

### Bonus fix — HTTPException propagation
Dodany `except HTTPException: raise` guard w bloku try/except, aby 403 nie było połykane przez nadrzedny except handler.

## Commit
- **SHA:** `7174fb1cdc847e4dfcbbc9941bb1e02d87e82427`
- **Wiadomość:** `security: add auth + user_id isolation to POST /v1/inject [vse-dev]`
- **Repo:** `gitomwtyczka/video-seo-engine` | **Branch:** `main`

## Weryfikacja GitHub MCP
Plik po commicie zweryfikowany przez `get_file_contents`:
- `from api.auth import get_current_user` ✅
- `current_user: User = Depends(get_current_user)` ✅
- `WpPortal.user_id == current_user.id` w query ✅
- Newlines poprawne (encoding base64 OK) ✅

## Deploy VPS
```
git pull: 429b274..7174fb1 Fast-forward
Docker build: DONE 3.6s (layers cached, tylko COPY . . rebuild)
Container vse-api: Started ✅
```

## Docker logs (health check)
```
INFO: Uvicorn running on http://0.0.0.0:8085
INFO: Application startup complete.
[INFO] api.main: VSE API v2.0.0 starting on port 8085
[INFO] api.main: Database tables verified/created
[INFO] api.main: Plans seeded
[INFO] api.main: Default LLM provider: claude
```
Brak ImportError, brak traceback, startup clean ✅

## Definition of Done
- [x] inject.py przeczytany z GitHub MCP
- [x] Fix Auth (Depends(get_current_user)) dodany
- [x] Fix user_id filter w portal lookup dodany
- [x] Commit na GitHub MCP z SHA
- [x] Weryfikacja pliku po commit
- [x] Deploy `docker compose up -d --build vse-api`
- [x] Docker logs — brak błędów
- [x] Raport dual-write

## Status
**DONE** — endpoint POST /v1/inject jest teraz chroniony JWT auth i user_id isolation.
