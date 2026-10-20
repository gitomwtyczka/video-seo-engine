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

Multi-Language & Cross-Language Engine (2026-10-17, vse-dev-01):
  - Extracts default_audio_language in fetch_metadata_api_v3() and fetch_metadata()
  - fetch_transcript_youtube_api() / fetch_transcript_api() never rejects foreign-language
    videos when target lang is missing (falls back to original manual/ASR track)
  - fetch_transcript_ytdlp() falls back to --sub-langs "en.*,de.*,es.*,fr.*,it.*,uk.*,pt.*,pl.*,orig"
  - Detects and returns source_lang in process_video()

Dependencies (in requirements.txt):
  youtube-transcript-api>=1.2.4
  yt-dlp>=2024.1.0  (transcript fallback only — metadata disabled on VPS)

Environment variables:
  YOUTUBE_API_KEY  — Required on VPS. Falls back to yt-dlp locally if not set.
"""
import glob
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

SUPPORTED_LANG_CODES = ("pl", "en", "de", "es", "fr", "it", "uk", "pt")

_LANG_STOPWORDS: dict[str, set[str]] = {
    "pl": {"jest", "nie", "się", "jak", "czy", "ale", "tylko", "przez", "oraz", "żeby", "który", "bardzo"},
    "en": {"the", "and", "that", "this", "with", "from", "your", "have", "are", "for", "you", "about"},
    "de": {"und", "der", "die", "das", "nicht", "mit", "sich", "auf", "für", "eine", "auch", "werden"},
    "es": {"que", "los", "las", "para", "con", "una", "por", "como", "más", "pero", "este", "esta"},
    "fr": {"les", "des", "une", "dans", "pour", "que", "qui", "sur", "pas", "plus", "avec", "sont"},
    "it": {"che", "non", "per", "con", "una", "sono", "della", "anche", "come", "più", "questo", "nella"},
    "uk": {"що", "не", "на", "для", "як", "але", "це", "він", "вона", "ми", "ви", "про", "або"},
    "pt": {"que", "não", "para", "com", "uma", "por", "mais", "como", "mas", "foi", "este", "isso"},
}


def normalize_lang_code(raw_lang: Optional[str]) -> str:
    """Normalize a BCP-47 language tag (e.g. 'en-US', 'pl-auto', 'de_DE') to 2-char lowercase code."""
    if not raw_lang:
        return ""
    cleaned = raw_lang.strip().lower().replace("_", "-")
    if cleaned.endswith("-auto"):
        cleaned = cleaned[:-5]
    base = cleaned.split("-")[0]
    if base == "ua":
        return "uk"
    return base[:2] if len(base) >= 2 else base


def detect_transcript_language(
    vtt_text: Optional[str],
    metadata_lang: Optional[str] = None,
    track_lang: Optional[str] = None,
) -> str:
    """Detect the 2-letter source language code of a transcript.

    Priority:
      1. WebVTT header 'Language: xx'
      2. Explicit track_lang from YouTube caption track (if not empty/unknown)
      3. Lexical stopword heuristic on VTT body text (PL/EN/DE/ES/FR/IT/UK/PT)
      4. metadata_lang (defaultAudioLanguage / defaultLanguage from YouTube metadata)
      5. Default fallback 'pl'
    """
    if vtt_text:
        m = re.search(r"(?im)^Language:\s*([a-zA-Z_-]+)", vtt_text[:600])
        if m:
            norm = normalize_lang_code(m.group(1))
            if norm:
                return norm

    norm_track = normalize_lang_code(track_lang)
    if norm_track and norm_track not in ("orig", "und", "auto"):
        # Verify with lexical heuristic if vtt_text is substantial
        if not vtt_text:
            return norm_track

    if vtt_text:
        clean_lines = []
        for line in vtt_text.splitlines():
            s = line.strip()
            if not s or s.startswith("WEBVTT") or "-->" in s or s.startswith("Kind:") or s.startswith("Language:") or s.isdigit():
                continue
            clean_lines.append(re.sub(r"<[^>]+>", "", s))
        sample_text = " ".join(clean_lines)[:15000].lower()
        words = re.findall(r"[a-ząćęłńóśźżäöüßáéíóúñàèìòùâêîôûçãõіїєґа-я]+", sample_text)
        if len(words) >= 15:
            scores: dict[str, int] = {code: 0 for code in _LANG_STOPWORDS}
            for w in words:
                for code, stop_set in _LANG_STOPWORDS.items():
                    if w in stop_set:
                        scores[code] += 1
            best_code, best_score = max(scores.items(), key=lambda kv: kv[1])
            if best_score >= 3:
                return best_code

    if norm_track and norm_track not in ("orig", "und", "auto"):
        return norm_track

    norm_meta = normalize_lang_code(metadata_lang)
    if norm_meta:
        return norm_meta

    return "pl"


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
    """Download YouTube video thumbnails for article screenshots."""
    os.makedirs(output_dir, exist_ok=True)
    results: list[dict] = []

    primary_chain = [
        ("maxresdefault", 1280, 720),
        ("sddefault", 640, 480),
        ("hqdefault", 480, 360),
    ]

    for quality, width, height in primary_chain:
        thumb_url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            resp = _requests_lib.get(thumb_url, timeout=15)
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

def fetch_transcript_youtube_api(video_id: str, lang: str = "pl") -> Tuple[Optional[str], Optional[str]]:
    """Fetch transcript via youtube-transcript-api v1.2.4+.

    Multi-Language & Cross-Language priority:
      1. Manual track in `lang`
      2. Original manual track in any language (`!is_generated`)
      3. Automatic (`ASR`) track in `lang`
      4. First available original `is_generated` track or first available track from `transcript_list`
         (e.g. English 'en', German 'de', Spanish 'es') — NEVER rejects foreign-language videos!

    Returns (vtt_text, language_used) or (None, None) on failure.
    """
    if not HAS_TRANSCRIPT_API:
        return None, None
    try:
        vid = extract_video_id(video_id)
        proxy_url = (os.getenv("YT_PROXY_URL") or os.getenv("WEBSHARE_PROXY_URL") or "").strip()
        ytt = None
        if proxy_url:
            try:
                from youtube_transcript_api.proxies import GenericProxyConfig
                ytt = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url))
            except Exception:
                ytt = YouTubeTranscriptApi()
        else:
            ytt = YouTubeTranscriptApi()
        formatter = WebVTTFormatter()

        transcript_list = list(ytt.list(vid))
        if not transcript_list:
            logger.warning("[fetcher] Empty transcript_list for %s", vid)
            return None, None

        target_norm = normalize_lang_code(lang) or "pl"

        manual_target = None
        manual_any = None
        asr_target = None
        asr_any = None

        for t in transcript_list:
            t_norm = normalize_lang_code(getattr(t, "language_code", ""))
            is_gen = bool(getattr(t, "is_generated", False))
            if t_norm == target_norm:
                if not is_gen and manual_target is None:
                    manual_target = t
                elif is_gen and asr_target is None:
                    asr_target = t
            else:
                if not is_gen and manual_any is None:
                    manual_any = t
                elif is_gen and asr_any is None:
                    asr_any = t

        # Priority: 1. manual in lang -> 2. manual in any lang -> 3. ASR in lang -> 4. ASR any / first available
        chosen = manual_target or manual_any or asr_target or asr_any or transcript_list[0]
        chosen_code = getattr(chosen, "language_code", target_norm)
        is_chosen_gen = bool(getattr(chosen, "is_generated", False))

        try:
            entries = chosen.fetch()
        except Exception:
            entries = ytt.fetch(vid, languages=[chosen_code])

        vtt_text = formatter.format_transcript(entries)
        norm_used = normalize_lang_code(chosen_code) or chosen_code
        if vtt_text and "Language:" not in vtt_text[:200]:
            vtt_text = vtt_text.replace("WEBVTT", f"WEBVTT\nLanguage: {norm_used}", 1)
        lang_used = f"{norm_used}-auto" if is_chosen_gen else norm_used
        logger.info(
            "[fetcher] transcript-api OK: %s requested=%s chosen=%s (generated=%s)",
            vid, lang, lang_used, is_chosen_gen,
        )
        return vtt_text, norm_used
    except Exception as e:
        logger.warning("[fetcher] transcript-api error for %s: %s", video_id, e)
        return None, None


# Backward-compatible alias
fetch_transcript_api = fetch_transcript_youtube_api


def fetch_transcript_ytdlp(
    video_id: str, lang: str = "pl", output_dir: str = "."
) -> Tuple[Optional[str], Optional[str]]:
    """Fallback: fetch subtitles via yt-dlp. Returns (vtt_text, language_used).

    Multi-Language support:
      - First tries `--sub-langs {lang}`
      - If no .vtt is downloaded, falls back to downloading original subtitles in main languages:
        `--sub-langs "en.*,de.*,es.*,fr.*,it.*,uk.*,pt.*,pl.*,orig"`
    """
    import sys

    # Support callers passing (video_url, output_dir="data/vtt", lang="pl")
    if lang and (os.path.sep in lang or "/" in lang or lang.startswith("data")):
        output_dir, lang = lang, (output_dir if len(output_dir) <= 5 and output_dir != "." else "pl")

    vid = extract_video_id(video_id)
    url = f"https://www.youtube.com/watch?v={vid}"
    os.makedirs(output_dir, exist_ok=True)

    cookies_file = os.environ.get("YTDLP_COOKIES_FILE", "")
    proxy_url = (os.getenv("YT_PROXY_URL") or os.getenv("WEBSHARE_PROXY_URL") or "").strip()
    sub_lang_specs = [
        lang,
        "en.*,de.*,es.*,fr.*,it.*,uk.*,pt.*,pl.*,orig",
    ]

    for sub_langs in sub_lang_specs:
        cmd_base = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-langs", sub_langs,
            "--sub-format", "vtt",
            "--output", os.path.join(output_dir, f"{vid}.%(ext)s"),
        ]
        if proxy_url:
            cmd_base.extend(["--proxy", proxy_url])
        cmd_base.append(url)

        methods_to_try = []
        if cookies_file and os.path.exists(cookies_file):
            methods_to_try.append(("file", cmd_base + ["--cookies", cookies_file]))

        if sys.platform == "win32":
            methods_to_try.append(("firefox", cmd_base + ["--cookies-from-browser", "firefox"]))
            methods_to_try.append(("chrome", cmd_base + ["--cookies-from-browser", "chrome"]))

        methods_to_try.append(("none", cmd_base))

        for cookies_method, cmd in methods_to_try:
            try:
                logger.info("[fetcher] yt-dlp sub-langs=%r cookies=%s", sub_langs, cookies_method)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                exact_path = os.path.join(output_dir, f"{vid}.{lang}.vtt")
                if os.path.exists(exact_path):
                    with open(exact_path, "r", encoding="utf-8") as f:
                        return f.read(), normalize_lang_code(lang) or lang

                vtt_candidates = sorted(glob.glob(os.path.join(output_dir, f"{vid}.*.vtt")))
                if vtt_candidates:
                    chosen_path = vtt_candidates[0]
                    parts = os.path.basename(chosen_path).split(".")
                    detected_lang = normalize_lang_code(parts[1]) if len(parts) >= 3 else normalize_lang_code(lang)
                    with open(chosen_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.strip():
                        logger.info("[fetcher] yt-dlp matched %s (detected_lang=%s)", chosen_path, detected_lang)
                        return content, detected_lang or lang

                if result.returncode != 0 and cookies_method != "none":
                    logger.warning("[fetcher] yt-dlp cookies method '%s' failed, retrying...", cookies_method)
                    continue

            except Exception as e:
                logger.warning("[fetcher] yt-dlp subtitle error for %s using %s: %s", vid, cookies_method, e)
                if cookies_method != "none":
                    continue

    return None, None


def fetch_transcript_api_v3(
    video_id: str,
    lang: str,
    api_key: str = "",
    access_token: Optional[str] = None,
    oauth_token: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Fetch transcript via YouTube Data API v3 (Captions endpoint).

    When access_token / oauth_token (OAuth 2.0 Bearer token with youtube.force-ssl scope) is provided:
      1. Lists caption tracks via GET /youtube/v3/captions?part=snippet&videoId={video_id}
      2. Orders tracks by priority: manual in lang -> manual any -> ASR in lang -> remaining tracks
      3. Iterates through candidate tracks and downloads VTT via GET /youtube/v3/captions/{caption_id}?tfmt=vtt
         (if one track returns 403/404 or empty, tries the next track)
      4. Works on VPS without Local Runner, including Private & Scheduled videos!
    """
    token = oauth_token or access_token
    try:
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            url = f"https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={video_id}"
            headers["Authorization"] = f"Bearer {token}"
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
            return normalize_lang_code(item_lang) == normalize_lang_code(target)

        manual_lang = []
        asr_lang = []
        manual_any = []
        asr_any = []

        for item in items:
            snip = item.get("snippet", {})
            item_lang = snip.get("language", "")
            track_kind = snip.get("trackKind", "")
            is_asr = track_kind.upper() == "ASR"
            if _lang_matches(item_lang, lang):
                if not is_asr:
                    manual_lang.append(item)
                else:
                    asr_lang.append(item)
            else:
                if not is_asr:
                    manual_any.append(item)
                else:
                    asr_any.append(item)

        ordered_candidates = manual_lang + manual_any + asr_lang + asr_any
        if not ordered_candidates:
            ordered_candidates = items

        for chosen in ordered_candidates:
            caption_id = chosen["id"]
            chosen_snip = chosen.get("snippet", {})
            chosen_lang = normalize_lang_code(chosen_snip.get("language", lang)) or lang

            dl_headers: dict[str, str] = {}
            if token:
                dl_url = f"https://www.googleapis.com/youtube/v3/captions/{caption_id}?tfmt=vtt"
                dl_headers["Authorization"] = f"Bearer {token}"
            else:
                dl_url = f"https://www.googleapis.com/youtube/v3/captions/{caption_id}?tfmt=vtt&key={api_key}"

            try:
                dl_req = urllib.request.Request(dl_url, headers=dl_headers)  # noqa: S310
                with urllib.request.urlopen(dl_req, timeout=20) as resp:  # noqa: S310
                    raw_bytes = resp.read()
                    vtt_text = raw_bytes.decode("utf-8", errors="replace").strip()

                if not vtt_text:
                    logger.warning("[fetcher] API v3 captions returned empty body for %s (caption_id=%s)", video_id, caption_id)
                    continue

                if not vtt_text.startswith("WEBVTT"):
                    vtt_text = f"WEBVTT\nLanguage: {chosen_lang}\n\n{vtt_text}\n"

                logger.info(
                    "[fetcher] API v3 captions OK: %s caption_id=%s lang=%s oauth=%s (%d chars)",
                    video_id, caption_id, chosen_lang, bool(token), len(vtt_text),
                )
                return vtt_text, chosen_lang
            except Exception as dl_exc:
                logger.warning(
                    "[fetcher] API v3 captions download failed for %s caption_id=%s (oauth=%s): %s",
                    video_id, caption_id, bool(token), dl_exc,
                )
                continue
    except Exception as e:
        logger.warning("[fetcher] API v3 captions error for %s (oauth=%s): %s", video_id, bool(token), e)
    return None, None


