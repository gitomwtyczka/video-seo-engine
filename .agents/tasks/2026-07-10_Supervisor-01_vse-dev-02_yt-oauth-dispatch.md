# VSE — DISPATCH: YouTube OAuth Integration — Plan Finalny
**[Supervisor 01 | sonic-void 10.07.2026 21:38]**
**Dla:** vse-dev-02, vse-strateg-01
**Status decyzji:** ZAMKNIĘTE — GO do wdrożenia

---

## DECYZJE ZATWIERDZONE

| # | Decyzja | Wybór |
|---|---------|-------|
| D1 | Storage dla OAuthState | PostgreSQL (zero nowych zaleznosci) |
| D2 | Model kanalow YT | Full multi-channel + multi-send (jeden film wiele kanalow) |
| D3 | Google Login vs YT OAuth | Jeden unified flow — ale NIE w tym sprincie |

---

## STAN REPOZYTORIUM — ALARM

**Revert brudnego commitu NIE jest potwierdzony w historii git.**

Ostatnie commity na main sprawdzone przez Supervisora:
- 8db199d — report: vse-strateg-01 yt-integration-review
- 9ba68cd — update heartbeat [vse-dev-02]
- ffe25ab — Zaktualizowany dispatch YT z WpPortal
- 439808e — include youtube router in main.py [vse-dev-01]
- 800874  — add youtube router [vse-dev-01]
- 430dec9 — add youtubechannel to models init [vse-dev-01]
- fedc389 — add youtube_channels relation to User [vse-dev-01]
- d4a192c — add youtube_channel model [vse-dev-01]

**Brak commitu z revert. Kod z niezabezpieczonym refresh_token siedzi na main.**

Etap 0 obowiazkowy przed startem Etapu 1.

---

## PLAN: Etap 0 -> Etap 1 -> [Etap 2 rownoleg z Etap 3] -> staging -> prod

---

## ETAP 0 — Weryfikacja stanu repo (15 min)
Kto: dev-02
Warunek startu: natychmiast

Sprawdz na branchu main:
```
git log --oneline -15
git show HEAD:api/routers/youtube.py
```

Sprawdz czy plik zawiera:
1. refresh_token = Column(Text, nullable=True)  <-- niebezpieczne
2. youtube.readonly  <-- bledny scope
3. brak select(OAuthState) w callbacku  <-- brak CSRF ochrony

Wynik raportu:
- youtube.py na main: [TAK/NIE zawiera niezabezpieczony kod]
- Revert wykonany: [TAK/NIE]
- SHA aktualnego HEAD: [sha]

Jesli kod niezabezpieczony: NIE ruszac srodowiska prod do zakonczenia Etapu 1.

---

## ETAP 1 — Security Hardening (90 min)
Kto: dev-02
Warunek startu: po raporcie z Etapu 0
Blokuje merge na prod: TAK

### 1.1 — Nowy model OAuthState

Utwórz plik api/models/oauth_state.py:

```python
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from api.db import Base

class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    state_token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    @staticmethod
    def create_for_user(user_id):
        return OAuthState(
            user_id=user_id,
            state_token=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
        )

    def is_valid(self):
        return datetime.now(timezone.utc) < self.expires_at
```

Zarejestruj w api/models/__init__.py:
```python
from api.models.oauth_state import OAuthState
```

Alembic:
```bash
alembic revision --autogenerate -m "add oauth_states table"
alembic upgrade head
```

Cleanup (w lifespan api/main.py):
```python
await db.execute(delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc)))
await db.commit()
```

### 1.2 — Szyfrowanie refresh_token (Fernet)

Utwórz api/services/crypto.py:
```python
import os
from cryptography.fernet import Fernet

def _get_fernet():
    key = os.getenv("FERNET_SECRET_KEY")
    if not key:
        raise RuntimeError("FERNET_SECRET_KEY not set")
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_token(plaintext):
    return _get_fernet().encrypt(plaintext.encode())

def decrypt_token(ciphertext):
    return _get_fernet().decrypt(ciphertext).decode()
```

