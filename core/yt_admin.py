"""YouTube Admin — OAuth write operations on YouTube channel.

Faza 2B: YouTube Description Writer.
Writes enriched descriptions with chapters, keywords, and channel-specific footer
back to YouTube via YouTube Data API v3 (OAuth 2.0).

D6b refactor (2026-06-20, vse-dev-21):
  - All public functions accept optional `channel: dict` parameter
  - Channel config loaded from channels/*.yaml via core.channel
  - OAuth credentials from channel['yt_oauth'] instead of os.environ
  - Hashtags from channel['yt_hashtags'] instead of hardcoded
  - Footer from channel['yt_footer'] instead of hardcoded YT_FOOTER
  - categoryId from channel['yt_category_id'] instead of hardcoded "25"
  - D6b.5: build_description() adds “⏰ KLUCZOWE MOMENTY” from quotes
  - Full backward compat: channel=None → env vars + legacy defaults

D6a (vse-dev-20, 2026-06-20):
  - batch_update_from_registry() now calls update_video_title_and_description()
    instead of deprecated update_video_description().
  - update_video_description() kept for backward compat but marked deprecated.

Usage:
    from core.yt_admin import update_video_title_and_description
    from core.channel import load_channel
    ch = load_channel("prawy-tv")
    ok = update_video_title_and_description("dQw4w9WgXcQ", seo, "https://prawy.pl/art/", channel=ch)
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests  # type: ignore

logger = logging.getLogger(__name__)

# ============================================================
# LEGACY FOOTER — fallback when channel has no yt_footer
# ============================================================

_LEGACY_YT_FOOTER = """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 PRAWY.PL — Niezależne media
🌐 https://prawy.pl
📘 Facebook: https://www.facebook.com/PortalPrawy/
🐦 Twitter/X: https://twitter.com/prawypl
▶️ YouTube: https://www.youtube.com/user/portalprawypl

❤️ WESPRZYJ NASZĄ MISJĘ:
👶 Fundacja S.O.S. Obrony Poczętego Życia
   Nr konta: 32 1140 1010 0000 4777 8600 1001
   KRS: 0000215438
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

# Public alias for backward compat
YT_FOOTER = _LEGACY_YT_FOOTER


# ============================================================
# OAUTH TOKEN MANAGEMENT
# ============================================================

_token_cache: dict = {}


def _get_access_token(channel: Optional[dict] = None) -> str:
    """Get a valid OAuth 2.0 access token, refreshing if expired.

    D6b: Reads credentials from channel['yt_oauth'] if provided,
    falls back to environment variables for backward compat.

    Args:
        channel: Optional channel config dict from channels/*.yaml.

    Returns:
        Valid access token string.

    Raises:
        EnvironmentError: If OAuth credentials are not configured.
        requests.HTTPError: On token refresh failure.
    """
    global _token_cache

    # Use channel-specific cache key to support multiple channels
    cache_key = (channel or {}).get("channel_id", "_default")

    now = time.time()
    cached = _token_cache.get(cache_key, {})
    if cached.get("expires_at", 0) > now + 60:
        return cached["access_token"]

    # Resolve credentials: channel dict > env vars
    if channel and channel.get("yt_oauth"):
        oauth = channel["yt_oauth"]
        client_id = oauth.get("client_id", "")
        client_secret = oauth.get("client_secret", "")
        refresh_token = oauth.get("refresh_token", "")
    else:
        client_id = os.environ.get("YT_CLIENT_ID", "")
        client_secret = os.environ.get("YT_CLIENT_SECRET", "")
        refresh_token = os.environ.get("YT_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError(
            "Missing YouTube OAuth credentials. "
            "Set YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN in .env "
            "or configure yt_oauth in channels/*.yaml"
        )

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()

    data = resp.json()
    _token_cache[cache_key] = {
        "access_token": data["access_token"],
        "expires_at": now + data.get("expires_in", 3600),
    }
    logger.debug("OAuth token refreshed for %s (expires in %ds)", cache_key, data.get("expires_in", 3600))
    return _token_cache[cache_key]["access_token"]


def _auth_headers(channel: Optional[dict] = None) -> dict:
    """Return Authorization headers for YouTube Data API v3 write operations."""
    return {
        "Authorization": f"Bearer {_get_access_token(channel)}",
        "Content-Type": "application/json",
    }


# ============================================================
# HELPERS
# ============================================================

