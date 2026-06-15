#!/usr/bin/env python3
"""VSE Core Fetcher — YouTube metadata + transcript fetching.

Migrated from: shadow-perihelion/scripts/youtube-worker/youtube_fetch.py
Original migration date: 2026-05-13 (vse-architect-01)
Key update: 2026-06-15 (vse-strateg-01) — fetch_metadata_ytdlp() → fetch_metadata_api_v3()

Context: Oracle Cloud VPS IP is banned by YouTube — yt-dlp metadata fails.
Fix: YouTube Data API v3 via googleapis.com (NOT blocked on Oracle Cloud).
GCP project: glass-turbine-388620 (Simple API Key AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo)

Dependencies (in requirements.txt):
  youtube-transcript-api>=1.2.4
  yt-dlp>=2024.1.0  (transcript fallback only — metadata disabled on VPS)

Environment variables:
  YOUTUBE_API_KEY  — Required on VPS. Falls back to yt-dlp locally if not set.
"""
import json
import logging
import os
import re
import subprocess
import urllib.request
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# youtube-transcript-api v1.2.4+ uses instance-based API
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import WebVTTFormatter
    HAS_TRANSCRIPT_API = True
except ImportError:
    HAS_TRANSCRIPT_API = False
    logger.warning("youtube-transcript-api not installed — transcript fetching unavailable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or return as-is if already an ID."""
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def iso_duration(seconds: int) -> str:
    """Convert seconds to ISO 8601 duration (PT#H#M#S)."""
    if seconds <= 0:
        return "PT0S"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = "PT"
    if h:
        parts += f"{h}H"
    if m:
        parts += f"{m}M"
    if s or parts == "PT":
        parts += f"{s}S"
    return parts


def parse_iso8601_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration string (PT#H#M#S) to seconds.

    Used for YouTube Data API v3 contentDetails.duration field.
    """
    if not duration_str:
        return 0
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    m = re.match(pattern, duration_str)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mins * 60 + s


def format_published_date(raw: str) -> str:
    """Convert yt-dlp upload_date (YYYYMMDD) or API publishedAt to ISO 8601."""
    if not raw:
        return ""
    try:
        if 'T' in raw:
            return raw
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T00:00:00Z"
        return raw
    except Exception:
        return raw


def log(msg: str, quiet: bool = False) -> None:
    """Legacy helper — kept for backward compat with old CLI callers."""
    if not quiet:
        logger.info(msg)


# ---------------------------------------------------------------------------
# Transcript fetching — youtube-transcript-api v1.2.4+ (instance API)
# ---------------------------------------------------------------------------

def fetch_transcript_api(video_id: str, lang: str = "pl") -> Tuple[Optional[str], Optional[str]]:
    """Fetch transcript via youtube-transcript-api v1.2.4+.

    Returns (vtt_text, language_used) or (None, None) on failure.
    Priority: manual in target lang > auto in target lang > manual any > auto any.
    """
    if not HAS_TRANSCRIPT_API:
        return None, None
    try:
        ytt = YouTubeTranscriptApi()
        formatter = WebVTTFormatter()

        transcript_list = ytt.list(video_id)

        manual_match = None
        auto_match = None
        any_manual = None
        any_auto = None

        for t in transcript_list:
            if t.language_code == lang:
                if not t.is_generated:
                    manual_match = t
                else:
                    auto_match = t
            elif not t.is_generated and any_manual is None:
                any_manual = t
            elif t.is_generated and any_auto is None:
                any_auto = t

        lang_used = lang
        if manual_match:
            entries = ytt.fetch(video_id, languages=[lang])
            lang_used = lang
        elif auto_match:
            entries = ytt.fetch(video_id, languages=[lang])
            lang_used = f"{lang}-auto"
        elif any_manual:
            entries = ytt.fetch(video_id, languages=[any_manual.language_code])
            lang_used = any_manual.language_code
        elif any_auto:
            entries = ytt.fetch(video_id, languages=[any_auto.language_code])
            lang_used = f"{any_auto.language_code}-auto"
        else:
            logger.warning("[fetcher] No transcripts found for %s", video_id)
            return None, None

        vtt_text = formatter.format_transcript(entries)
        logger.info("[fetcher] transcript-api OK: %s lang=%s", video_id, lang_used)
        return vtt_text, lang_used
    except Exception as e:
        logger.warning("[fetcher] transcript-api error for %s: %s", video_id, e)
        return None, None


def fetch_transcript_ytdlp(
    video_id: str, lang: str = "pl", output_dir: str = "."
) -> Tuple[Optional[str], Optional[str]]:
    """Fallback: fetch subtitles via yt-dlp. Returns (vtt_text, language_used).

    WARNING: May fail on Oracle Cloud VPS due to YouTube IP ban.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    vtt_path = os.path.join(output_dir, f"{video_id}.{lang}.vtt")
    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", lang,
            "--sub-format", "vtt",
            "--output", os.path.join(output_dir, f"{video_id}.%(ext)s"),
            url
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(vtt_path):
            with open(vtt_path, 'r', encoding='utf-8') as f:
                return f.read(), lang
    except Exception as e:
        logger.warning("[fetcher] yt-dlp subtitle error for %s: %s", video_id, e)
    return None, None


# ---------------------------------------------------------------------------
# Metadata fetching — YouTube Data API v3 (PRIMARY on VPS)
# ---------------------------------------------------------------------------

def fetch_metadata_api_v3(video_id: str, api_key: str) -> dict:
    """Fetch video metadata via YouTube Data API v3.

    Uses googleapis.com — NOT blocked on Oracle Cloud VPS.
    GCP project: glass-turbine-388620 (Simple API Key, public data only).

    Returns metadata dict or {} on failure.
    """
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?id={video_id}&key={api_key}"
        f"&part=snippet,contentDetails,statistics"
    )
    try:
        req = urllib.request.Request(url)  # noqa: S310
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read())

        if not data.get("items"):
            logger.warning("[fetcher] API v3: no items for video_id=%s", video_id)
            return {}

        item = data["items"][0]
        snippet = item["snippet"]
        duration_iso_str = item["contentDetails"]["duration"]
        thumbnails = snippet.get("thumbnails", {})
        thumb = (
            thumbnails.get("maxres")
            or thumbnails.get("standard")
            or thumbnails.get("high", {})
        ).get("url", "")

        meta = {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt", ""),
            "duration_seconds": parse_iso8601_duration(duration_iso_str),
            "duration_iso": duration_iso_str,
            "view_count": int(item["statistics"].get("viewCount", 0)),
            "like_count": int(item["statistics"].get("likeCount", 0)),
            "comment_count": int(item["statistics"].get("commentCount", 0)),
            "thumbnail_url": thumb,
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "tags": snippet.get("tags", []),
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        }
        logger.info(
            "[fetcher] API v3 OK: %s title=%r duration=%s views=%s",
            video_id, meta["title"][:50], duration_iso_str, meta["view_count"],
        )
        return meta
    except Exception as e:
        logger.error("[fetcher] API v3 error for %s: %s", video_id, e)
        return {}


