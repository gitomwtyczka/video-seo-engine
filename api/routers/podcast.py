"""
Podcast Router — VSE Podcast Publishing Module
Obsługuje wielokrotne show (Biblijny, Płużański, przyszłe)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import yaml
import os

router = APIRouter(prefix="/podcast", tags=["podcast"])

# Load podcast config from profile
def get_podcast_shows(profile: str = "prawy") -> dict:
    """Load podcast show configs from YAML profile."""
    profile_path = os.path.join(os.path.dirname(__file__), f"../../profiles/{profile}.yaml")
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    shows = {show["slug"]: show for show in data.get("podcast", {}).get("shows", [])}
    return shows


class PodcastLinkRequest(BaseModel):
    """Request to link MP3 to existing WP post (Phase 1 — post-VSE step)."""
    show_slug: str                  # e.g. 'prawy-biblijny'
    wp_post_id: int                 # WP post ID (from VSE inject response)
    episode: int                    # episode number
    mp3_filename: str               # e.g. 'prawy-biblijny-2026-08-15.mp3'
    duration: Optional[str] = None  # e.g. '2:53'
    profile: str = "prawy"


class PodcastLinkResponse(BaseModel):
    success: bool
    show_slug: str
    wp_post_id: int
    episode: int
    mp3_filename: str
    rss_url: str
    message: str


@router.post("/link-mp3", response_model=PodcastLinkResponse)
async def link_mp3_to_post(
    req: PodcastLinkRequest,
    # auth: dict = Depends(get_current_user)  # TODO: add auth
):
    """
    Phase 1: Link existing MP3 to a WordPress post.
    Sets podcast_show taxonomy and meta (episode, mp3_file, duration).
    Called after VSE creates the post.
    """
    shows = get_podcast_shows(req.profile)
    if req.show_slug not in shows:
        raise HTTPException(404, f"Show '{req.show_slug}' not found in profile '{req.profile}'")
    
    show = shows[req.show_slug]
    
    # TODO: implement WP REST API calls:
    # 1. POST /wp/v2/posts/{wp_post_id} with podcast_show taxonomy
    # 2. POST /wp/v2/posts/{wp_post_id} meta fields
    # For now return placeholder
    return PodcastLinkResponse(
        success=True,
        show_slug=req.show_slug,
        wp_post_id=req.wp_post_id,
        episode=req.episode,
        mp3_filename=req.mp3_filename,
        rss_url=show["rss_url"],
        message=f"Linked EP{req.episode} to post {req.wp_post_id} (implementation pending)"
    )


@router.get("/shows")
async def list_shows(profile: str = "prawy"):
    """List all configured podcast shows for a profile."""
    shows = get_podcast_shows(profile)
    return {"profile": profile, "shows": list(shows.values())}


@router.get("/shows/{show_slug}")
async def get_show(show_slug: str, profile: str = "prawy"):
    """Get podcast show config."""
    shows = get_podcast_shows(profile)
    if show_slug not in shows:
        raise HTTPException(404, f"Show '{show_slug}' not found")
    return shows[show_slug]
