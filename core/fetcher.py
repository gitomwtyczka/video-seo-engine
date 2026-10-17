#!/usr/bin/env python3
"""VSE Core Fetcher — YouTube metadata + transcript fetching.

Migrated from: shadow-perihelion/scripts/youtube-worker/youtube_fetch.py
Original migration date: 2026-05-13 (vse-architect-01)
Key update: 2026-06-15 (vse-strateg-01) — fetch_metadata_ytdlp() → fetch_metadata_api_v3()

Context: Oracle Cloud VPS IP is banned by YouTube — yt-dlp metadata fails.
Fix: YouTube Data API v3 via googleapis.com (NOT blocked on Oracle Cloud).
GCP project: glass-turbine-388620 (Simple API Key AIzaSyAlexKzu4-Wu2Wupck5p7qJuyPme9bh1lo)

D11 Video Thumbnails (2026-06-21, vse-dev-26):
  fetch_video_thumbnails() — downloads YouTube thumbnails for article screenshots.
  Fallback chain: maxresdefault.jpg → sddefault.jpg → hqdefault.jpg
  For second screenshot: /1.jpg, /2.jpg, /3.jpg (YouTube auto-generated storyboard frames)

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

import requests as _requests_lib

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


def get_vtt_coverage_seconds(vtt_text: str) -> float:
    """Parse VTT to find the last timestamp and return it in seconds."""
    if not vtt_text:
        return 0.0
    
    matches = re.findall(r'-->\s*(\d+:\d{2}:\d{2}[\.,]\d{3}|\d+:\d{2}[\.,]\d{3})', vtt_text)
    if not matches:
        return 0.0
        
    last_ts = matches[-1]
    last_ts = last_ts.replace(',', '.')
    
    parts = last_ts.split(':')
    try:
        if len(parts) == 3:
            h, m, s_ms = parts
            s, ms = s_ms.split('.')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
        elif len(parts) == 2:
            m, s_ms = parts
            s, ms = s_ms.split('.')
            return int(m) * 60 + int(s) + int(ms) / 1000.0
    except ValueError:
        pass
    return 0.0


def check_vtt_coverage(vtt_text: str, duration_seconds: int) -> float:
    """Return coverage ratio of VTT vs actual video duration."""
    if not vtt_text or duration_seconds <= 0:
        return 0.0
    cov_sec = get_vtt_coverage_seconds(vtt_text)
    return cov_sec / duration_seconds


# ---------------------------------------------------------------------------
# D11: Video Thumbnails — download from YouTube
# ---------------------------------------------------------------------------

def fetch_video_thumbnails(
    video_id: str,
    output_dir: str,
    count: int = 2,
) -> list[dict]:
    """Download YouTube video thumbnails for article screenshots.

    CO: Pobiera thumbnails z YouTube dla screenshotów w artykule.

    PO CO: Artykuły z obrazkami rankują wyżej w Google (Image SEO, Discover).
    RankMath i Google wymagają ImageObject w schema. Thumbnails z YouTube
    są najszybszym źródłem — nie wymagają renderowania wideo.

    JAK: Dla pierwszego screena próbuje maxresdefault → sddefault → hqdefault.
    Dla drugiego screena: /1.jpg, /2.jpg, /3.jpg (YouTube auto-generated
    storyboard frames — różne momenty wideo).
    Pliki zapisywane do output_dir z unikalnymi nazwami.

    Args:
        video_id: YouTube video ID (11 chars).
        output_dir: Directory to save downloaded thumbnails.
        count: Number of thumbnails to download (1 or 2).

    Returns:
        List of dicts: [{"path": "...", "width": 1280, "height": 720,
        "source": "youtube_maxres", "url": "https://img.youtube.com/..."}]
        Empty list on complete failure (graceful degradation).
    """
    os.makedirs(output_dir, exist_ok=True)
    results: list[dict] = []

    # Primary thumbnail: main video thumbnail (best quality)
    primary_chain = [
        ("maxresdefault", 1280, 720),
        ("sddefault", 640, 480),
        ("hqdefault", 480, 360),
    ]

    for quality, width, height in primary_chain:
        thumb_url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            resp = _requests_lib.get(thumb_url, timeout=15)
            # YouTube returns 200 + tiny grey placeholder for missing resolutions
            if resp.status_code == 200 and len(resp.content) > 5000:
                filename = f"{video_id}_thumb_0.jpg"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                results.append({
                    "path": filepath,
                    "width": width,
                    "height": height,
                    "source": f"youtube_{quality}",
                    "url": thumb_url,
                })
                logger.info(
                    "[fetcher] D11 thumbnail 0: %s (%s, %d bytes)",
                    quality, video_id, len(resp.content),
                )
                break
        except Exception as exc:
            logger.debug("[fetcher] D11 thumb %s failed: %s", quality, exc)

    if not results:
        logger.warning("[fetcher] D11: no primary thumbnail for %s", video_id)
        return []

    if count < 2:
        return results

    # Secondary thumbnail: YouTube auto-generated storyboard frames
    # These are different moments of the video (YouTube generates /1.jpg, /2.jpg, /3.jpg)
    secondary_chain = ["1", "2", "3"]
    for frame_id in secondary_chain:
        thumb_url = f"https://img.youtube.com/vi/{video_id}/{frame_id}.jpg"
        try:
            resp = _requests_lib.get(thumb_url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 3000:
                filename = f"{video_id}_thumb_1.jpg"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                results.append({
                    "path": filepath,
                    "width": 480,
                    "height": 360,
                    "source": f"youtube_frame_{frame_id}",
                    "url": thumb_url,
                })
                logger.info(
                    "[fetcher] D11 thumbnail 1: frame %s (%s, %d bytes)",
                    frame_id, video_id, len(resp.content),
                )
                break
        except Exception as exc:
            logger.debug("[fetcher] D11 frame %s failed: %s", frame_id, exc)

    if len(results) < 2:
        logger.warning(
            "[fetcher] D11: only %d thumbnail(s) for %s (wanted 2)",
            len(results), video_id,
        )

    return results


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
    import sys
    url = f"https://www.youtube.com/watch?v={video_id}"
    vtt_path = os.path.join(output_dir, f"{video_id}.{lang}.vtt")
    
    cookies_file = os.environ.get('YTDLP_COOKIES_FILE', '')
    cmd_base = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang", lang,
        "--sub-format", "vtt",
        "--output", os.path.join(output_dir, f"{video_id}.%(ext)s"),
        url
    ]

    methods_to_try = []
    if cookies_file and os.path.exists(cookies_file):
        methods_to_try.append(('file', cmd_base + ['--cookies', cookies_file]))
    
    if sys.platform == 'win32':  # local runner na Windows
        methods_to_try.append(('firefox', cmd_base + ['--cookies-from-browser', 'firefox']))
        methods_to_try.append(('chrome', cmd_base + ['--cookies-from-browser', 'chrome']))
        
    methods_to_try.append(('none', cmd_base))
    
    for cookies_method, cmd in methods_to_try:
        try:
            logger.info("[fetcher] yt-dlp using cookies: %s", cookies_method)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if os.path.exists(vtt_path):
                with open(vtt_path, 'r', encoding='utf-8') as f:
                    return f.read(), lang
            
            if result.returncode != 0 and cookies_method != 'none':
                logger.warning("[fetcher] yt-dlp cookies method '%s' failed, retrying...", cookies_method)
                continue
                
        except Exception as e:
            logger.warning("[fetcher] yt-dlp subtitle error for %s using %s: %s", video_id, cookies_method, e)
            if cookies_method != 'none':
                continue
                
    return None, None


def fetch_transcript_api_v3(
    video_id: str,
    lang: str,
    api_key: str = "",
    access_token: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Fetch transcript via YouTube Data API v3 (Captions endpoint).

    When access_token (OAuth 2.0 Bearer token with youtube.force-ssl scope) is provided:
      1. Lists caption tracks via GET /youtube/v3/captions?part=snippet&videoId={video_id}
      2. Selects best track: manual in lang -> ASR in lang -> manual any -> first available
      3. Downloads VTT via GET /youtube/v3/captions/{caption_id}?tfmt=vtt
      4. Works on VPS without Local Runner, including Private & Scheduled videos!
    """
    try:
        headers: dict[str, str] = {"Accept": "application/json"}
        if access_token:
            url = f"https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={video_id}"
            headers["Authorization"] = f"Bearer {access_token}"
        elif api_key:
            url = f"https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={video_id}&key={api_key}"
        else:
            return None, None

        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read())

        items = data.get("items", [])
        if not items:
            logger.info("[fetcher] API v3 captions: 0 tracks for %s", video_id)
            return None, None

        def _lang_matches(item_lang: str, target: str) -> bool:
            item_l = (item_lang or "").lower()
            tgt_l = (target or "").lower()
            return item_l == tgt_l or item_l.startswith(f"{tgt_l}-") or item_l.startswith(tgt_l)

        manual_lang = None
        asr_lang = None
        manual_any = None

        for item in items:
            snip = item.get("snippet", {})
            item_lang = snip.get("language", "")
            track_kind = snip.get("trackKind", "")
            is_asr = track_kind.upper() == "ASR"
            if _lang_matches(item_lang, lang):
                if not is_asr and manual_lang is None:
                    manual_lang = item
                elif is_asr and asr_lang is None:
                    asr_lang = item
            elif not is_asr and manual_any is None:
                manual_any = item

        chosen = manual_lang or asr_lang or manual_any or items[0]
        caption_id = chosen["id"]
        chosen_snip = chosen.get("snippet", {})
        chosen_lang = chosen_snip.get("language", lang) or lang

        dl_headers: dict[str, str] = {}
        if access_token:
            dl_url = f"https://www.googleapis.com/youtube/v3/captions/{caption_id}?tfmt=vtt"
            dl_headers["Authorization"] = f"Bearer {access_token}"
        else:
            dl_url = f"https://www.googleapis.com/youtube/v3/captions/{caption_id}?tfmt=vtt&key={api_key}"

        dl_req = urllib.request.Request(dl_url, headers=dl_headers)  # noqa: S310
        with urllib.request.urlopen(dl_req, timeout=20) as resp:  # noqa: S310
            raw_bytes = resp.read()
            vtt_text = raw_bytes.decode("utf-8", errors="replace").strip()

        if not vtt_text:
            logger.warning("[fetcher] API v3 captions returned empty body for %s (caption_id=%s)", video_id, caption_id)
            return None, None

        if not vtt_text.startswith("WEBVTT"):
            vtt_text = f"WEBVTT\n\n{vtt_text}\n"

        logger.info(
            "[fetcher] API v3 captions OK: %s caption_id=%s lang=%s oauth=%s (%d chars)",
            video_id, caption_id, chosen_lang, bool(access_token), len(vtt_text),
        )
        return vtt_text, chosen_lang
    except Exception as e:
        logger.warning("[fetcher] API v3 captions error for %s (oauth=%s): %s", video_id, bool(access_token), e)
    return None, None


