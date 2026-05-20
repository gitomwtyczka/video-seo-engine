"""WordPress REST API Injector — write JSON-LD schema + rich content to WP posts.

Migrated from: inject_rest_v5.py (shadow-perihelion / D:\\Biblioteki\\prawy.pl)
Migration by: vse-architect-01 | DISPATCH-VSE-ARCHITECT-02 | 2026-05-13

Responsibilities:
  - Fetch upload date from WP REST API (get_post_date)
  - Fetch YouTube view count via Data API v3 (get_youtube_view_count)
  - Download & upload YouTube thumbnail as WP featured image (set_youtube_thumbnail)
  - Build VideoObject + Clip[] + FAQPage + Quotation JSON-LD (build_schema_jsonld)
  - Build full post content with WP blocks + seekTo JS (build_post_content)
  - PATCH WP post via REST API (update_post)

Safety rules:
  - NEVER hardcode credentials — all from environment / args
  - NEVER overwrite post content outside the JSON-LD script block
  - Always verify WP REST API response code (check 200, not just no exception)
  - Dry-run mode: --dry-run flag skips actual PATCH

Dependencies:
  pip install requests python-dotenv
"""
import json
import logging
import os
import re
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


# ============================================================
# PLAYER JAVASCRIPT — seekTo via postMessage
# ============================================================


def _build_player_js(seek_fn: str = "prawySeek", chapter_class: str = "prawy-chapter") -> str:
    """Build the seekTo player JavaScript with profile-specific identifiers.

    Args:
        seek_fn: Name of the global JS seek function (e.g. 'prawySeek', 'vseSeek').
        chapter_class: CSS class selector for chapter links (e.g. 'prawy-chapter').

    Returns:
        HTML <script> block string.
    """
    return f"""<script>
(function(){{
  var iframe = document.querySelector('iframe[src*="youtube.com"]');
  if(!iframe) return;
  var src = iframe.src;
  if(src.indexOf('enablejsapi=1') === -1){{
    iframe.src = src + (src.indexOf('?')>-1?'&':'?') + 'enablejsapi=1';
  }}
  window.{seek_fn} = function(seconds){{
    iframe.contentWindow.postMessage(JSON.stringify({{
      event:'command', func:'seekTo', args:[seconds, true]
    }}), '*');
    iframe.contentWindow.postMessage(JSON.stringify({{
      event:'command', func:'playVideo', args:[]
    }}), '*');
    iframe.scrollIntoView({{behavior:'smooth', block:'center'}});
  }};
  document.querySelectorAll('.{chapter_class}').forEach(function(el){{
    el.addEventListener('click', function(e){{
      e.preventDefault();
      var t = parseInt(this.getAttribute('data-time'));
      window.{seek_fn}(t);
    }});
  }});
}})();
</script>"""


# Legacy constant — backward compat for callers that import PLAYER_JS directly
PLAYER_JS = _build_player_js(seek_fn="prawySeek", chapter_class="prawy-chapter")


# ============================================================
# HELPERS
# ============================================================

