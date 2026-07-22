# api/core/youtube_publish.py
# ROADMAP F2B: Serwis YouTube videos.update — Scenariusz A (Immediate Publish)
# Wywoływany przez inject.py po udanym WP inject, gdy yt_channel_ids niepuste
# Patrz: docs/ARCHITECTURE_decisions.md ADR-11, ADR-12 (planowane)

import os
import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.models.youtube_channel import YouTubeChannel

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

async def _get_channel(db: AsyncSession, user_id: int, channel_id: str) -> YouTubeChannel | None:
    result = await db.execute(
        select(YouTubeChannel).where(
            YouTubeChannel.user_id == user_id,
            YouTubeChannel.youtube_channel_id == channel_id,
            YouTubeChannel.is_active == True
        )
    )
    return result.scalar_one_or_none()

def _build_credentials(channel: YouTubeChannel) -> Credentials:
    # Scope musi byc identyczny jak w OAuth flow (youtube.py YT_SCOPE)
    return Credentials(
        token=None,
        refresh_token=channel.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
    )

async def _save_refreshed_token(db: AsyncSession, channel: YouTubeChannel, creds: Credentials):
    if creds.refresh_token and creds.refresh_token != channel.refresh_token:
        channel.refresh_token = creds.refresh_token
        await db.commit()

async def update_youtube_metadata(
    db: AsyncSession,
    user_id: int,
    channel_ids: list[str],
    video_id: str,
    new_description: str,
    new_title: str | None = None,
) -> dict:
    """
    Aktualizuje metadane wideo na YouTube dla każdego z podanych kanałów.
    Zwraca dict: {channel_id: "ok" | "error: <msg>"}
    """
    results = {}
    for channel_id in channel_ids:
        try:
            # 1. Pobierz token z DB (weryfikacja user_id ownership)
            channel = await _get_channel(db, user_id, channel_id)
            if not channel:
                results[channel_id] = "error: channel not found or access denied"
                continue

            # 2. Odśwież token jeśli wygasł / wymuś uzyskanie access tokena z refresh tokena
            creds = _build_credentials(channel)
            if not creds.valid:
                creds.refresh(Request())
                await _save_refreshed_token(db, channel, creds)

            # 3. Wywołaj videos.update
            youtube = build("youtube", "v3", credentials=creds)
            
            # Najpierw pobierz snippet, bo videos.update wymaga zachowania categoryId i title.
            video_response = youtube.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if not video_response.get("items"):
                results[channel_id] = "error: video not found"
                continue
                
            snippet = video_response["items"][0]["snippet"]
            
            # Zaktualizuj opis
            snippet["description"] = new_description
            
            # Zaktualizuj tytuł jeśli podano
            if new_title:
                snippet["title"] = new_title
            
            # API Update request
            youtube.videos().update(
                part="snippet",
                body={
                    "id": video_id,
                    "snippet": snippet
                }
            ).execute()
            
            results[channel_id] = "ok"

        except Exception as e:
            logger.error("Error updating YT metadata for channel %s: %s", channel_id, e)
            results[channel_id] = f"error: {str(e)}"

    return results