# ---------------------------------------------------------------------------
# Metadata fetching — YouTube Data API v3 (PRIMARY on VPS)
# ---------------------------------------------------------------------------

def fetch_metadata_api_v3(video_id: str, api_key: str, access_token: str | None = None) -> dict:
    """Fetch video metadata via YouTube Data API v3.

    Uses googleapis.com — NOT blocked on Oracle Cloud VPS.
    When access_token is provided, requests part=snippet,contentDetails,statistics,status
    so Private and Scheduled videos owned by the user's channel are accessible.
    Extracts normalized 2-char `default_audio_language` and `channel_id`.

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

    raw_audio_lang = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or ""
    default_audio_lang = normalize_lang_code(raw_audio_lang)

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
        "default_audio_language": default_audio_lang,
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    logger.info(
        "[fetcher] API v3 OK: %s title=%r channel_id=%s duration=%s views=%s lang=%s privacy=%s",
        video_id, meta["title"][:50], meta["channel_id"], duration_iso_str, meta["view_count"],
        default_audio_lang or "auto", meta["privacy_status"],
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
    vid = extract_video_id(video_id)
    url = f"https://www.youtube.com/watch?v={vid}"
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.warning(
                "[fetcher] yt-dlp metadata error for %s: %s",
                vid, result.stderr[:200]
            )
            return {}
        data = json.loads(result.stdout)
        raw_lang = data.get("language") or data.get("original_language") or ""
        return {
            "video_id": vid,
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
            "default_audio_language": normalize_lang_code(raw_lang),
        }
    except json.JSONDecodeError:
        logger.error("[fetcher] yt-dlp returned invalid JSON for %s", vid)
        return {}
    except FileNotFoundError:
        logger.error("[fetcher] yt-dlp not found — install: pip install yt-dlp")
        return {}
    except Exception as e:
        logger.error("[fetcher] yt-dlp error for %s: %s", vid, e)
        return {}


# Alias for callers expecting fetch_metadata
fetch_metadata = fetch_metadata_ytdlp


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
    """Fetch metadata + transcript for one video. Returns metadata dict with `source_lang`."""
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
        vtt_text, lang_used = fetch_transcript_youtube_api(video_id, lang)
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

    # 5. Detect source_lang and save VTT
    source_lang = detect_transcript_language(
        best_vtt,
        metadata_lang=meta.get("default_audio_language"),
        track_lang=best_lang,
    )
    meta["source_lang"] = source_lang

    if best_vtt:
        effective_lang = normalize_lang_code(best_lang) or source_lang or lang
        vtt_path = os.path.join(output_dir, f"{video_id}.{effective_lang}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(best_vtt)
        logger.info("[fetcher] VTT saved: %s (%d chars, source_lang=%s)", vtt_path, len(best_vtt), source_lang)
        meta["vtt_path"] = vtt_path
        meta["vtt_language"] = effective_lang
    else:
        logger.warning("[fetcher] No transcript available for %s (source_lang=%s)", video_id, source_lang)
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