def _strip_html(html: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", html).strip()


def _make_auth(wp_user: str, wp_app_pass: str) -> HTTPBasicAuth:
    """Build HTTPBasicAuth from credentials."""
    return HTTPBasicAuth(wp_user, wp_app_pass)


def _build_rankmath_meta(seo: dict) -> dict:
    """Build RankMath SEO meta fields dict (used for update_rankmath_meta).

    Returns a dict with keys: rank_math_focus_keyword, rank_math_description,
    rank_math_title. Empty values are omitted.
    """
    focus_keyword = seo.get("focus_keyphrase", "").strip()
    lead_plain = _strip_html(seo.get("lead", ""))
    meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain
    seo_title = seo.get("seo_title", "").strip()
    meta: dict = {}
    if focus_keyword:
        meta["rank_math_focus_keyword"] = focus_keyword
    if meta_desc:
        meta["rank_math_description"] = meta_desc
    if seo_title:
        meta["rank_math_title"] = seo_title
    if meta:
        logger.info("  RankMath: keyphrase=%r title=%r", focus_keyword[:40], seo_title[:40])
    return meta


def update_rankmath_meta(
    wp_id: int,
    seo: dict,
    wp_base_url: str,
    auth: HTTPBasicAuth,
) -> bool:
    """Push SEO meta to RankMath via its dedicated REST endpoint.

    WP REST API's standard ``meta`` field silently ignores RankMath keys
    (only 'footnotes' is returned). The correct approach is the
    ``rankmath/v1/updateMeta`` endpoint which accepts objectType + objectID + meta.

    Verified live on prawy.pl: POST rankmath/v1/updateMeta returns
    ``{"slug": true, ...}`` on success.

    Args:
        wp_id: WordPress post ID.
        seo: SEO result dict from generator.process_video().
        wp_base_url: WordPress site base URL.
        auth: HTTPBasicAuth instance.

    Returns:
        True if RankMath accepted the update, False otherwise.
    """
    rankmath_meta = _build_rankmath_meta(seo)
    if not rankmath_meta:
        logger.warning("  RankMath: no meta to update for WP#%s (empty focus_keyphrase?)", wp_id)
        return False

    url = f"{wp_base_url.rstrip('/')}/wp-json/rankmath/v1/updateMeta"
    payload = {
        "objectType": "post",
        "objectID": wp_id,
        "meta": rankmath_meta,
    }
    try:
        resp = requests.post(url, json=payload, auth=auth, timeout=20)
        data = resp.json()
        if resp.status_code == 200 and data.get("slug") is True:
            logger.info(
                "  RankMath OK: WP#%s | keyphrase=%r",
                wp_id, rankmath_meta.get("rank_math_focus_keyword", "-")[:40],
            )
            return True
        logger.error(
            "  RankMath FAIL WP#%s: HTTP %s | %s",
            wp_id, resp.status_code, str(data)[:200],
        )
        return False
    except Exception as exc:
        logger.error("  RankMath exception WP#%s: %s", wp_id, exc)
        return False


# ============================================================
# FETCH POST DATE FROM WP REST API
# ============================================================

def get_post_date(wp_id: int, wp_base_url: str, auth: HTTPBasicAuth) -> str:
    """Fetch the post's publication date from WordPress REST API.

    Args:
        wp_id: WordPress post ID.
        wp_base_url: Base URL of the WordPress site (e.g. 'https://prawy.pl').
        auth: HTTPBasicAuth instance.

    Returns:
        ISO 8601 datetime string with timezone, e.g. '2026-01-15T10:00:00+01:00'.
        Falls back to '2024-01-01T00:00:00+00:00' on error.
    """
    url = f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}"
    try:
        resp = requests.get(url, auth=auth, timeout=15)
        if resp.status_code == 200:
            date_val = resp.json().get("date", "2024-01-01T00:00:00")
            # Ensure timezone is present
            if "T" in date_val and "+" not in date_val and "Z" not in date_val:
                return date_val + "+00:00"
            return date_val
        logger.warning("get_post_date WP#%s: HTTP %s", wp_id, resp.status_code)
    except Exception as exc:
        logger.error("get_post_date WP#%s: %s", wp_id, exc)
    return "2024-01-01T00:00:00+00:00"


# ============================================================
# FETCH VIEW COUNT FROM YOUTUBE DATA API v3
# ============================================================

def get_youtube_view_count(yt_id: str, yt_api_key: Optional[str] = None) -> Optional[int]:
    """Fetch view count from YouTube Data API v3.

    Args:
        yt_id: YouTube video ID.
        yt_api_key: YouTube Data API key. Falls back to YT_API_KEY env var.

    Returns:
        View count as int, or None if unavailable / no API key.
    """
    api_key = yt_api_key or os.environ.get("YT_API_KEY", "")
    if not api_key:
        logger.debug("YT_API_KEY not set — skipping view count for %s", yt_id)
        return None
    try:
        url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?id={yt_id}&part=statistics&key={api_key}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                return int(items[0]["statistics"].get("viewCount", 0))
    except Exception as exc:
        logger.warning("get_youtube_view_count %s: %s", yt_id, exc)
    return None


# ============================================================
# SET YOUTUBE THUMBNAIL AS FEATURED IMAGE
# ============================================================

def _set_media_alt(media_id: int, alt_text: str, title: str, wp_base_url: str, auth: HTTPBasicAuth) -> None:
    """PATCH WP media item to set alt_text and title."""
    try:
        requests.post(
            f"{wp_base_url}/wp-json/wp/v2/media/{media_id}",
            json={"alt_text": alt_text, "title": title},
            auth=auth,
            timeout=10,
        )
        logger.info("  THUMB ALT: set alt_text=%r", alt_text[:60])
    except Exception as exc:
        logger.warning("  THUMB ALT: could not set alt_text: %s", exc)