Zmodyfikuj api/models/youtube_channel.py — zmien kolumne i dodaj property:
```python
# USUN: refresh_token = Column(Text, nullable=True)
# DODAJ:
refresh_token_encrypted = Column(LargeBinary, nullable=True)

from api.services.crypto import encrypt_token, decrypt_token

@property
def refresh_token(self):
    if self.refresh_token_encrypted is None:
        return None
    return decrypt_token(self.refresh_token_encrypted)

@refresh_token.setter
def refresh_token(self, value):
    self.refresh_token_encrypted = encrypt_token(value) if value else None
```

Dodaj do .env i .env.api.example:
```
# Wygeneruj: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_SECRET_KEY=<wygenerowany_klucz>
```

Alembic:
```bash
alembic revision --autogenerate -m "encrypt refresh_token in youtube_channels"
alembic upgrade head
```

### 1.3 — UniqueConstraint na kanale

W klasie YouTubeChannel:
```python
from sqlalchemy import UniqueConstraint
__table_args__ = (
    UniqueConstraint("user_id", "youtube_channel_id", name="uq_user_yt_channel"),
)
```

### 1.4 — Poprawiony router (scope + state CSRF + weryfikacja user)

Zastap calosc api/routers/youtube.py:
```python
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.db import get_db
from api.models.user import User
from api.models.youtube_channel import YouTubeChannel
from api.models.oauth_state import OAuthState
from api.middleware.auth import get_current_user

router = APIRouter(prefix="/v1/youtube", tags=["youtube"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("YOUTUBE_OAUTH_REDIRECT_URI", "https://vse.impresjapr.pl/v1/youtube/oauth/callback")

# WAZNE: force-ssl = najwezszy scope z prawem zapisu (videos.update)
# NIE uzywaj youtube.readonly — pipeline inject nie zadziala
YT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


@router.get("/oauth/login")
async def youtube_oauth_login(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    oauth_state = OAuthState.create_for_user(current_user.id)
    db.add(oauth_state)
    await db.commit()
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&scope={YT_SCOPE}&access_type=offline&prompt=consent"
        f"&state={oauth_state.state_token}"
    )
    return RedirectResponse(auth_url)


@router.get("/oauth/callback")
async def youtube_oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    # 1. Weryfikuj state (CSRF)
    result = await db.execute(select(OAuthState).where(OAuthState.state_token == state))
    oauth_state = result.scalar_one_or_none()
    if not oauth_state or not oauth_state.is_valid():
        raise HTTPException(status_code=403, detail="Invalid or expired OAuth state.")
    user_id = oauth_state.user_id
    # 2. Weryfikuj user
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    # 3. Zuzyt state (jednorazowy)
    await db.delete(oauth_state)
    # 4. Wymiana code na tokeny
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
        })
        if token_resp.status_code != 200:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Token exchange failed")
        token_data = token_resp.json()
        # 5. Pobierz dane kanalu
        channels_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        if channels_resp.status_code != 200:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Failed to fetch channel info")
        items = channels_resp.json().get("items", [])
        if not items:
            raise HTTPException(status_code=404, detail="No YouTube channel found")
        channel_info = items[0]
        # 6. Zapisz kanal (setter szyfruje automatycznie)
        channel = YouTubeChannel(
            user_id=user_id,
            youtube_channel_id=channel_info["id"],
            title=channel_info["snippet"]["title"],
        )
        channel.refresh_token = token_data.get("refresh_token")
        db.add(channel)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Channel already connected")
    return {"status": "ok", "channel_id": channel_info["id"], "channel_title": channel_info["snippet"]["title"]}


@router.get("/channels")
async def list_user_channels(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(YouTubeChannel)
        .where(YouTubeChannel.user_id == current_user.id)
        .where(YouTubeChannel.is_active == True)
        .order_by(YouTubeChannel.created_at)
    )
    channels = result.scalars().all()
    return [{"id": str(ch.id), "youtube_channel_id": ch.youtube_channel_id, "title": ch.title} for ch in channels]


@router.delete("/channels/{channel_id}")
async def disconnect_channel(channel_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(YouTubeChannel).where(YouTubeChannel.id == channel_id).where(YouTubeChannel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or access denied")
    channel.is_active = False
    await db.commit()
    return {"status": "disconnected"}
```