def seconds_to_timestamp(s: int) -> str:
    """Convert seconds to YouTube chapter timestamp format.

    Args:
        s: Time in seconds (integer).

    Returns:
        Timestamp string: "H:MM:SS" (if >= 1h) or "M:SS".

    Examples:
        >>> seconds_to_timestamp(0)   -> "0:00"
        >>> seconds_to_timestamp(75)  -> "1:15"
        >>> seconds_to_timestamp(3661) -> "1:01:01"
    """
    s = int(s)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_hashtags(seo: dict, channel: Optional[dict] = None) -> str:
    """Build #hashtag string from SEO data (max 8 tags).

    D6b: Base tags from channel['yt_hashtags'] if provided,
    falls back to legacy ["#PrawyTV", "#Prawy", "#Polska"].

    Args:
        seo: SEO result dict.
        channel: Optional channel config dict.

    Returns:
        Space-separated hashtag string, e.g. "#PrawyTV #Polska #Polityka".
    """
    # Base tags from channel config or legacy defaults
    if channel and channel.get("yt_hashtags"):
        tags = list(channel["yt_hashtags"])[:3]  # Copy first 3
    else:
        tags = ["#PrawyTV", "#Prawy", "#Polska"]

    keyphrase = seo.get("focus_keyphrase", "")
    if keyphrase:
        tag = "#" + re.sub(r"[^a-zA-Z0-9\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b]", "", keyphrase)
        if 2 < len(tag) < 30 and tag not in tags:
            tags.append(tag)

    title = seo.get("seo_title", "") or seo.get("original_title", "")
    for word in title.split():
        word = word.strip(".,!?-:;()[]'\"\u00ab\u00bb")
        if (
            len(word) >= 4
            and word[0].isupper()
            and word not in ("Prawy", "Studio", "Wi\u0119cej", "Nowe", "Nowy")
        ):
            tag = "#" + re.sub(r"[^a-zA-Z0-9\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b]", "", word)
            if tag not in tags and len(tag) < 25:
                tags.append(tag)
                if len(tags) >= 8:
                    break

    return " ".join(tags[:8])


def _build_intro_with_bullets(seo: dict) -> str:
    """Build a rich merytoryczny intro (800-1200 chars) from SEO data.

    Uses article_body stripped of HTML as the primary intro text (first 2 paragraphs),
    falling back to video_description / lead. Adds 3-5 bullet points from FAQ questions.

    Args:
        seo: SEO result dict from generator.process_video().

    Returns:
        Formatted intro string with merytoryczny wstęp + bullet points.
    """
    # --- Merytoryczny wstęp: pierwsze 2 paragrafy article_body ---
    article_body = seo.get("article_body", "")
    intro_text = ""
    if article_body:
        # Extract paragraphs from HTML
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", article_body, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            # Take first 2 paragraphs, strip HTML
            intro_parts = [_strip_html(p) for p in paragraphs[:2]]
            intro_text = "\n\n".join(p for p in intro_parts if p.strip())

    # Fallback: video_description lub lead
    if not intro_text:
        intro_text = _strip_html(
            seo.get("video_description", "") or seo.get("lead", "")
        )

    # Trim intro do ~600 znaków, nie ciąj w środku zdania
    if len(intro_text) > 600:
        cutoff = intro_text.rfind(".", 400, 600)
        if cutoff > 0:
            intro_text = intro_text[: cutoff + 1]
        else:
            intro_text = intro_text[:600]

    # --- Bullet points z FAQ (3-5 pytań jako wątki) ---
    faq_items = seo.get("faq", [])
    bullets = []
    for item in faq_items[:5]:
        q = _strip_html(item.get("question", "")).strip()
        if q and len(q) < 100:
            # Skróć pytanie do przystępnego wątku (bez znaku zapytania)
            bullet = q.rstrip("?")
            if not bullet.endswith(":"):
                bullet = bullet.rstrip(".")
            bullets.append(f"\u2022 {bullet}")

    result = intro_text
    if bullets:
        result += "\n\nKLUCZOWE W\u0104TKI:\n" + "\n".join(bullets[:5])

    return result


# ============================================================
# D6b.5: KEY MOMENTS — quotes with timestamps for YT description
# ============================================================