def set_youtube_thumbnail(
    wp_id: int,
    yt_id: str,
    post_title: str,
    wp_base_url: str,
    auth: HTTPBasicAuth,
    alt_text: str = "",
) -> Optional[int]:
    """Download YouTube thumbnail, set as featured image, and set ALT text with focus keyphrase."""
    """Download YouTube thumbnail and set it as the WP post's featured image.

    Tries maxresdefault → hqdefault → mqdefault. Deduplicates uploads
    by checking if a media item with the same filename already exists.

    Args:
        wp_id: WordPress post ID.
        yt_id: YouTube video ID.
        post_title: Post title (used for logging only).
        wp_base_url: Base URL of the WordPress site.
        auth: HTTPBasicAuth instance.

    Returns:
        WP media ID (int) on success, or None on failure.
    """
    img_resp = None
    for quality in ["maxresdefault", "hqdefault", "mqdefault"]:
        thumb_url = f"https://img.youtube.com/vi/{yt_id}/{quality}.jpg"
        r = requests.get(thumb_url, timeout=15)
        if r.status_code == 200 and len(r.content) > 5000:
            img_resp = r
            logger.info("  THUMB: downloaded %s (%s)", quality, yt_id)
            break

    if not img_resp:
        logger.warning("  THUMB: could not download for %s", yt_id)
        return None

    filename = f"prawy-tv-{yt_id}.jpg"

    # Dedup: check if already uploaded
    search_url = f"{wp_base_url}/wp-json/wp/v2/media?search=prawy-tv-{yt_id}&per_page=1"
    try:
        existing = requests.get(search_url, auth=auth, timeout=10)
        if existing.status_code == 200 and existing.json():
            media_id = existing.json()[0]["id"]
            requests.post(
                f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}",
                json={"featured_media": media_id},
                auth=auth,
                timeout=15,
            )
            if alt_text:
                _set_media_alt(media_id, alt_text, post_title, wp_base_url, auth)
            logger.info("  THUMB: reuse existing media #%s", media_id)
            return media_id
    except Exception as exc:
        logger.warning("  THUMB dedup check failed: %s", exc)

    # Upload
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/jpeg",
    }
    try:
        upload_resp = requests.post(
            f"{wp_base_url}/wp-json/wp/v2/media",
            headers=headers,
            data=img_resp.content,
            auth=auth,
            timeout=30,
        )
        if upload_resp.status_code == 201:
            media_id = upload_resp.json()["id"]
            set_resp = requests.post(
                f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}",
                json={"featured_media": media_id},
                auth=auth,
                timeout=15,
            )
            if set_resp.status_code == 200:
                if alt_text:
                    _set_media_alt(media_id, alt_text, post_title, wp_base_url, auth)
                logger.info("  THUMB: uploaded + set as featured (media #%s)", media_id)
                return media_id
        logger.warning("  THUMB: upload failed HTTP %s", upload_resp.status_code)
    except Exception as exc:
        logger.error("  THUMB: upload exception: %s", exc)
    return None


# ============================================================
# BUILD SCHEMA JSON-LD — VideoObject + Clip + FAQPage + Quotation
# ============================================================