Po Etapie 1 — raport: SHA + alembic OK + screenshot /docs

---

## ETAP 2 — Pipeline Refactor: jeden strzal YT + multi-send + fallback (60 min)
Kto: dev-02
Warunek startu: Etap 1 zakończony

Zmien logike w api/services/inject_service.py:
```python
async def inject_with_yt_crosslink(video_id, wp_portal, yt_channel_ids, db):
    seo_payload = await generate_seo_payload(video_id)
    post_url, wp_success, wp_error_msg = None, False, None
    try:
        post_url = await inject_to_wordpress(seo_payload, wp_portal)
        wp_success = True
    except Exception as e:
        wp_error_msg = str(e)
    if post_url:
        seo_payload["description"] += f"\n\nArtykal: {post_url}"
    yt_results = []
    for channel_uuid in yt_channel_ids:
        channel = await get_channel_with_token(channel_uuid, db)
        if not channel:
            yt_results.append({"channel_id": channel_uuid, "status": "error", "detail": "not found"})
            continue
        try:
            access_token = await refresh_yt_access_token(channel.refresh_token)
            await update_youtube_video(video_id, seo_payload, access_token)
            yt_results.append({"channel_id": channel_uuid, "status": "ok"})
        except Exception as e:
            yt_results.append({"channel_id": channel_uuid, "status": "error", "detail": str(e)})
    if wp_success and all(r["status"] == "ok" for r in yt_results):
        return {"status": "ok", "post_url": post_url, "yt_channels": yt_results}
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=207, content={
        "status": "partial",
        "wp": {"success": wp_success, "post_url": post_url, "error": wp_error_msg},
        "yt_channels": yt_results
    })
```

Endpoint /v1/inject przyjmuje:
```python
class InjectRequest(BaseModel):
    video_id: str
    portal_id: str
    yt_channel_ids: list[str] = []
```

Po Etapie 2: SHA + log z 1x videos.update per kanal + test z blednym WP URL

---

## ETAP 3 — UI: Multi-Channel Dropdown + Multi-Send (60 min)
Kto: dev-02 (front Next.js) — moze rownolegly z Etapem 2
Warunek startu: Etap 1 zakończony

W ustawieniach portalu dodaj sekcje z checkboxami kanalow YT.
Dane z GET /v1/youtube/channels.
Przycisk "Wysylij do N kanalow" aktywny gdy wybrano >=1.
Przycisk "+ Podepnij nowy kanal" redirect do /v1/youtube/oauth/login.

Po Etapie 3: screenshot dropdownu + przycisk Send

---

## UWAGA D3 — Unified Google+YT OAuth

NIE implementujemy w tym sprincie.
Ten sprint = YT OAuth tylko dla juz zalogowanych userow.
Unified flow = osobny dispatch po zamknieciu tego.
Dev-02 ma NIE laczyc tych dwoch flow.

---

## CHECKLIST ZAMKNIECIA

- [ ] Etap 0 — stan repo potwierdzony (SHA)
- [ ] Etap 1 — security fixes + alembic OK
- [ ] Etap 2 — pipeline refactor + testy
- [ ] Etap 3 — UI dropdown screenshot
- [ ] Deploy staging bez bledow
- [ ] Smoke test end-to-end

Raporty po kazdem etapie do: sonic-void/.agents/reports/inbox/

*[Supervisor 01 | sonic-void 10.07.2026 21:38]*