def _build_key_moments(seo: dict) -> str:
    """Build '⏰ KLUCZOWE MOMENTY' section from quotes with timestamps.

    CO: Generuje sekcję „KLUCZOWE MOMENTY” z cytatów i ich timestampów.

    PO CO: YouTube i widzowie lubią mieć kluczowe cytaty z timestampami
           w opisie. To te same dane co w JSON-LD na stronie (Clip schema).

    JAK: Iteruje po seo['quotes'], każdy ma 'time' (sekundy) i 'text'.
         Formatuje jako lista timestamp — „cytat...”. Max 5 momentów.

    Args:
        seo: SEO result dict from generator.process_video().

    Returns:
        Formatted string with key moments, or empty string if no quotes.
    """
    quotes = seo.get("quotes", [])
    if not quotes:
        return ""

    moments = []
    for q in quotes[:5]:
        t = q.get("time", 0)
        text = _strip_html(q.get("text", "")).strip()
        if not text:
            continue
        # Truncate long quotes for YT description readability
        if len(text) > 80:
            cutoff = text.rfind(" ", 50, 80)
            if cutoff > 0:
                text = text[:cutoff] + "\u2026"
            else:
                text = text[:80] + "\u2026"
        ts = seconds_to_timestamp(int(t))
        # Pad timestamp to HH:MM:SS for consistency
        moments.append(f"{ts} \u2014 \u201e{text}\u201d")

    if not moments:
        return ""

    return "\u23f0 KLUCZOWE MOMENTY\n" + "\n".join(moments)


# ============================================================
# BUILD DESCRIPTION
# ============================================================

def build_description(
    seo: dict,
    wp_url: str,
    original_description: str = "",
    channel: Optional[dict] = None,
) -> str:
    """Build enriched YouTube video description from SEO data.

    D6b: Uses channel config for footer and hashtags if provided.
    D6b.5: Adds '⏰ KLUCZOWE MOMENTY' section from quotes.

    Format:
        [Merytoryczny wstęp + bullet points]

        🔗 Pełny artykuł: [wp_url]

        ⏱️ ROZDZIAŁY:
        0:00 Intro
        ...

        ⏰ KLUCZOWE MOMENTY
        0:03:15 — „Cytat...”

        🔑 TEMATY: keyphrase

        [Oryginalny opis YouTube]

        [Footer from channel config]

        #Hashtagi

    Args:
        seo: SEO result dict from generator.process_video().
        wp_url: Full URL of the article.
        original_description: Current YouTube description (preserved).
        channel: Optional channel config dict from channels/*.yaml.

    Returns:
        Full description string (trimmed to 4900 chars if needed).
    """
    parts = []

    # --- Merytoryczny wstęp z bullet points (800-1200 znaków) ---
    intro_block = _build_intro_with_bullets(seo)
    if intro_block:
        parts.append(intro_block)

    # --- Link do artykułu (wyeksponowany) ---
    if wp_url:
        parts.append(f"\ud83d\udd17 Pe\u0142ny artyku\u0142 z transkryptem i analiz\u0105:\n{wp_url}")

    # --- Rozdziały (REQUIRED for YouTube chapters to work) ---
    chapters = seo.get("chapters", [])
    if chapters:
        chapter_lines = ["\u23f1\ufe0f ROZDZIA\u0141Y:"]
        for ch in chapters:
            ts = seconds_to_timestamp(int(ch["time"]))
            chapter_lines.append(f"{ts} {ch['label']}")
        parts.append("\n".join(chapter_lines))

    # --- D6b.5: Kluczowe momenty (cytaty z timestamps) ---
    key_moments = _build_key_moments(seo)
    if key_moments:
        parts.append(key_moments)

    # --- Tematy / Frazy kluczowe ---
    keywords = []
    keyphrase = seo.get("focus_keyphrase", "")
    if keyphrase:
        keywords.append(keyphrase)
    for faq_item in seo.get("faq", [])[: 3]:
        q = _strip_html(faq_item.get("question", ""))
        if q and len(q) < 80:
            keywords.append(q)
    if keywords:
        parts.append("\ud83d\udd11 TEMATY: " + " \u2022 ".join(keywords))

    # --- Oryginalny opis (zachowany, bez istniej\u0105cej stopki) ---
    orig = original_description.strip()
    if "\u2501\u2501\u2501" in orig:
        orig = orig[: orig.index("\u2501\u2501\u2501")].strip()
    if orig:
        parts.append(orig)

    # --- Footer from channel config or legacy ---
    if channel and channel.get("yt_footer"):
        footer = channel["yt_footer"].strip()
    else:
        footer = _LEGACY_YT_FOOTER
    parts.append(footer)

    # --- Hashtagi ---
    parts.append(_build_hashtags(seo, channel))

    description = "\n\n".join(parts)

    # YouTube limit: 5000 chars
    if len(description) > 4900:
        logger.warning(
            "Description truncated to 4900 chars (was %d) for SEO compliance.",
            len(description),
        )
        description = description[:4900] + "\u2026"

    return description


# ============================================================
# FETCH CURRENT VIDEO DATA FROM YOUTUBE
# ============================================================