def build_schema_jsonld(
    seo: dict,
    yt_id: str,
    upload_date: str,
    yt_api_key: Optional[str] = None,
) -> list[dict]:
    """Build the full JSON-LD schema list for a video post.

    Produces: VideoObject (with optional interactionStatistic + hasPart clips),
    FAQPage (if faq present), Quotation per polished quote.

    Note: Quotation schema is kept for completeness; Google does not render it.
    Do NOT add new Quotation items — preserve existing if already injected.

    Args:
        seo: SEO result dict from generator.process_video().
        yt_id: YouTube video ID.
        upload_date: ISO 8601 datetime string with timezone.
        yt_api_key: Optional YouTube Data API key for live view count fetch.

    Returns:
        List of schema dicts (each is a separate JSON-LD block).
    """
    chapters = seo.get("chapters", [])
    total_dur = seo.get("total_duration", 0)
    yt_url = seo.get("yt_url", f"https://www.youtube.com/watch?v={yt_id}")

    # ISO 8601 duration
    dur_h = total_dur // 3600
    dur_m = (total_dur % 3600) // 60
    dur_s = total_dur % 60
    iso_dur = seo.get("duration_iso") or (
        f"PT{dur_h}H{dur_m}M{dur_s}S" if dur_h else f"PT{dur_m}M{dur_s}S"
    )

    # Clips (hasPart)
    clips: list[dict] = []
    for i, ch in enumerate(chapters):
        end_time = chapters[i + 1]["time"] if i + 1 < len(chapters) else total_dur
        clips.append({
            "@type": "Clip",
            "name": ch["label"],
            "startOffset": ch["time"],
            "endOffset": end_time,
            "url": f"{yt_url}&t={ch['time']}s",
        })

    # Ensure uploadDate has timezone
    if "T" in upload_date and "+" not in upload_date and "Z" not in upload_date:
        upload_date = upload_date + "+00:00"

    video_schema: dict = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": seo.get("seo_title", ""),
        "description": seo.get("video_description", ""),
        "thumbnailUrl": f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg",
        "uploadDate": upload_date,
        "contentUrl": yt_url,
        "embedUrl": f"https://www.youtube.com/embed/{yt_id}",
        "duration": iso_dur,
    }
    if clips:
        video_schema["hasPart"] = clips

    # interactionStatistic — prefer cached value, fallback to live API call
    view_count = seo.get("view_count") or get_youtube_view_count(yt_id, yt_api_key)
    if view_count:
        video_schema["interactionStatistic"] = {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/WatchAction",
            "userInteractionCount": int(view_count),
        }

    schemas: list[dict] = [video_schema]

    # FAQPage
    faq_items = []
    for faq in seo.get("faq", []):
        faq_items.append({
            "@type": "Question",
            "name": faq["question"],
            "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]},
        })
    if faq_items:
        schemas.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items,
        })

    # Quotation — kept for completeness, NOT added to new posts by default
    for q in seo.get("quotes", []):
        t = q.get("time", 0)
        schemas.append({
            "@context": "https://schema.org",
            "@type": "Quotation",
            "text": q["text"],
            "creator": {"@type": "Person", "name": q["speaker"]},
            "citation": f"{yt_url}&t={int(t)}s",
        })

    return schemas


# ============================================================
# BUILD POST CONTENT — WP blocks + seekTo JS
# ============================================================

