#!/usr/bin/env python3
"""YouTube Data Worker — universal CLI for fetching transcripts, metadata & stats.

Migrated from: shadow-perihelion/scripts/youtube-worker/youtube_fetch.py
Migration date: 2026-05-13
Author: youtube-worker 01 | shadow-perihelion
Migrated by: vse-architect-01

Usage:
  python -m core.fetcher --video <URL_or_ID>
  python -m core.fetcher --channel <CHANNEL_ID> [--limit N]
  python -m core.fetcher --playlist <PLAYLIST_ID> [--limit N]
  python -m core.fetcher --batch <file.txt>

Output:
  output/<video_id>.json   — metadata
  output/<video_id>.pl.vtt — transcript (VTT format, compatible with video-seo pipeline)

Dependencies:
  pip install youtube-transcript-api yt-dlp
"""
import argparse
import json
import logging
import os
import re
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# youtube-transcript-api v1.2.4+ uses instance-based API
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import WebVTTFormatter
    HAS_TRANSCRIPT_API = True
except ImportError:
    HAS_TRANSCRIPT_API = False


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


# ---------------------------------------------------------------------------
# Transcript fetching — youtube-transcript-api v1.2.4+ (instance API)
# ---------------------------------------------------------------------------

def fetch_transcript_api(video_id: str, lang: str = "pl") -> tuple:
    """Fetch transcript via youtube-transcript-api v1.2.4+.

    Returns (vtt_text, language_used) or (None, None) on failure.
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
            return None, None

        vtt_text = formatter.format_transcript(entries)
        return vtt_text, lang_used
    except Exception as e:
        log.warning("transcript-api error for %s: %s", video_id, e)
        return None, None


def fetch_transcript_ytdlp(video_id: str, lang: str = "pl", output_dir: str = ".") -> tuple:
    """Fallback: fetch subtitles via yt-dlp. Returns (vtt_text, language_used)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    vtt_path = os.path.join(output_dir, f"{video_id}.{lang}.vtt")
    try:
        cmd = [
            "yt-dlp", "--skip-download",
            "--write-auto-sub", "--write-sub",
            "--sub-lang", lang, "--sub-format", "vtt",
            "--output", os.path.join(output_dir, f"{video_id}.%(ext)s"),
            url
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(vtt_path):
            with open(vtt_path, 'r', encoding='utf-8') as f:
                return f.read(), lang
    except Exception as e:
        log.warning("yt-dlp subtitle error for %s: %s", video_id, e)
    return None, None


# ---------------------------------------------------------------------------
# Metadata fetching (yt-dlp — no API key needed)
# ---------------------------------------------------------------------------

def fetch_metadata_ytdlp(video_id: str) -> dict:
    """Fetch video metadata via yt-dlp --dump-json."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            log.warning("yt-dlp metadata error for %s: %s", video_id, result.stderr[:200])
            return {}
        data = json.loads(result.stdout)
        return {
            "video_id": video_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "published_at": data.get("upload_date", ""),
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
        log.error("yt-dlp returned invalid JSON for %s", video_id)
        return {}
    except FileNotFoundError:
        log.error("yt-dlp not found. Install: pip install yt-dlp")
        return {}
    except Exception as e:
        log.error("yt-dlp error for %s: %s", video_id, e)
        return {}


def format_published_date(raw: str) -> str:
    """Convert yt-dlp upload_date (YYYYMMDD) to ISO 8601."""
    if not raw:
        return ""
    try:
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T00:00:00Z"
        return raw
    except Exception:
        return raw


# ---------------------------------------------------------------------------
# Channel / Playlist listing
# ---------------------------------------------------------------------------

def fetch_channel_videos(channel_id: str, limit: int = 0) -> list:
    """List videos from a YouTube channel via yt-dlp."""
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    return _fetch_video_list(url, limit)


def fetch_playlist_videos(playlist_id: str, limit: int = 0) -> list:
    """List videos from a playlist via yt-dlp."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    return _fetch_video_list(url, limit)


def _fetch_video_list(url: str, limit: int = 0) -> list:
    """Internal: extract flat video list from URL."""
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", url]
    if limit > 0:
        cmd.extend(["--playlist-end", str(limit)])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                videos.append({
                    "video_id": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "url": entry.get("url", ""),
                    "duration": entry.get("duration", 0),
                    "duration_iso": iso_duration(int(entry.get("duration", 0) or 0)),
                })
            except json.JSONDecodeError:
                continue
        return videos
    except Exception as e:
        log.error("Error listing videos from %s: %s", url, e)
        return []


# ---------------------------------------------------------------------------
# Single video processing
# ---------------------------------------------------------------------------

def process_video(video_id: str, output_dir: str, lang: str = "pl") -> dict:
    """Fetch metadata + transcript for a single video. Returns metadata dict."""
    log.info("Processing %s...", video_id)

    meta = fetch_metadata_ytdlp(video_id)
    if not meta:
        meta = {"video_id": video_id, "error": "metadata_fetch_failed"}
    else:
        meta["published_at"] = format_published_date(meta.get("published_at", ""))

    vtt_text, lang_used = fetch_transcript_api(video_id, lang)
    if not vtt_text:
        log.info("transcript-api failed for %s, trying yt-dlp fallback...", video_id)
        vtt_text, lang_used = fetch_transcript_ytdlp(video_id, lang, output_dir)

    if vtt_text:
        vtt_filename = f"{video_id}.{lang}.vtt"
        vtt_path = os.path.join(output_dir, vtt_filename)
        with open(vtt_path, 'w', encoding='utf-8') as f:
            f.write(vtt_text)
        log.info("VTT saved: %s (%d chars)", vtt_filename, len(vtt_text))
        meta["vtt_path"] = vtt_path
        meta["vtt_language"] = lang_used or lang
    else:
        log.warning("No transcript available for %s", video_id)
        meta["vtt_path"] = None
        meta["vtt_language"] = None

    meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"
    json_path = os.path.join(output_dir, f"{video_id}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log.info("JSON saved: %s.json", video_id)

    return meta


# ---------------------------------------------------------------------------
# CLI (when used as module entrypoint)
# ---------------------------------------------------------------------------

def main():
    """CLI entrypoint for direct invocation."""
    logging.basicConfig(level=logging.INFO, format="[yt-worker] %(message)s")
    parser = argparse.ArgumentParser(description="YouTube Data Worker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--video', help='Video URL or ID')
    group.add_argument('--channel', help='Channel ID')
    group.add_argument('--playlist', help='Playlist ID')
    group.add_argument('--batch', help='File with video URLs/IDs (one per line)')

    parser.add_argument('--output-dir', default='./output')
    parser.add_argument('--lang', default='pl')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--fetch-all', action='store_true')

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.video:
        vid = extract_video_id(args.video)
        meta = process_video(vid, args.output_dir, args.lang)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    elif args.channel:
        videos = fetch_channel_videos(args.channel, args.limit)
        log.info("Found %d videos", len(videos))
        if args.fetch_all:
            for i, v in enumerate(videos, 1):
                if v.get("video_id"):
                    log.info("[%d/%d] %s", i, len(videos), v["video_id"])
                    process_video(v["video_id"], args.output_dir, args.lang)
                    time.sleep(1)
    elif args.playlist:
        videos = fetch_playlist_videos(args.playlist, args.limit)
        log.info("Found %d videos", len(videos))
        if args.fetch_all:
            for i, v in enumerate(videos, 1):
                if v.get("video_id"):
                    process_video(v["video_id"], args.output_dir, args.lang)
                    time.sleep(1)
    elif args.batch:
        if not os.path.exists(args.batch):
            log.error("Batch file not found: %s", args.batch)
            sys.exit(1)
        with open(args.batch) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        for i, line in enumerate(lines, 1):
            try:
                vid = extract_video_id(line)
                log.info("[%d/%d] %s", i, len(lines), vid)
                process_video(vid, args.output_dir, args.lang)
                time.sleep(1)
            except ValueError as e:
                log.warning("[%d/%d] SKIP: %s", i, len(lines), e)


if __name__ == "__main__":
    main()
