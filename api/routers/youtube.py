import os
import logging
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
from api.models.request import YouTubePublishRequest, YouTubeChannelUpdate

logger = logging.getLogger(__name__)

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
    # Zwracaj channel_id, channel_title, footer_text — zgodnie z oczekiwaniami frontendu
    return [{"id": str(ch.id), "channel_id": ch.youtube_channel_id, "channel_title": ch.title, "footer_text": ch.footer_text} for ch in channels]


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


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: str,
    req: YouTubeChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Aktualizuje ustawienia kanału YT, np. footer_text."""
    result = await db.execute(
        select(YouTubeChannel)
        .where(YouTubeChannel.id == channel_id)
        .where(YouTubeChannel.user_id == current_user.id)
        .where(YouTubeChannel.is_active == True)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or access denied")
    
    channel.footer_text = req.footer_text
    await db.commit()
    return {"status": "updated"}


@router.post("/publish-description")
async def publish_youtube_description(
    req: YouTubePublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Aktualizuje metadane wideo na YouTube (opis, tytuł) dla wybranych kanałów.
    Endpoint niezalezny od /v1/inject — WP i YT sa osobnymi akcjami.
    ROADMAP F2B: YouTube Publishing Scenariusz A — Immediate Publish
    """
    from api.core.youtube_publish import update_youtube_metadata, _get_channel
    from api.routers.inject import build_yt_description

    if not req.channel_ids:
        raise HTTPException(status_code=400, detail="channel_ids cannot be empty")
    if not req.video_id:
        raise HTTPException(status_code=400, detail="video_id is required")

    results = {}
    seo = req.schema_data

    for channel_id in req.channel_ids:
        if req.override_description:
            full_description = req.override_description
        else:
            # Pobierz footer_text z DB
            footer_text = ""
            ft_channel = await _get_channel(db, current_user.id, channel_id)
            if ft_channel:
                footer_text = ft_channel.footer_text or ""

            full_description = build_yt_description(
                body=seo.get("youtube_description_body") or seo.get("youtube_description_hook", ""),
                wp_url=req.wp_article_url or "",
                mid_cta=seo.get("youtube_mid_cta", ""),
                chapters=seo.get("resolved_chapters") or seo.get("chapters", []),
                credits=seo.get("youtube_credits", {}),
                footer_text=footer_text,
                hashtags=seo.get("youtube_hashtags", []),
                youtube_id=req.video_id,
                site_url="",
            )

        # Uzywamy zaktualizowanego opisu i tytulu dla tego kanalu
        res = await update_youtube_metadata(
            db=db,
            user_id=current_user.id,
            channel_ids=[channel_id],
            video_id=req.video_id,
            new_description=full_description,
            new_title=seo.get("yt_title") or seo.get("post_title"),
            publish_at=req.publish_at,
            privacy_status=req.privacy_status,
        )
        results.update(res)

    return {"results": results, "video_id": req.video_id}


@router.get("/channels/{channel_id}/playlists")
async def get_channel_playlists(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Zwraca listę playlist kanału YouTube."""
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from api.core.youtube_publish import _get_channel, _build_credentials, _save_refreshed_token

    # Pobierz kanał z DB
    channel = await _get_channel(db, current_user.id, channel_id)
    if not channel and channel_id.isdigit():
        result = await db.execute(
            select(YouTubeChannel).where(
                YouTubeChannel.user_id == current_user.id,
                YouTubeChannel.id == int(channel_id),
                YouTubeChannel.is_active == True,
            )
        )
        channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or access denied")

    try:
        creds = _build_credentials(channel)
        if not creds.valid:
            creds.refresh(Request())
            await _save_refreshed_token(db, channel, creds)

        youtube = build("youtube", "v3", credentials=creds)
        yt_channel_id = channel.youtube_channel_id

        resp = youtube.playlists().list(
            part="snippet",
            channelId=yt_channel_id,
            maxResults=50,
        ).execute()

        playlists = []
        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            thumbnails = snippet.get("thumbnails", {})
            thumb_url = (
                thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
                or thumbnails.get("high", {}).get("url")
                or ""
            )
            playlists.append({
                "id": item.get("id"),
                "title": snippet.get("title", ""),
                "thumbnail": thumb_url,
            })

        return playlists
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching playlists for channel %s: %s", channel_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlists: {str(e)}")
