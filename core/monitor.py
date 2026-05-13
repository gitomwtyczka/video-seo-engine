"""YouTube Channel Monitor — Faza 2 (MODE A: push).

Watches a YouTube channel for new videos and:
  1. Checks the local registry to prevent double-processing.
  2. Creates a WordPress draft with the video title + embed.
  3. Triggers core/generator.py to enrich the draft with SEO schema.
  4. Updates the registry with final status.

Usage (via CLI):
  vse watch --channel UC... --interval 3600 --dry-run

Environment variables:
  CHANNEL_ID        -- YouTube channel ID (UCxxx...)
  MONITOR_INTERVAL  -- polling interval in seconds (default: 3600)
  YT_API_KEY        -- YouTube Data API v3 key (required for get_latest_videos)
  WP_USER           -- WordPress username
  WP_APP_PASSWORD   -- WordPress Application Password
  WP_BASE_URL       -- e.g. https://prawy.pl

Dependencies:
  pip install requests python-dotenv
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests  # type: ignore

logger = logging.getLogger(__name__)

# Default registry directory (relative to CWD / project root)
REGISTRY_DIR = Path("registry")


# ============================================================
# REGISTRY — pre-flight check + update
# ============================================================

def check_registry(video_id: str, registry_dir: Path = REGISTRY_DIR) -> Optional[dict]:
    """Check if a video has already been processed.

    Args:
        video_id: YouTube video ID.
        registry_dir: Path to the registry directory.

    Returns:
        Registry record dict if found, None if not processed yet.
    """
    registry_path = registry_dir / f"{video_id}.json"
    if registry_path.exists():
        try:
            state = json.loads(registry_path.read_text(encoding="utf-8"))
            return state
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Registry read error for %s: %s", video_id, exc)
    return None


def update_registry(
    video_id: str,
    status: str,
    wp_post_id: Optional[int] = None,
    agent: str = "vse-architect-01",
    registry_dir: Path = REGISTRY_DIR,
) -> None:
    """Write or update a registry entry for a video.

    Args:
        video_id: YouTube video ID.
        status: One of 'pending', 'injected', 'failed', 'skipped'.
        wp_post_id: WordPress post ID (if created/updated).
        agent: Agent callsign that processed the video.
        registry_dir: Path to the registry directory.
    """
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / f"{video_id}.json"

    record = {
        "video_id": video_id,
        "status": status,
        "wp_post_id": wp_post_id,
        "injected_at": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
    }
    registry_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Registry updated: %s -> %s (WP#%s)", video_id, status, wp_post_id)


def is_already_processed(video_id: str, registry_dir: Path = REGISTRY_DIR) -> bool:
    """Return True if video is in registry with status injected or pending.

    This is the pre-flight check to prevent double-injection.

    Args:
        video_id: YouTube video ID.
        registry_dir: Path to the registry directory.

    Returns:
        True if video should be skipped.
    """
    state = check_registry(video_id, registry_dir)
    if state and state.get("status") in ("injected", "pending"):
        logger.warning(
            "SKIP %s -- already in registry (%s)", video_id, state["status"]
        )
        return True
    return False


# ============================================================
# YOUTUBE DATA API v3 — new video discovery
# ============================================================

def get_latest_videos(
    channel_id: str,
    yt_api_key: str,
    since: Optional[datetime] = None,
    max_results: int = 10,
) -> list[dict]:
    """Fetch the latest videos from a YouTube channel.

    Uses YouTube Data API v3 search.list endpoint.

    Args:
        channel_id: YouTube channel ID (UCxxx...).
        yt_api_key: YouTube Data API v3 key.
        since: Only return videos published after this datetime.
            If None, returns the most recent max_results videos.
        max_results: Maximum number of results to return (max 50).

    Returns:
        List of dicts with keys: video_id, title, published_at, description.

    Raises:
        requests.HTTPError: On YouTube API errors.
    """
    params: dict = {
        "part": "snippet",
        "channelId": channel_id,
        "order": "date",
        "type": "video",
        "maxResults": min(max_results, 50),
        "key": yt_api_key,
    }
    if since:
        params["publishedAfter"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = "https://www.googleapis.com/youtube/v3/search"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    videos = []
    for item in data.get("items", []):
        video_id = item["id"].get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        videos.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "description": snippet.get("description", ""),
            "thumbnail_url": (
                snippet.get("thumbnails", {})
                .get("maxres", snippet.get("thumbnails", {}).get("high", {}))
                .get("url", f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg")
            ),
        })

    logger.info(
        "YouTube API: found %d videos from channel %s (since=%s)",
        len(videos), channel_id, since.isoformat() if since else "any",
    )
    return videos


# ============================================================
# WORDPRESS — create draft post
# ============================================================

def create_draft(
    video_id: str,
    post_title: str,
    yt_embed_url: str,
    wp_base_url: str,
    wp_user: str,
    wp_app_pass: str,
    dry_run: bool = False,
) -> Optional[int]:
    """Create a WordPress draft post with YouTube embed.

    Args:
        video_id: YouTube video ID (for embed URL construction).
        post_title: Post title (from YouTube snippet.title).
        yt_embed_url: YouTube embed URL (https://www.youtube.com/embed/{id}).
        wp_base_url: WordPress site URL.
        wp_user: WordPress username.
        wp_app_pass: WordPress Application Password.
        dry_run: If True, log the action without making API calls.

    Returns:
        WordPress post ID (int) if created, None if dry_run or failed.
    """
    embed_block = (
        f'<!-- wp:embed {{"url":"https://www.youtube.com/watch?v={video_id}",'
        f'"type":"video","providerNameSlug":"youtube"}} -->\n'
        f'<figure class="wp-block-embed is-type-video is-provider-youtube">'
        f'<div class="wp-block-embed__wrapper">\n'
        f'https://www.youtube.com/watch?v={video_id}\n'
        f'</div></figure>\n'
        f'<!-- /wp:embed -->'
    )

    payload = {
        "title": post_title,
        "content": embed_block,
        "status": "draft",
    }

    if dry_run:
        logger.info(
            "DRY RUN -- would create draft: %r | YT:%s", post_title[:60], video_id
        )
        return None

    api_url = f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/posts"
    resp = requests.post(
        api_url,
        json=payload,
        auth=(wp_user, wp_app_pass),
        timeout=30,
    )
    resp.raise_for_status()
    post_data = resp.json()
    wp_id = post_data.get("id")
    link = post_data.get("link", "")
    logger.info("Draft created: WP#%s | %s", wp_id, link)
    return wp_id


# ============================================================
# GENERATE TRIGGER — call core/generator pipeline
# ============================================================

def trigger_generate(
    video_id: str,
    wp_id: int,
    post_title: str,
    api_key: str,
    subs_dir: str,
    seo_dir: str,
    dry_run: bool = False,
) -> bool:
    """Trigger SEO generation for a newly discovered video.

    Requires the VTT transcript to already exist in subs_dir.
    If VTT is missing, logs a warning and returns False.

    Args:
        video_id: YouTube video ID.
        wp_id: WordPress post ID for the draft.
        post_title: Post title.
        api_key: Gemini API key.
        subs_dir: Directory containing .vtt transcript files.
        seo_dir: Output directory for SEO JSON files.
        dry_run: If True, skip actual Gemini call.

    Returns:
        True if generation succeeded, False otherwise.
    """
    from core.generator import process_video  # type: ignore

    vtt_path = os.path.join(subs_dir, f"{video_id}.pl.vtt")
    if not os.path.exists(vtt_path):
        logger.warning(
            "SKIP generate for %s -- VTT not found: %s "
            "(run 'vse fetch --video %s' first)",
            video_id, vtt_path, video_id,
        )
        return False

    if dry_run:
        logger.info("DRY RUN -- would generate SEO for %s (WP#%s)", video_id, wp_id)
        return True

    try:
        process_video(
            youtube_id=video_id,
            wp_id=wp_id,
            post_title=post_title,
            yt_url=f"https://www.youtube.com/watch?v={video_id}",
            vtt_path=vtt_path,
            api_key=api_key,
            out_dir=seo_dir,
        )
        logger.info("Generate OK: %s -> %s/%s.json", video_id, seo_dir, video_id)
        return True
    except Exception as exc:
        logger.error("Generate FAIL for %s: %s", video_id, exc)
        return False


# ============================================================
# WATCH LOOP — main monitor entry point
# ============================================================

def watch(
    channel_id: str,
    yt_api_key: str,
    wp_base_url: str,
    wp_user: str,
    wp_app_pass: str,
    gemini_api_key: str,
    subs_dir: str,
    seo_dir: str,
    interval: int = 3600,
    registry_dir: Path = REGISTRY_DIR,
    dry_run: bool = False,
    run_once: bool = False,
) -> None:
    """Main watch loop — poll YouTube channel and process new videos.

    Args:
        channel_id: YouTube channel ID.
        yt_api_key: YouTube Data API v3 key.
        wp_base_url: WordPress site URL.
        wp_user: WordPress username.
        wp_app_pass: WordPress Application Password.
        gemini_api_key: Gemini API key for SEO generation.
        subs_dir: Directory with .vtt transcript files.
        seo_dir: Output directory for SEO JSON results.
        interval: Polling interval in seconds (default: 3600 = 1h).
        registry_dir: Path to the registry directory.
        dry_run: If True, no actual WP or Gemini calls.
        run_once: If True, poll once and exit (useful for cron/CI).
    """
    logger.info(
        "Monitor starting | channel=%s | interval=%ds | dry_run=%s",
        channel_id, interval, dry_run,
    )

    last_check: Optional[datetime] = None

    while True:
        now = datetime.now(timezone.utc)
        logger.info("Polling YouTube channel %s (since=%s)...", channel_id,
                    last_check.isoformat() if last_check else "any")

        try:
            videos = get_latest_videos(
                channel_id=channel_id,
                yt_api_key=yt_api_key,
                since=last_check,
                max_results=10,
            )
        except Exception as exc:
            logger.error("YouTube API error: %s -- will retry in %ds", exc, interval)
            if run_once:
                break
            time.sleep(interval)
            continue

        new_count = 0
        for video in videos:
            vid_id = video["video_id"]
            title = video["title"]

            # PRE-FLIGHT CHECK — prevent double-injection
            if is_already_processed(vid_id, registry_dir):
                continue

            logger.info("New video: %s | %s", vid_id, title[:60])
            new_count += 1

            # Mark as pending immediately to prevent race conditions
            if not dry_run:
                update_registry(vid_id, "pending", agent="vse-architect-01",
                                registry_dir=registry_dir)

            # Create WP draft
            wp_id = create_draft(
                video_id=vid_id,
                post_title=title,
                yt_embed_url=f"https://www.youtube.com/embed/{vid_id}",
                wp_base_url=wp_base_url,
                wp_user=wp_user,
                wp_app_pass=wp_app_pass,
                dry_run=dry_run,
            )

            # Trigger SEO generation (requires VTT to be available)
            gen_ok = trigger_generate(
                video_id=vid_id,
                wp_id=wp_id or 0,
                post_title=title,
                api_key=gemini_api_key,
                subs_dir=subs_dir,
                seo_dir=seo_dir,
                dry_run=dry_run,
            )

            # Update registry with final status
            if not dry_run:
                final_status = "injected" if (wp_id and gen_ok) else "pending"
                update_registry(vid_id, final_status, wp_post_id=wp_id,
                                agent="vse-architect-01", registry_dir=registry_dir)

        logger.info(
            "Poll done: %d new videos processed | next check in %ds",
            new_count, interval,
        )
        last_check = now

        if run_once:
            break
        time.sleep(interval)
