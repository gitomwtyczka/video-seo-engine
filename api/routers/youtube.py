"""Router: YouTube OAuth & Channel integration."""
import os
import urllib.parse
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx

from api.db import AsyncSessionLocal
from api.models.user import User
from api.models.youtube_channel import YouTubeChannel
from api.routers.auth import get_current_user

router = APIRouter(prefix="/v1/youtube", tags=["youtube"])
logger = logging.getLogger(__name__)

YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3001")


@router.get("/oauth/login")
async def youtube_oauth_login(user: User = Depends(get_current_user)):
    """Generate Google OAuth redirect URL for YouTube Channel linking."""
    if not YT_CLIENT_ID:
        raise HTTPException(status_code=500, detail="YouTube Client ID not configured")
        
    redirect_uri = f"{os.environ.get('API_URL', 'http://localhost:8085')}/v1/youtube/oauth/callback"
    
    params = {
        "client_id": YT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
        "access_type": "offline",
        "prompt": "consent",  # Force consent to ensure refresh_token is returned
        "state": str(user.id),  # Pass user ID via state
    }
    
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": url}


@router.get("/oauth/callback")
async def youtube_oauth_callback(code: str, state: str):
    """Callback for YouTube OAuth. Exchanges code for refresh_token and saves channel."""
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="YouTube OAuth not configured")
        
    redirect_uri = f"{os.environ.get('API_URL', 'http://localhost:8085')}/v1/youtube/oauth/callback"
    
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": YT_CLIENT_ID,
                "client_secret": YT_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
        if token_resp.status_code != 200:
            logger.error(f"Token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange token")
            
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token returned")
            
        # Get user's channels
        channels_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if channels_resp.status_code != 200:
            logger.error(f"Failed to fetch channels: {channels_resp.text}")
            raise HTTPException(status_code=400, detail="Failed to fetch channels")
            
        channels_data = channels_resp.json()
        items = channels_data.get("items", [])
        
        if not items:
            return RedirectResponse(f"{FRONTEND_URL}/dashboard?yt_error=no_channels")
            
        async with AsyncSessionLocal() as db:
            for item in items:
                channel_id = item["id"]
                title = item["snippet"]["title"]
                
                channel = await db.get(YouTubeChannel, channel_id)
                if not channel:
                    channel = YouTubeChannel(
                        id=channel_id,
                        user_id=state,
                        name=title,
                        refresh_token=refresh_token or "", 
                        footer_text="Subskrybuj kanał i zostaw łapkę w górę!"
                    )
                    db.add(channel)
                else:
                    if refresh_token:
                        channel.refresh_token = refresh_token
                    channel.name = title
                    channel.user_id = state
                    
            await db.commit()
            
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?yt_success=true")