def build_post_content(
    seo: dict,
    yt_id: str,
    upload_date: str,
    yt_api_key: Optional[str] = None,
    profile: Optional[dict] = None,
) -> str:
    """Build full WordPress post content with blocks, schema JSON-LD, and seekTo JS.

    Produces: lead paragraph → <!-- more --> → YT embed → chapters list →
    article body → polished quotes → FAQ collapsible → JSON-LD schemas → player JS.

    Args:
        seo: SEO result dict from generator.process_video().
        yt_id: YouTube video ID.
        upload_date: ISO 8601 datetime string with timezone.
        yt_api_key: Optional YouTube Data API key for view count.
        profile: Optional portal profile dict. If None, uses Prawy.pl defaults.

    Returns:
        Full WP post content string (Gutenberg block syntax).
    """
    # Resolve profile-specific identifiers (backward compat defaults)
    seo_cfg = (profile or {}).get("seo", {})
    chapter_class = seo_cfg.get("chapter_js_class", "prawy-chapter")
    seek_fn = seo_cfg.get("seek_fn_name", "prawySeek")
    lead_html = seo["lead"]
    article_body = seo["article_body"]
    chapters = seo.get("chapters", [])
    quotes = seo.get("quotes", [])
    faq = seo.get("faq", [])
    yt_url = seo.get("yt_url", f"https://www.youtube.com/watch?v={yt_id}")

    # Lead block
    lead_block = (
        f"<!-- wp:paragraph -->\n<p>{lead_html}</p>\n<!-- /wp:paragraph -->\n\n"
        f"<!-- wp:more -->\n<!--more-->\n<!-- /wp:more -->"
    )

    # YouTube embed
    embed_json = json.dumps({
        "url": yt_url, "type": "video", "providerNameSlug": "youtube",
        "responsive": True, "className": "wp-embed-aspect-16-9 wp-has-aspect-ratio",
    })
    embed_block = (
        f'<!-- wp:embed {embed_json} -->\n'
        f'<figure class="wp-block-embed is-type-video is-provider-youtube '
        f'wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio">'
        f'<div class="wp-block-embed__wrapper">\n{yt_url}\n</div></figure>\n'
        f"<!-- /wp:embed -->"
    )

    # Chapters list with seekTo (uses profile chapter_class)
    ch_items = []
    for ch in chapters:
        t = ch["time"]
        m = int(t // 60)
        s = int(t % 60)
        ch_items.append(
            f'<li><a href="#" class="{chapter_class}" data-time="{int(t)}">'
            f"<strong>{m:02d}:{s:02d}</strong> \u2014 {ch['label']}</a></li>"
        )
    chapters_block = ""
    if ch_items:
        chapters_block = (
            "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">Rozdzia\u0142y nagrania</h2>\n<!-- /wp:heading -->\n\n"
            f"<!-- wp:list -->\n<ul class=\"{chapter_class}s-list\">\n"
            + "\n".join(ch_items)
            + "\n</ul>\n<!-- /wp:list -->"
        )

    # Article body
    article_block = f"<!-- wp:html -->\n{article_body}\n<!-- /wp:html -->"

    # Polished quotes with seekTo links
    quotes_blocks = []
    for q in quotes:
        t = q.get("time", 0)
        m = int(t // 60)
        s = int(t % 60)
        quotes_blocks.append(
            f'<!-- wp:quote -->\n'
            f'<blockquote class="wp-block-quote"><p>{q["text"]}</p>'
            f'<cite>\u2014 {q["speaker"]} '
            f'(<a href="#" class="prawy-chapter" data-time="{int(t)}">{m:02d}:{s:02d}</a>)'
            f"</cite></blockquote>\n<!-- /wp:quote -->"
        )
    quotes_section = ""
    if quotes_blocks:
        quotes_section = (
            "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">Kluczowe cytaty</h2>\n<!-- /wp:heading -->\n\n"
            + "\n".join(quotes_blocks)
        )

    # FAQ collapsible
    faq_blocks = []
    for item in faq:
        faq_blocks.append(
            f'<details><summary><strong>{item["question"]}</strong></summary>'
            f'<p>{item["answer"]}</p></details>'
        )
    faq_section = ""
    if faq_blocks:
        faq_section = (
            "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">Najcz\u0119\u015bciej zadawane pytania</h2>\n<!-- /wp:heading -->\n\n"
            f"<!-- wp:html -->\n" + "\n".join(faq_blocks) + "\n<!-- /wp:html -->"
        )

    # JSON-LD schemas
    schemas = build_schema_jsonld(seo, yt_id, upload_date, yt_api_key)
    schema_block = ""
    for s in schemas:
        schema_json = json.dumps(s, ensure_ascii=False, indent=2)
        schema_block += (
            f'\n<!-- wp:html -->\n<script type="application/ld+json">\n'
            f"{schema_json}\n</script>\n<!-- /wp:html -->"
        )

    # Player JS — use profile identifiers (seek_fn, chapter_class)
    player_js = _build_player_js(seek_fn=seek_fn, chapter_class=chapter_class)
    js_block = f"<!-- wp:html -->\n{player_js}\n<!-- /wp:html -->"

    parts = [
        lead_block, embed_block, chapters_block,
        article_block, quotes_section, faq_section,
        schema_block, js_block,
    ]
    return "\n\n".join(p for p in parts if p)


# ============================================================
# UPDATE POST — REST API PATCH
# ============================================================

def update_post(
    wp_id: int,
    seo: dict,
    yt_id: str,
    wp_base_url: str,
    auth: HTTPBasicAuth,
    yt_api_key: Optional[str] = None,
    dry_run: bool = False,
    profile: Optional[dict] = None,
) -> tuple[int, str]:
    """Fetch uploadDate and inject full content to a WordPress post.

    Args:
        wp_id: WordPress post ID.
        seo: SEO result dict from generator.process_video().
        yt_id: YouTube video ID.
        wp_base_url: WordPress site base URL.
        auth: HTTPBasicAuth instance.
        yt_api_key: Optional YouTube Data API key for view count.
        dry_run: If True, skip actual PATCH and return (0, 'DRY_RUN').
        profile: Optional portal profile dict for multi-tenant customization.

    Returns:
        Tuple of (http_status_code, post_url_or_message).
    """
    upload_date = get_post_date(wp_id, wp_base_url, auth)
    logger.info("  uploadDate: %s", upload_date)

    content = build_post_content(seo, yt_id, upload_date, yt_api_key, profile=profile)
    excerpt = _strip_html(seo["lead"])

    if dry_run:
        rankmath_meta = _build_rankmath_meta(seo)
        logger.info("  DRY RUN — skipping PATCH for WP#%s", wp_id)
        logger.info("  Would set: keyphrase=%r", rankmath_meta.get("rank_math_focus_keyword", "-"))
        return 0, "DRY_RUN"

    url = f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}"
    # NOTE: WP REST 'meta' field silently ignores rank_math_* keys —
    # use update_rankmath_meta() separately for the correct endpoint.
    payload: dict = {"content": content, "excerpt": excerpt}
    try:
        resp = requests.post(url, json=payload, auth=auth, timeout=30)
        link = resp.json().get("link", "?")
        logger.info("  REST API: %s | %s", resp.status_code, link)
        if resp.status_code != 200:
            logger.error("  PATCH failed for WP#%s: %s", wp_id, resp.text[:300])
        return resp.status_code, link
    except Exception as exc:
        logger.error("  update_post WP#%s exception: %s", wp_id, exc)
        raise


# ============================================================
# FULL INJECTION PIPELINE — thumbnail + content
# ============================================================

def inject_video(
    wp_id: int,
    yt_id: str,
    seo: dict,
    wp_base_url: str,
    wp_user: str,
    wp_app_pass: str,
    yt_api_key: Optional[str] = None,
    dry_run: bool = False,
    skip_thumbnail: bool = False,
    profile: Optional[dict] = None,
) -> dict:
    """Run the full injection pipeline for a single video post.

    Steps: thumbnail → WP content/excerpt → RankMath meta → YT description.
    YT description update is skipped gracefully if OAuth not configured or
    the video does not belong to the authenticated channel (403).

    Args:
        wp_id: WordPress post ID.
        yt_id: YouTube video ID.
        seo: SEO result dict from generator.process_video().
        wp_base_url: WordPress site base URL.
        wp_user: WordPress username.
        wp_app_pass: WordPress Application Password.
        yt_api_key: Optional YouTube Data API key.
        dry_run: If True, skip actual API write calls.
        skip_thumbnail: If True, skip thumbnail upload.
        profile: Optional portal profile dict for multi-tenant customization.

    Returns:
        Dict with keys: wp_id, yt_id, ok, status, link,
        thumbnail_media_id, rankmath_ok, yt_desc_ok.
    """
    auth = _make_auth(wp_user, wp_app_pass)
    logger.info("Injecting WP#%s | YT:%s", wp_id, yt_id)

    # ALT text: focus keyphrase + portal display name for SEO
    portal_name = (profile or {}).get("display_name", "Prawy TV")
    focus_kw = seo.get("focus_keyphrase", "").strip()
    img_alt = f"{focus_kw} | {portal_name}" if focus_kw else seo.get("seo_title", "")[:80]

    media_id = None
    if not skip_thumbnail and not dry_run:
        media_id = set_youtube_thumbnail(
            wp_id, yt_id, seo.get("original_title", ""), wp_base_url, auth,
            alt_text=img_alt,
        )

    status, link = update_post(
        wp_id, seo, yt_id, wp_base_url, auth, yt_api_key, dry_run, profile=profile
    )

    # RankMath SEO meta — via dedicated rankmath/v1/updateMeta endpoint
    # (WP REST 'meta' field silently ignores rank_math_* keys)
    rankmath_ok = False
    if not dry_run and status == 200:
        rankmath_ok = update_rankmath_meta(wp_id, seo, wp_base_url, auth)
    elif dry_run:
        rankmath_meta = _build_rankmath_meta(seo)
        logger.info(
            "  DRY RUN RankMath — would set keyphrase=%r",
            rankmath_meta.get("rank_math_focus_keyword", "-"),
        )

    # YouTube description update — via OAuth (yt_admin module)
    # Skipped gracefully if OAuth not configured or video not on our channel (403)
    yt_desc_ok = False
    if not dry_run and status == 200:
        try:
            from core.yt_admin import update_video_description  # type: ignore
            yt_desc_ok = update_video_description(yt_id, seo, link, dry_run=False)
        except EnvironmentError as exc:
            logger.info("  YT desc skipped — OAuth not configured: %s", exc)
        except Exception as exc:
            logger.warning("  YT desc update failed for %s: %s", yt_id, exc)
    elif dry_run:
        logger.info("  DRY RUN YT desc — would update description for %s", yt_id)

    return {
        "wp_id": wp_id,
        "yt_id": yt_id,
        "status": status,
        "link": link,
        "thumbnail_media_id": media_id,
        "rankmath_ok": rankmath_ok,
        "yt_desc_ok": yt_desc_ok,
        "ok": status == 200 or dry_run,
    }