# ---------------------------------------------------------------------------
# Metadata fetching — YouTube Data API v3 (PRIMARY on VPS)
# ---------------------------------------------------------------------------

def fetch_metadata_api_v3(video_id: str, api_key: str, access_token: str | None = None) -> dict:
    """Fetch video metadata via YouTube Data API v3.

    Uses googleapis.com — NOT blocked on Oracle Cloud VPS.
    When access_token is provided, requests part=snippet,contentDetails,statistics,status
    so Private and Scheduled videos owned by the user's channel are accessible.

    Returns metadata dict or {} on failure.
    """
    import urllib.parse

    base_url = "https://www.googleapis.com/youtube/v3/videos"

    def _do_request(use_oauth: bool) -> dict:
        if use_oauth and access_token:
            params = {"id": video_id, "part": "snippet,contentDetails,statistics,status"}
            headers = {"Authorization": f"Bearer {access_token}"}
        else:
            params = {"id": video_id, "part": "snippet,contentDetails,statistics"}
            headers = {}
            if api_key:
                params["key"] = api_key
        query_string = urllib.parse.urlencode(params)
        req_url = f"{base_url}?{query_string}"
        req = urllib.request.Request(req_url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read())

    data: dict = {}
    if access_token:
        try:
            data = _do_request(use_oauth=True)
        except Exception as e:
            logger.warning("[fetcher] API v3 OAuth metadata error for %s: %s — falling back to api_key", video_id, e)
            data = {}

    if not data.get("items") and api_key:
        try:
            data = _do_request(use_oauth=False)
        except Exception as e:
            logger.error("[fetcher] API v3 error for %s: %s", video_id, e)
            return {}

    if not data.get("items"):
        logger.warning("[fetcher] API v3: no items for video_id=%s", video_id)
        return {}

    item = data["items"][0]
    snippet = item.get("snippet", {})
    duration_iso_str = item.get("contentDetails", {}).get("duration", "")
    thumbnails = snippet.get("thumbnails", {})
    thumb = (
        thumbnails.get("maxres")
        or thumbnails.get("standard")
        or thumbnails.get("high", {})
    ).get("url", "")
    stats = item.get("statistics", {})
    status_obj = item.get("status", {})

    meta = {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "published_at": snippet.get("publishedAt", ""),
        "duration_seconds": parse_iso8601_duration(duration_iso_str),
        "duration_iso": duration_iso_str,
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "thumbnail_url": thumb,
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "tags": snippet.get("tags", []),
        "privacy_status": status_obj.get("privacyStatus", "public"),
        "publish_at": status_obj.get("publishAt"),
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    logger.info(
        "[fetcher] API v3 OK: %s title=%r duration=%s views=%s privacy=%s",
        video_id, meta["title"][:50], duration_iso_str, meta["view_count"], meta["privacy_status"],
    )
    return meta


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

def process_video(
    video_url: str,
    output_dir: str = "data/vtt",
    lang: str = "pl",
    api_key: Optional[str] = None,
    access_token: Optional[str] = None,
) -> dict:
    """Fetch metadata + transcript for one video. Returns metadata dict.

    Strategy:
      1. Metadata: YOUTUBE_API_KEY / OAuth access_token → API v3 (VPS-safe, supports Private/Scheduled).
         Fallback: yt-dlp (local only).
      2. Priority 0 Transcript (when access_token is provided):
         YouTube Data API v3 Captions endpoint via OAuth Bearer token.
         If captions are returned, skips blocked youtube-transcript-api / yt-dlp on VPS.
      3. Fallback Transcript: youtube-transcript-api → yt-dlp VTT → API v3 key.
      4. Save VTT to output_dir/<video_id>.<lang>.vtt.
    """
    video_id = extract_video_id(video_url)
    logger.info("[fetcher] Processing %s (lang=%s, oauth=%s)", video_id, lang, bool(access_token))
    os.makedirs(output_dir, exist_ok=True)

    # 1. Metadata: API v3 first (VPS-safe), yt-dlp as local fallback
    yt_api_key = os.environ.get("YOUTUBE_API_KEY", "") or (api_key or "")
    if yt_api_key or access_token:
        meta = fetch_metadata_api_v3(video_id, yt_api_key, access_token=access_token)
    else:
        logger.warning(
            "[fetcher] YOUTUBE_API_KEY not set — falling back to yt-dlp "
            "(will fail on Oracle Cloud VPS)"
        )
        meta = fetch_metadata_ytdlp(video_id)

    if not meta:
        logger.error("[fetcher] metadata_fetch_failed for %s", video_id)
        return {"video_id": video_id, "error": "metadata_fetch_failed"}

    duration_seconds = meta.get("duration_seconds", 0)
    best_vtt = None
    best_lang = None
    best_coverage = 0.0

    # Priority 0: OAuth 2.0 YouTube Data API v3 Captions (works on VPS + Private/Scheduled videos)
    if access_token:
        logger.info("[fetcher] Priority 0: trying YouTube Data API v3 OAuth captions for %s...", video_id)
        oauth_vtt, oauth_lang = fetch_transcript_api_v3(
            video_id, lang, yt_api_key, access_token=access_token
        )
        if oauth_vtt:
            oauth_cov = check_vtt_coverage(oauth_vtt, duration_seconds)
            if (
                oauth_cov >= 0.8
                or meta.get("privacy_status") in ("private", "unlisted")
                or (duration_seconds <= 0 and len(oauth_vtt.strip()) > 20)
            ):
                best_vtt, best_lang, best_coverage = oauth_vtt, oauth_lang, max(oauth_cov, 0.8)
                logger.info(
                    "[fetcher] Priority 0 OAuth captions OK (coverage=%.2f, privacy=%s) — skipping yt-dlp/transcript-api",
                    oauth_cov, meta.get("privacy_status"),
                )
            else:
                best_vtt, best_lang, best_coverage = oauth_vtt, oauth_lang, oauth_cov
                logger.info("[fetcher] Priority 0 OAuth captions coverage %.2f < 0.8.", oauth_cov)

    # 2. Transcript: transcript-api (<= 35 min)
    if best_coverage < 0.8 and duration_seconds <= 35 * 60:
        logger.info("[fetcher] Duration <= 35 min (%.0f s), trying transcript-api...", duration_seconds)
        vtt_text, lang_used = fetch_transcript_api(video_id, lang)
        if vtt_text:
            cov = check_vtt_coverage(vtt_text, duration_seconds)
            if cov >= 0.8:
                best_vtt, best_lang, best_coverage = vtt_text, lang_used, cov
                logger.info("[fetcher] transcript-api coverage %.2f >= 0.8. OK.", cov)
            else:
                logger.info("[fetcher] transcript-api coverage %.2f < 0.8.", cov)
                if cov > best_coverage:
                    best_vtt, best_lang, best_coverage = vtt_text, lang_used, cov

    # 3. yt-dlp if > 35 min OR step 2 failed / coverage < 80%
    if best_coverage < 0.8:
        reason = "> 35 min" if duration_seconds > 35 * 60 else "coverage < 80%"
        logger.info("[fetcher] trying yt-dlp for transcript (%s)...", reason)
        yt_vtt, yt_lang = fetch_transcript_ytdlp(video_id, lang, output_dir)
        if yt_vtt:
            yt_cov = check_vtt_coverage(yt_vtt, duration_seconds)
            if yt_cov >= 0.8:
                best_vtt, best_lang, best_coverage = yt_vtt, yt_lang, yt_cov
                logger.info("[fetcher] yt-dlp coverage %.2f >= 0.8. OK.", yt_cov)
            else:
                logger.info("[fetcher] yt-dlp coverage %.2f < 0.8.", yt_cov)
                if yt_cov > best_coverage:
                    best_vtt, best_lang, best_coverage = yt_vtt, yt_lang, yt_cov

    # 4. API v3 key fallback if yt-dlp also fails / coverage < 80% and OAuth was not used
    if best_coverage < 0.8:
        if yt_api_key and not access_token:
            logger.info("[fetcher] trying YouTube Data API v3 captions (api_key) as last resort...")
            api3_vtt, api3_lang = fetch_transcript_api_v3(video_id, lang, yt_api_key)
            if api3_vtt:
                api3_cov = check_vtt_coverage(api3_vtt, duration_seconds)
                if api3_cov >= 0.8:
                    best_vtt, best_lang, best_coverage = api3_vtt, api3_lang, api3_cov
                    logger.info("[fetcher] API v3 coverage %.2f >= 0.8. OK.", api3_cov)
                elif api3_cov > best_coverage:
                    best_vtt, best_lang, best_coverage = api3_vtt, api3_lang, api3_cov

        if best_vtt:
            logger.warning(
                "[fetcher] Warning: All methods failed to reach 80%% coverage. Best coverage: %.2f%%. Saving what we have.",
                best_coverage * 100,
            )
        else:
            logger.warning("[fetcher] Warning: All methods failed to fetch transcript.")

    # 5. Save VTT
    if best_vtt:
        vtt_path = os.path.join(output_dir, f"{video_id}.{best_lang}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(best_vtt)
        logger.info("[fetcher] VTT saved: %s (%d chars)", vtt_path, len(best_vtt))
        meta["vtt_path"] = vtt_path
        meta["vtt_language"] = best_lang
    else:
        logger.warning("[fetcher] No transcript available for %s", video_id)
        meta["vtt_path"] = None
        meta["vtt_language"] = None

    meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"

    # 6. Save JSON metadata (legacy compat with CLI callers)
    json_path = os.path.join(output_dir, f"{video_id}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info("[fetcher] JSON saved: %s.json", video_id)
    except Exception as e:
        logger.warning("[fetcher] Could not save JSON for %s: %s", video_id, e)

    return meta