def get_video_data(video_id: str, channel: Optional[dict] = None) -> dict:
    """Fetch current video snippet + liveStreamingDetails from YouTube API.

    Used before update to preserve required fields (title, categoryId, tags).
    Also returns scheduling info (scheduledStartTime for premieres).

    Args:
        video_id: YouTube video ID.
        channel: Optional channel config dict.

    Returns:
        Full video resource dict (items[0]).

    Raises:
        ValueError: If video not found or not accessible.
        requests.HTTPError: On API error.
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,liveStreamingDetails,status", "id": video_id}

    resp = requests.get(url, headers=_auth_headers(channel), params=params, timeout=15)
    resp.raise_for_status()

    items = resp.json().get("items", [])
    if not items:
        raise ValueError(f"Video not found or not accessible: {video_id}")

    return items[0]


# ============================================================
# UPDATE VIDEO DESCRIPTION ON YOUTUBE (DEPRECATED)
# ============================================================

def update_video_description(
    video_id: str,
    seo: dict,
    wp_url: str,
    dry_run: bool = False,
    channel: Optional[dict] = None,
) -> bool:
    """Fetch current snippet and write enriched description to YouTube.

    .. deprecated::
        Use update_video_title_and_description() instead for quota efficiency.
        This function is kept for backward compatibility only.
    """
    logger.warning(
        "update_video_description() is deprecated \u2014 use update_video_title_and_description() instead"
    )
    try:
        video_data = get_video_data(video_id, channel)
    except Exception as exc:
        logger.error("get_video_data failed for %s: %s", video_id, exc)
        return False

    snippet = video_data.get("snippet", {})
    original_description = snippet.get("description", "")
    category_id = (channel or {}).get("yt_category_id", snippet.get("categoryId", "25"))

    new_description = build_description(seo, wp_url, original_description, channel)

    if dry_run:
        logger.info(
            "DRY RUN \u2014 description for %s (%d chars):\n%s\u2026",
            video_id, len(new_description), new_description[:400],
        )
        return True

    update_body = {
        "id": video_id,
        "snippet": {
            "title": snippet.get("title", ""),
            "description": new_description,
            "categoryId": category_id,
            "defaultLanguage": snippet.get("defaultLanguage", "pl"),
            "defaultAudioLanguage": snippet.get("defaultAudioLanguage", "pl"),
        },
    }
    if snippet.get("tags"):
        update_body["snippet"]["tags"] = snippet["tags"]

    api_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet"
    try:
        resp = requests.put(
            api_url,
            headers=_auth_headers(channel),
            json=update_body,
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info("\u2705 YouTube description updated: %s", video_id)
            return True
        logger.error(
            "YouTube update FAIL for %s: HTTP %s | %s",
            video_id, resp.status_code, resp.text[:400],
        )
        return False
    except Exception as exc:
        logger.error("YouTube update exception for %s: %s", video_id, exc)
        return False


# ============================================================
# UPDATE VIDEO TITLE + DESCRIPTION — single API call (quota opt)
# ============================================================

def update_video_title_and_description(
    video_id: str,
    seo: dict,
    wp_url: str,
    dry_run: bool = False,
    channel: Optional[dict] = None,
) -> bool:
    """Update YouTube video title AND description in a single API call.

    D6b: Uses channel config for OAuth, footer, hashtags, categoryId.

    Quota optimization: videos.update costs 50 units regardless of whether
    we update title only, description only, or both. Always combine.

    Args:
        video_id: YouTube video ID.
        seo: SEO result dict from generator.process_video(). Must contain
             'yt_title' (str, max 100 chars) and fields for build_description().
        wp_url: Full URL of the corresponding WordPress article.
        dry_run: If True, log only without making API calls.
        channel: Optional channel config dict from channels/*.yaml.

    Returns:
        True on success or dry_run, False on API failure.

    Raises:
        EnvironmentError: If OAuth credentials are not configured.
    """
    try:
        video_data = get_video_data(video_id, channel)
    except Exception as exc:
        logger.error("get_video_data failed for %s: %s", video_id, exc)
        return False

    snippet = video_data.get("snippet", {})
    original_description = snippet.get("description", "")
    category_id = (channel or {}).get("yt_category_id", snippet.get("categoryId", "25"))

    yt_title = seo.get("yt_title", "").strip()
    if not yt_title:
        # Fallback: use existing YT title (description-only update)
        yt_title = snippet.get("title", "")
        logger.warning(
            "yt_title missing in seo dict for %s \u2014 preserving existing title", video_id
        )

    if len(yt_title) > 100:
        logger.warning(
            "yt_title truncated from %d to 100 chars for %s", len(yt_title), video_id
        )
        yt_title = yt_title[:100]

    new_description = build_description(seo, wp_url, original_description, channel)

    logger.info("YT title+desc update: %s -> %r", video_id, yt_title[:60])

    if dry_run:
        logger.info(
            "DRY RUN \u2014 YT update for %s:\n  title: %r\n  desc (%d chars): %s\u2026",
            video_id, yt_title, len(new_description), new_description[:200],
        )
        return True

    update_body = {
        "id": video_id,
        "snippet": {
            "title": yt_title,
            "description": new_description,
            "categoryId": category_id,
            "defaultLanguage": snippet.get("defaultLanguage", "pl"),
            "defaultAudioLanguage": snippet.get("defaultAudioLanguage", "pl"),
        },
    }
    if snippet.get("tags"):
        update_body["snippet"]["tags"] = snippet["tags"]

    api_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet"
    try:
        resp = requests.put(
            api_url,
            headers=_auth_headers(channel),
            json=update_body,
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info(
                "\u2705 YouTube title+description updated: %s | title=%r",
                video_id, yt_title[:60],
            )
            return True
        logger.error(
            "YouTube update FAIL for %s: HTTP %s | %s",
            video_id, resp.status_code, resp.text[:400],
        )
        return False
    except Exception as exc:
        logger.error("YouTube update exception for %s: %s", video_id, exc)
        return False


# ============================================================
# BATCH UPDATE — from registry
# ============================================================

def batch_update_from_registry(
    registry_dir: Path,
    seo_dir: Path,
    wp_base_url: str,
    dry_run: bool = False,
    delay_between: float = 2.0,
    channel: Optional[dict] = None,
) -> dict:
    """Update YouTube title + descriptions for all videos in the registry.

    D6b: Accepts optional channel config for multi-channel support.

    Args:
        registry_dir: Path to registry/ directory.
        seo_dir: Path to seo_results/ directory with SEO JSON files.
        wp_base_url: WordPress base URL (e.g. 'https://prawy.pl').
        dry_run: If True, skip actual YouTube API calls.
        delay_between: Seconds to wait between consecutive API calls.
        channel: Optional channel config dict from channels/*.yaml.

    Returns:
        Stats dict: {total, success, failed, skipped}.
    """
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    registry_files = sorted(registry_dir.glob("*.json"))
    logger.info(
        "Batch YT title+description update: %d registry entries | dry_run=%s",
        len(registry_files), dry_run,
    )

    for idx, reg_file in enumerate(registry_files, start=1):
        video_id = reg_file.stem
        stats["total"] += 1

        try:
            reg = json.loads(reg_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[%d/%d] Skip %s: registry read error: %s",
                           idx, len(registry_files), video_id, exc)
            stats["skipped"] += 1
            continue

        # Idempotency: skip if already updated (unless dry_run)
        if reg.get("yt_desc_updated") and not dry_run:
            logger.info("[%d/%d] Skip %s: already yt_updated at %s",
                        idx, len(registry_files), video_id, reg["yt_desc_updated"])
            stats["skipped"] += 1
            continue

        seo_file = seo_dir / f"{video_id}.json"
        if not seo_file.exists():
            logger.warning("[%d/%d] Skip %s: SEO JSON not found at %s",
                           idx, len(registry_files), video_id, seo_file)
            stats["skipped"] += 1
            continue

        try:
            seo = json.loads(seo_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[%d/%d] Skip %s: SEO JSON parse error: %s",
                           idx, len(registry_files), video_id, exc)
            stats["skipped"] += 1
            continue

        wp_id = reg.get("wp_post_id")
        # Try to build canonical URL from WP id; fallback to /?p=
        wp_url = f"{wp_base_url.rstrip('/')}/?p={wp_id}" if wp_id else wp_base_url

        logger.info(
            "[%d/%d] Updating %s (WP#%s) \u2014 %s",
            idx, len(registry_files), video_id, wp_id,
            seo.get("seo_title", "")[:50],
        )

        ok = update_video_title_and_description(video_id, seo, wp_url, dry_run, channel)

        if ok:
            stats["success"] += 1
            if not dry_run:
                reg["yt_desc_updated"] = datetime.now(timezone.utc).isoformat()
                reg_file.write_text(
                    json.dumps(reg, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        else:
            stats["failed"] += 1

        if delay_between > 0 and not dry_run:
            time.sleep(delay_between)

    logger.info(
        "Batch done: total=%d success=%d failed=%d skipped=%d",
        stats["total"], stats["success"], stats["failed"], stats["skipped"],
    )
    return stats