# ---------------------------------------------------------------------------
# Metadata fallback — yt-dlp (LOCAL ONLY — fails on VPS)
# ---------------------------------------------------------------------------

def fetch_metadata_ytdlp(video_id: str) -> dict:
    """Fetch video metadata via yt-dlp --dump-json.

    WARNING: Fails on Oracle Cloud VPS (YouTube IP ban). Use only locally
    or as last-resort when YOUTUBE_API_KEY is not set.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.warning(
                "[fetcher] yt-dlp metadata error for %s: %s",
                video_id, result.stderr[:200]
            )
            return {}
        data = json.loads(result.stdout)
        return {
            "video_id": video_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "published_at": format_published_date(data.get("upload_date", "")),
            "duration_seconds": data.get("duration", 0),
            "duration_iso": iso_duration(int(data.get("duration", 0))),
            "view_count": data.get("view_count", 0),
            "like_count": data.get("like_count", 0),
            "comment_count": data.get("comment_count", 0),
            "thumbnail_url": data.get("thumbnail", ""),
            "channel_id": data.get("channel_id", ""),
            "channel_title": data.get("channel", ""),
            "webpage_url": data.get("webpage_url", url),
            "tags": data.get("tags", []),
        }
    except json.JSONDecodeError:
        logger.error("[fetcher] yt-dlp returned invalid JSON for %s", video_id)
        return {}
    except FileNotFoundError:
        logger.error("[fetcher] yt-dlp not found — install: pip install yt-dlp")
        return {}
    except Exception as e:
        logger.error("[fetcher] yt-dlp error for %s: %s", video_id, e)
        return {}


# ---------------------------------------------------------------------------
# Main entry point — called by pipeline.py
# ---------------------------------------------------------------------------

def process_video(video_id: str, output_dir: str, lang: str = "pl") -> dict:
    """Fetch metadata + transcript for one video. Returns metadata dict.

    Called by api/services/pipeline.py as:
        from core.fetcher import process_video as fetch_video
        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)

    Strategy:
      1. Metadata: YOUTUBE_API_KEY → API v3 (VPS-safe). Fallback: yt-dlp (local only).
      2. Transcript: youtube-transcript-api → yt-dlp VTT.
      3. Save VTT to output_dir/<video_id>.<lang>.vtt.

    Returns:
        dict with keys: video_id, title, description, published_at,
        duration_seconds, duration_iso, view_count, thumbnail_url,
        vtt_path, vtt_language, fetched_at.
        On failure: {"video_id": video_id, "error": "..."}.
    """
    logger.info("[fetcher] Processing %s (lang=%s)", video_id, lang)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Metadata: API v3 first (VPS-safe), yt-dlp as local fallback
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if api_key:
        meta = fetch_metadata_api_v3(video_id, api_key)
    else:
        logger.warning(
            "[fetcher] YOUTUBE_API_KEY not set — falling back to yt-dlp "
            "(will fail on Oracle Cloud VPS)"
        )
        meta = fetch_metadata_ytdlp(video_id)

    if not meta:
        logger.error("[fetcher] metadata_fetch_failed for %s", video_id)
        return {"video_id": video_id, "error": "metadata_fetch_failed"}

    # 2. Transcript: transcript-api first, yt-dlp as fallback
    vtt_text, lang_used = fetch_transcript_api(video_id, lang)
    if not vtt_text:
        logger.info("[fetcher] transcript-api failed for %s, trying yt-dlp fallback...", video_id)
        vtt_text, lang_used = fetch_transcript_ytdlp(video_id, lang, output_dir)

    # 3. Save VTT
    if vtt_text:
        vtt_path = os.path.join(output_dir, f"{video_id}.{lang}.vtt")
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(vtt_text)
        logger.info("[fetcher] VTT saved: %s (%d chars)", vtt_path, len(vtt_text))
        meta["vtt_path"] = vtt_path
        meta["vtt_language"] = lang_used or lang
    else:
        logger.warning("[fetcher] No transcript available for %s", video_id)
        meta["vtt_path"] = None
        meta["vtt_language"] = None

    meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"

    # 4. Save JSON metadata (legacy compat with CLI callers)
    json_path = os.path.join(output_dir, f"{video_id}.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info("[fetcher] JSON saved: %s.json", video_id)
    except Exception as e:
        logger.warning("[fetcher] Could not save JSON for %s: %s", video_id, e)

    return meta
