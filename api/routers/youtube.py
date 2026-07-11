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
from api.auth import get_current_user

router = APIRouter(prefix="/v1/youtube", tags=["youtube"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Nginx routes /v1 directly to the backend
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
    return {"authorization_url": auth_url}


@router.get("/oauth/callback")
async def youtube_oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    # 1. Weryfikuj state (CSRF)
    result = await db.execute(select(OAuthState).where(OAuthState.state_token == state))
    oauth_state = result.scalar_one_or_none()
    if not oauth_state or not oauth_state.is_valid():
        return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
    user_id = oauth_state.user_id
    # 2. Weryfikuj user
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
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
            return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
        token_data = token_resp.json()
        # 5. Pobierz dane kanalu
        channels_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        if channels_resp.status_code != 200:
            await db.rollback()
            return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
        items = channels_resp.json().get("items", [])
        if not items:
            return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
        channel_info = items[0]
        # 6. Sprawdz czy kanal juz istnieje (obsługa re-connect / unique constraint)
        existing_result = await db.execute(
            select(YouTubeChannel).where(
                YouTubeChannel.user_id == user_id,
                YouTubeChannel.youtube_channel_id == channel_info["id"]
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            # Kanal juz podlaczony — reaktywuj jesli nieaktywny, zaktualizuj token
            existing.is_active = True
            if token_data.get("refresh_token"):
                existing.refresh_token = token_data.get("refresh_token")
            await db.commit()
            return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=connected", status_code=302)
        # 7. Zapisz nowy kanal (setter szyfruje automatycznie)
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
            return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=error", status_code=302)
    return RedirectResponse(url="https://vse.impresjapr.pl/ustawienia?yt=connected", status_code=302)


@router.get("/channels")
async def list_user_channels(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(YouTubeChannel)
        .where(YouTubeChannel.user_id == current_user.id)
        .where(YouTubeChannel.is_active == True)
        .order_by(YouTubeChannel.created_at)
    )
    channels = result.scalars().all()
    # Zwracaj channel_id i channel_title — zgodnie z oczekiwaniami frontendu
    return [{"id": str(ch.id), "channel_id": ch.youtube_channel_id, "channel_title": ch.title} for ch in channels]


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
