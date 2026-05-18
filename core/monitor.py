"""YouTube Channel Monitor — Faza 2 (MODE A: push).

Watches a YouTube channel for new videos and:
  1. Checks the local registry to prevent double-processing.
  2. Detects scheduled/premiere videos and sets WP publish time accordingly.
  3. Creates a WordPress draft or scheduled post with the video title + embed.
  4. Triggers core/generator.py to enrich the draft with SEO schema.
  5. Updates the registry with final status.

Usage (via CLI):
  vse watch --channel UC... --interval 3600 --dry-run

Environment variables:
  CHANNEL_ID          -- YouTube channel ID (UCxxx...)
  MONITOR_INTERVAL    -- polling interval in seconds (default: 3600)
  YT_API_KEY          -- YouTube Data API v3 key (required for get_latest_videos)
  WP_USER             -- WordPress username
  WP_APP_PASSWORD     -- WordPress Application Password
  WP_BASE_URL         -- e.g. https://prawy.pl
  PUBLISH_DELAY_MIN   -- Minimum WP publish delay after YT (minutes, default: 5)
  PUBLISH_DELAY_MAX   -- Maximum WP publish delay after YT (minutes, default: 37)

Dependencies:
  pip install requests python-dotenv
"""
import json
import logging
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests  # type: ignore

logger = logging.getLogger(__name__)

# Default registry directory (relative to CWD / project root)
REGISTRY_DIR = Path("registry")


# ============================================================
# SMART PUBLISH DELAY — variable timing to look natural
# ============================================================

def calculate_publish_delay(
    delay_min: int = 5,
    delay_max: int = 37,
) -> int:
    """Calculate a randomised publish delay in minutes.

    Base range: [delay_min, delay_max] (default 5-37 minutes).
    Occasionally (~15% of calls) produces an "outlier" that
    slightly exceeds the range in either direction, simulating
    organic editorial timing variation.

    Args:
        delay_min: Minimum delay in minutes (default: 5).
        delay_max: Maximum delay in minutes (default: 37).

    Returns:
        Delay in minutes (int), always >= 3.
    """
    base = random.randint(delay_min, delay_max)

    # ~15% chance of outlier
    if random.random() < 0.15:
        direction = random.choice([-1, 1])
        if direction == -1:
            # Publish slightly ahead of schedule (3-4 min before range)
            base = random.randint(max(3, delay_min - 4), delay_min - 1)
        else:
            # Publish somewhat later (slightly above range)
            base = random.randint(delay_max + 1, delay_max + 15)

    return max(3, base)


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
    extra: Optional[dict] = None,
) -> None:
    """Write or update a registry entry for a video.

    Args:
        video_id: YouTube video ID.
        status: One of 'pending', 'injected', 'failed', 'skipped'.
        wp_post_id: WordPress post ID (if created/updated).
        agent: Agent callsign that processed the video.
        registry_dir: Path to the registry directory.
        extra: Optional additional fields to merge into the record.
    """
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / f"{video_id}.json"

    # Preserve existing fields (e.g. yt_desc_updated)
    existing = {}
    if registry_path.exists():
        try:
            existing = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    record = {
        **existing,
        "video_id": video_id,
        "status": status,
        "wp_post_id": wp_post_id if wp_post_id is not None else existing.get("wp_post_id"),
        "injected_at": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
    }
    if extra:
        record.update(extra)

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
        List of dicts with keys: video_id, title, published_at, description,
        thumbnail_url.

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
            "live_broadcast_content": snippet.get("liveBroadcastContent", "none"),
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


def get_video_scheduled_time(video_id: str, yt_api_key: str) -> Optional[datetime]:
    """Fetch scheduledStartTime for premiere/livestream videos from YouTube API.

    Used to detect future-scheduled uploads so that the WP post can be
    set to 'future' status and published shortly after the video goes live.

    Args:
        video_id: YouTube video ID.
        yt_api_key: YouTube Data API v3 key.

    Returns:
        Scheduled start datetime (UTC, timezone-aware) if available,
        or None for regular (already-published) videos.
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "liveStreamingDetails,snippet,status",
        "id": video_id,
        "key": yt_api_key,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None

        item = items[0]
        # Scheduled premiere / live stream
        live_details = item.get("liveStreamingDetails", {})
        scheduled_str = live_details.get("scheduledStartTime")
        if scheduled_str:
            try:
                dt = datetime.fromisoformat(scheduled_str.replace("Z", "+00:00"))
                logger.info("Video %s scheduled at %s", video_id, dt.isoformat())
                return dt
            except ValueError:
                logger.warning("Could not parse scheduledStartTime: %s", scheduled_str)

        # Regular upload with publishAt (privacy = private + scheduled)
        status = item.get("status", {})
        publish_at_str = status.get("publishAt")
        if publish_at_str:
            try:
                dt = datetime.fromisoformat(publish_at_str.replace("Z", "+00:00"))
                logger.info("Video %s publishAt: %s", video_id, dt.isoformat())
                return dt
            except ValueError:
                logger.warning("Could not parse publishAt: %s", publish_at_str)

    except Exception as exc:
        logger.warning("get_video_scheduled_time %s: %s", video_id, exc)

    return None


# ============================================================
# WORDPRESS — create draft or scheduled post
# ============================================================

def create_draft(
    video_id: str,
    post_title: str,
    yt_embed_url: str,
    wp_base_url: str,
    wp_user: str,
    wp_app_pass: str,
    scheduled_at: Optional[datetime] = None,
    dry_run: bool = False,
) -> Optional[int]:
    """Create a WordPress post with YouTube embed.

    If scheduled_at is in the future, creates the post with status='future'
    so WordPress publishes it automatically at the specified time.
    Otherwise creates a regular draft.

    Args:
        video_id: YouTube video ID (for embed URL construction).
        post_title: Post title (from YouTube snippet.title).
        yt_embed_url: YouTube embed URL (https://www.youtube.com/embed/{id}).
        wp_base_url: WordPress site URL.
        wp_user: WordPress username.
        wp_app_pass: WordPress Application Password.
        scheduled_at: Optional UTC datetime when WP post should go live.
            If None or in the past, creates a draft.
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

    now_utc = datetime.now(timezone.utc)

    # Determine WP post status and date
    if scheduled_at and scheduled_at > now_utc:
        wp_status = "future"
        # Use date_gmt (UTC) for scheduled posts
        wp_date_gmt = scheduled_at.strftime("%Y-%m-%dT%H:%M:%S")
        logger.info(
            "Scheduling WP post for %s at %s UTC",
            video_id, wp_date_gmt,
        )
    else:
        wp_status = "draft"
        wp_date_gmt = None

    payload: dict = {
        "title": post_title,
        "content": embed_block,
        "status": wp_status,
    }
    if wp_date_gmt:
        payload["date_gmt"] = wp_date_gmt

    if dry_run:
        logger.info(
            "DRY RUN -- would create %s: %r | YT:%s | scheduled=%s",
            wp_status, post_title[:60], video_id, wp_date_gmt,
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
    logger.info(
        "Post created [%s]: WP#%s | scheduled=%s | %s",
        wp_status, wp_id, wp_date_gmt, link,
    )
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
    publish_delay_min: int = 5,
    publish_delay_max: int = 37,
) -> None:
    """Main watch loop — poll YouTube channel and process new videos.

    For each new video:
      - If it's a future premiere: creates a WordPress scheduled post
        with publish time = YT premiere time + random(5..37) minutes.
      - If already published: creates a draft for editorial review.

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
        publish_delay_min: Min WP publish delay after YT premiere (minutes).
        publish_delay_max: Max WP publish delay after YT premiere (minutes).
    """
    logger.info(
        "Monitor starting | channel=%s | interval=%ds | dry_run=%s | "
        "publish_delay=%d-%dmin",
        channel_id, interval, dry_run, publish_delay_min, publish_delay_max,
    )

    last_check: Optional[datetime] = None

    while True:
        now = datetime.now(timezone.utc)
        logger.info(
            "Polling YouTube channel %s (since=%s)...", channel_id,
            last_check.isoformat() if last_check else "any",
        )

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
                update_registry(
                    vid_id, "pending",
                    agent="vse-architect-01",
                    registry_dir=registry_dir,
                )

            # -----------------------------------------------
            # SMART SCHEDULING — detect premiere/scheduledTime
            # -----------------------------------------------
            scheduled_yt_time: Optional[datetime] = None

            live_content = video.get("live_broadcast_content", "none")
            if live_content == "upcoming":
                # Premiere or live stream scheduled for the future
                scheduled_yt_time = get_video_scheduled_time(vid_id, yt_api_key)

            wp_publish_at: Optional[datetime] = None
            if scheduled_yt_time and scheduled_yt_time > now:
                delay_minutes = calculate_publish_delay(
                    publish_delay_min, publish_delay_max
                )
                wp_publish_at = scheduled_yt_time + timedelta(minutes=delay_minutes)
                logger.info(
                    "Scheduled post: YT@%s + %dmin = WP@%s",
                    scheduled_yt_time.strftime("%H:%M"),
                    delay_minutes,
                    wp_publish_at.strftime("%H:%M"),
                )

            # -----------------------------------------------
            # CREATE WP POST (draft or scheduled future)
            # -----------------------------------------------
            wp_id = create_draft(
                video_id=vid_id,
                post_title=title,
                yt_embed_url=f"https://www.youtube.com/embed/{vid_id}",
                wp_base_url=wp_base_url,
                wp_user=wp_user,
                wp_app_pass=wp_app_pass,
                scheduled_at=wp_publish_at,
                dry_run=dry_run,
            )

            # -----------------------------------------------
            # SEO GENERATION (requires VTT to be available)
            # -----------------------------------------------
            gen_ok = trigger_generate(
                video_id=vid_id,
                wp_id=wp_id or 0,
                post_title=title,
                api_key=gemini_api_key,
                subs_dir=subs_dir,
                seo_dir=seo_dir,
                dry_run=dry_run,
            )

            # -----------------------------------------------
            # INJECT FULL SEO CONTENT (if generation succeeded)
            # Content + thumbnail + RankMath meta
            # -----------------------------------------------
            inject_ok = False
            if gen_ok and wp_id:
                seo_path = os.path.join(seo_dir, f"{vid_id}.json")
                if os.path.exists(seo_path):
                    try:
                        import json as _json
                        from core.injector import inject_video  # type: ignore

                        seo_data = _json.loads(
                            open(seo_path, encoding="utf-8").read()
                        )
                        result = inject_video(
                            wp_id=wp_id,
                            yt_id=vid_id,
                            seo=seo_data,
                            wp_base_url=wp_base_url,
                            wp_user=wp_user,
                            wp_app_pass=wp_app_pass,
                            dry_run=dry_run,
                        )
                        inject_ok = result.get("ok", False)
                        logger.info(
                            "Inject %s: WP#%s | RankMath=%s | %s",
                            "OK" if inject_ok else "FAIL",
                            wp_id,
                            result.get("rankmath_ok", False),
                            result.get("link", "?"),
                        )
                    except Exception as exc:
                        logger.error("Inject exception for %s: %s", vid_id, exc)
                else:
                    logger.warning(
                        "SEO JSON not found after generate for %s: %s",
                        vid_id, seo_path,
                    )

            # -----------------------------------------------
            # UPDATE REGISTRY
            # -----------------------------------------------
            if not dry_run:
                final_status = "injected" if (wp_id and gen_ok and inject_ok) else "pending"
                extra = {}
                if wp_publish_at:
                    extra["wp_scheduled_at"] = wp_publish_at.isoformat()
                update_registry(
                    vid_id, final_status,
                    wp_post_id=wp_id,
                    agent="vse-architect-01",
                    registry_dir=registry_dir,
                    extra=extra if extra else None,
                )


        logger.info(
            "Poll done: %d new videos processed | next check in %ds",
            new_count, interval,
        )
        last_check = now

        if run_once:
            break
        time.sleep(interval)
