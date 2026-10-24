"""WordPress REST API Injector — write JSON-LD schema + rich content to WP posts.

Migrated from: inject_rest_v5.py (shadow-perihelion / D:\Biblioteki\prawy.pl)
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

Article structure (2026-06-19, vse-dev-17 — D2+D3 fix):
  Build order: lead → first paragraph of article_body → YT embed → chapters →
  rest of article_body → external link → Podsumowanie (quotes) → FAQ → JSON-LD → player JS
  Rationale: First paragraph before embed gives Google crawlable text above the fold
  and improves UX — reader gets article context before the video player.
  Quotes section renamed from 'Kluczowe cytaty' to 'Podsumowanie' for better
  editorial framing.

D4: External links (2026-06-20, vse-dev-18):
  CO: Wstrzykuje jeden stały link zewnętrzny per profil do treści artykułu.
  PO CO: RankMath wymaga co najmniej jednego linku zewnętrznego w artykule,
         żeby dać zielony wynik SEO. Bez niego scoring jest obniżany.
  JAK: Czyta seo_external_link.url + .anchor z profilu YAML, buduje <p><a> tag
       z target="_blank" rel="noopener". Wstawia po article_body,
       przed sekcją Podsumowanie. Graceful skip gdy pole nieobecne w profilu.

D5: Multi-keyword RankMath (2026-06-20, vse-dev-19):
  CO: Merguje frazy z 3 źródeł (GSC + Trends + LLM) do rank_math_focus_keyword.
  PO CO: RankMath akceptuje do 5 fraz oddzielonych przecinkami. Dotychczas
         używano tylko 1 frazy z LLM. Teraz: top2 GSC + top2 Trends + LLM
         keyphrases → dedupe → max 5 → comma-separated.
  JAK: build_focus_keywords() przyjmuje seo_data + saas_data, buduje
       merged listę, _build_rankmath_meta() używa jej zamiast prostego get().

D7: SEO Scoring Fix (2026-06-20, vse-dev-22):
  CO: Naprawia 6 problemów RankMath scoring (57→90+).
  PO CO: RankMath dawał 57/100 zamiast 90+. Root cause: meta_description
         z LLM ignorowana, noreferrer na external links, brak walidacji slug.
  JAK: 1) meta_desc z seo.get("meta_description") zamiast obcinania lead
       2) rel="noopener" zamiast "noopener noreferrer"
       3) Slug keyphrase validation z fallback na _sanitize_slug(focus_kp)
       4) Meta desc keyphrase check z append jeśli brak

D6a: yt_update_enabled flag (2026-06-20, vse-dev-20):
  CO: Dodaje flagę yt_update_enabled do profilu — steruje czy YT update jest wywoływany.
  PO CO: Portale bez OAuth (np. kurier365) generowały EnvironmentError przy każdej
         publikacji, zaśmiecając logi i maskując prawdziwe błędy.
  JAK: inject_video() czyta profile.get('yt_update_enabled', False). Jeśli False
       — pomija YT update z logiem debug. Jeśli True — wywołuje jak dotychczas.

D11: Video Screenshots + ImageObject (2026-06-21, vse-dev-26):
  CO: Upload screenshotów do WP Media Library + wstawianie <figure> w artykuł
      + ImageObject w JSON-LD schema.
  PO CO: Artykuły z obrazkami rankują wyżej w Google i Google Discover.
         ImageObject w JSON-LD podnosi RankMath scoring do 80+.
  JAK: _upload_image_to_wp() uploaduje do WP /wp/v2/media z opisami z SAAS/LLM.
       build_schema_jsonld() dodaje "image" z ImageObject do VideoObject.
       build_post_content() wstawia <figure> z <img> po pierwszym akapicie.

Fix lead-excerpt (2026-07-23, vse-dev-fix):
  CO: Usuwa lead z post_excerpt — lead był wyświetlany dwukrotnie na stronie.
  PO CO: Lead pojawiał się pod tytułem (post_excerpt) i pod filmem (post_content).
         User chce lead TYLKO w treści (pod filmem), NIE pod tytułem.
  JAK: Usunięto excerpt z payloadu update_post(). WP post_excerpt = pusty.

T1 (2026-10-24, vse-dev-t1):
  - _upload_image_to_wp pobiera obrazek przez HTTP image_url gdy brak pliku lokalnego.
  - set_youtube_thumbnail obsługuje PressAI Vision image_meta (5 pól) oraz wp_base_url.rstrip('/').
  - build_schema_jsonld zawsze generuje pełną listę @type: ImageObject (uploaded_images, image_data, YT fallback).
  - inject_video ustawia featured_media także z pierwszego wgranego screenshotu.

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


def _build_player_js(seek_fn: str = "vseSeek", chapter_class: str = "vse-chapter") -> str:
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
PLAYER_JS = _build_player_js(seek_fn="vseSeek", chapter_class="vse-chapter")


# ============================================================
# HELPERS
# ============================================================

def _strip_html(html: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", html).strip()

def _sanitize_slug(text: str) -> str:
    """Convert SEO title/post_title to a URL-safe WP slug.

    Transliterates Polish chars, lowercases, replaces spaces with hyphens,
    strips stop-words and special characters. Result <= 60 chars.

    Should only be used when WP slug is not provided by Gemini (wp_slug field).
    Gemini-generated wp_slug is preferred.

    Args:
        text: Input string (post_title or seo_title).

    Returns:
        URL-safe slug string, max 60 chars.
    """
    PL_MAP = str.maketrans(
        "\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c\u0104\u0106\u0118\u0141\u0143\u00d3\u015a\u0179\u017b",
        "acelnoszzACELNOSZZ",
    )
    STOP_WORDS = {
        "i", "w", "z", "na", "do", "ze", "si\u0119", "lub",
        "oraz", "dla", "jak", "jest", "by", "to", "nie", "co",
    }
    slug = text.lower().translate(PL_MAP)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    words = [w for w in slug.split() if w not in STOP_WORDS and len(w) > 1]
    slug = "-".join(words)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]


def _make_auth(wp_user: str, wp_app_pass: str) -> HTTPBasicAuth:
    """Build HTTPBasicAuth from credentials."""
    return HTTPBasicAuth(wp_user, wp_app_pass)


# ============================================================
# D5: MULTI-KEYWORD MERGE (vse-dev-19)
# ============================================================

def build_focus_keywords(seo_data: dict, saas_data: Optional[dict] = None) -> str:
    """Merge keywords from 3 sources: GSC + Trends + LLM → comma-separated for RankMath.

    CO: Buduje string comma-separated z frazami kluczowymi z trzech źródeł.

    PO CO: RankMath akceptuje do 5 fraz oddzielonych przecinkami w polu
    rank_math_focus_keyword. Dotychczas używano tylko 1 frazy z LLM.
    Teraz łączymy: top2 GSC + top2 Trends + LLM keyphrases, deduplikujemy,
    i zwracamy max 5 — co daje lepszy scoring SEO.

    JAK:
    1. GSC priority keywords (top 2) — z saas_data
    2. Google Trends keywords (top 2) — z saas_data
    3. LLM-generated keyphrases — z seo_data
    4. Dedupe (case-insensitive), max 5
    5. Join z przecinkami

    Args:
        seo_data: SEO result dict from generator.process_video().
        saas_data: Optional dict from saas_enricher.get_saas_seo_data().
            If None, only LLM keyphrases are used.

    Returns:
        Comma-separated string of up to 5 unique keyphrases.
        Empty string if no keyphrases available.
    """
    from api.services.saas_enricher import extract_priority_keywords, extract_trends_keywords

    keywords: list[str] = []

    if saas_data:
        # 1. GSC priority (top 2)
        gsc_kw = extract_priority_keywords(saas_data, max_keywords=2)
        keywords.extend(gsc_kw)

        # 2. Trends (top 2)
        trends_kw = extract_trends_keywords(saas_data)
        keywords.extend(trends_kw[:2])

    # 3. LLM-generated keyphrases
    llm_kw = seo_data.get("focus_keyphrases", [])
    if isinstance(llm_kw, str):  # backward compat: old single string format
        llm_kw = [llm_kw] if llm_kw.strip() else []
    keywords.extend(llm_kw)

    # Fallback: try old focus_keyphrase field
    if not keywords:
        old_kp = seo_data.get("focus_keyphrase", "").strip()
        if old_kp:
            keywords.append(old_kp)

    # Dedupe (case-insensitive), preserve order, max 5
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        kw_lower = kw.strip().lower()
        if kw_lower and kw_lower not in seen:
            seen.add(kw_lower)
            unique.append(kw.strip())

    result = ",".join(unique[:5])
    logger.info(
        "  D5 focus_keywords merged: %d sources → %d unique → %r",
        len(keywords), len(unique), result[:80],
    )
    return result


def _build_rankmath_meta(seo: dict, saas_data: Optional[dict] = None) -> dict:
    """Build RankMath SEO meta fields dict (used for update_rankmath_meta).

    D5 (vse-dev-19): Now uses build_focus_keywords() to merge GSC + Trends + LLM
    keyphrases instead of just using single focus_keyphrase from LLM.

    Returns a dict with keys: rank_math_focus_keyword, rank_math_description,
    rank_math_title. Empty values are omitted.
    """
    # D5: Multi-keyword merge
    focus_keyword = build_focus_keywords(seo, saas_data)

    # D7: Use LLM-generated meta_description first (has keyphrase by prompt design)
    meta_desc = seo.get("meta_description", "").strip()
    if not meta_desc:
        # Fallback: strip lead to 160 chars
        lead_plain = _strip_html(seo.get("lead", ""))
        meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain

    # D7: Validate meta_desc contains at least one word from focus keyphrase
    focus_kp = seo.get("focus_keyphrase", "").strip()
    if meta_desc and focus_kp:
        kp_words = {w.lower() for w in focus_kp.split() if len(w) > 2}
        desc_lower = meta_desc.lower()
        if kp_words and not any(w in desc_lower for w in kp_words):
            # Keyphrase missing from meta_desc — append it (max 160 chars)
            suffix = f" — {focus_kp}"
            if len(meta_desc) + len(suffix) <= 160:
                meta_desc = meta_desc.rstrip(".") + suffix
            else:
                max_len = 160 - len(suffix)
                if max_len > 20:
                    meta_desc = meta_desc[:max_len].rstrip() + suffix
            logger.warning("  D7 meta_desc: keyphrase appended → %r", meta_desc[:80])

    seo_title = seo.get("seo_title", "").strip()
    meta: dict = {}
    if focus_keyword:
        meta["rank_math_focus_keyword"] = focus_keyword
    if meta_desc:
        meta["rank_math_description"] = meta_desc
    if seo_title:
        meta["rank_math_title"] = seo_title
    if meta:
        logger.info("  RankMath: keyphrase=%r title=%r", focus_keyword[:60], seo_title[:40])
    return meta


def _build_external_link_block(profile: Optional[dict] = None) -> str:
    """Build an external link HTML block from profile's seo_external_link config.

    CO: Generuje blok <p><a> z linkiem zewnętrznym zdefiniowanym w profilu YAML.

    PO CO: RankMath wymaga co najmniej jednego linku zewnętrznego w artykule,
    żeby dać zielony wynik SEO. Bez tego pola RankMath obniża scoring za każdy post.
    Link jest stały per profil — nie wymaga logiki LLM.

    JAK: Czyta profile['seo_external_link']['url'] i ['anchor']. Jeśli pole
    nie istnieje lub jest puste — zwraca pusty string (graceful skip).
    Buduje <a> tag z target="_blank" rel="noopener" wewnątrz
    WP paragraph block.

    Args:
        profile: Portal profile dict loaded from YAML. May be None.

    Returns:
        WP block HTML string with external link, or empty string if not configured.
    """
    if not profile:
        return ""
    ext_link = profile.get("seo_external_link", {})
    if not ext_link:
        return ""
    url = ext_link.get("url", "").strip()
    anchor = ext_link.get("anchor", "").strip()
    if not url:
        return ""
    if not anchor:
        anchor = "Źródło zewnętrzne"
    logger.info("  D4 external link: %s -> %r", url, anchor)
    return (
        f'<!-- wp:paragraph -->\n'
        f'<p>Więcej informacji: <a href="{url}" target="_blank" '
        f'rel="noopener">{anchor}</a></p>\n'
        f'<!-- /wp:paragraph -->'
    )


def update_rankmath_meta(
    wp_id: int,
    seo: dict,
    wp_base_url: str,
    auth: HTTPBasicAuth,
    saas_data: Optional[dict] = None,
) -> bool:
    """Push SEO meta to RankMath via its dedicated REST endpoint.

    WP REST API's standard ``meta`` field silently ignores RankMath keys
    (only 'footnotes' is returned). The correct approach is the
    ``rankmath/v1/updateMeta`` endpoint which accepts objectType + objectID + meta.

    Verified live on prawy.pl: POST rankmath/v1/updateMeta returns
    ``{"slug": true, ...}`` on success.

    D5 (vse-dev-19): Now accepts optional saas_data parameter for multi-keyword
    merge. If saas_data is provided, build_focus_keywords() merges GSC + Trends
    + LLM keyphrases into rank_math_focus_keyword.

    Args:
        wp_id: WordPress post ID.
        seo: SEO result dict from generator.process_video().
        wp_base_url: WordPress site base URL.
        auth: HTTPBasicAuth instance.
        saas_data: Optional SAAS enrichment data for multi-keyword merge.

    Returns:
        True if RankMath accepted the update, False otherwise.
    """
    rankmath_meta = _build_rankmath_meta(seo, saas_data)
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
        debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
        if debug_mode and resp.status_code >= 400:
            logger.error("  [DEBUG] WP Error Payload: %s", json.dumps(payload))
            logger.error("  [DEBUG] WP Error Response: %s", resp.text)
        resp.raise_for_status()

        if not resp.text.strip():
            logger.warning("  RankMath update returned empty body (HTTP %s) for WP#%s", resp.status_code, wp_id)
            return True

        data = resp.json()
        if resp.status_code == 200 and data.get("slug") is True:
            logger.info(
                "  RankMath OK: WP#%s | keyphrase=%r",
                wp_id, rankmath_meta.get("rank_math_focus_keyword", "-")[:60],
            )
            return True
        logger.error(
            "  RankMath FAIL WP#%s: HTTP %s | %s",
            wp_id, resp.status_code, str(data)[:200],
        )
        return False
    except requests.exceptions.RequestException as exc:
        logger.error("  RankMath exception WP#%s: %s", wp_id, exc)
        return False
    except ValueError as exc:
        logger.error("  RankMath JSON decode exception WP#%s: %s", wp_id, exc)
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
    url = f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/posts/{wp_id}"
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

def _set_media_alt(
    media_id: int,
    alt_text: str,
    title: str,
    wp_base_url: str,
    auth: HTTPBasicAuth,
    caption: str = "",
    description: str = "",
) -> None:
    """PATCH WP media item to set alt_text, title, caption, and description."""
    payload = {"alt_text": alt_text, "title": title}
    if caption:
        payload["caption"] = caption
    if description:
        payload["description"] = description
    try:
        resp = requests.post(
            f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/media/{media_id}",
            json=payload,
            auth=auth,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.error(
                "  THUMB ALT: metadata update failed for media #%s: HTTP %s | %s",
                media_id, resp.status_code, resp.text[:200]
            )
        else:
            logger.info("  THUMB ALT: set alt_text=%r title=%r", alt_text[:60], title[:60])
    except Exception as exc:
        logger.warning("  THUMB ALT: could not set media metadata: %s", exc)


def set_youtube_thumbnail(
    wp_id: int,
    yt_id: str,
    post_title: str,
    wp_base_url: str,
    auth: HTTPBasicAuth,
    alt_text: str = "",
    image_meta: Optional[dict] = None,
) -> Optional[int]:
    """Download YouTube thumbnail and set it as the WP post's featured image.

    Tries maxresdefault → hqdefault → mqdefault. Deduplicates uploads
    by checking if a media item with the same filename already exists.
    Supports PressAI Vision image_meta (filename, alt_text, title, caption, description).

    Args:
        wp_id: WordPress post ID.
        yt_id: YouTube video ID.
        post_title: Post title (used for logging and fallback).
        wp_base_url: Base URL of the WordPress site.
        auth: HTTPBasicAuth instance.
        alt_text: Fallback ALT text for the thumbnail image.
        image_meta: Optional PressAI Vision metadata dict (filename, alt_text, title, caption, description).

    Returns:
        WP media ID (int) on success, or None on failure.
    """
    wp_base_url = wp_base_url.rstrip("/")

    img_resp = None
    for quality in ["maxresdefault", "hqdefault", "mqdefault"]:
        thumb_url = f"https://img.youtube.com/vi/{yt_id}/{quality}.jpg"
        try:
            r = requests.get(thumb_url, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                img_resp = r
                logger.info("  THUMB: downloaded %s (%s)", quality, yt_id)
                break
        except Exception as e:
            logger.debug("  THUMB: %s download error for %s: %s", quality, yt_id, e)

    if not img_resp:
        logger.warning("  THUMB: could not download for %s", yt_id)
        return None

    # Handle image_meta from PressAI Vision
    descs = {}
    if image_meta:
        if isinstance(image_meta.get("descriptions"), dict):
            descs = image_meta["descriptions"]
        elif isinstance(image_meta, dict):
            descs = image_meta

    from urllib.parse import urlparse
    domain = urlparse(wp_base_url).netloc.replace('www.', '').replace('.', '-')
    if not domain:
        domain = "vse-media"

    custom_fn = descs.get("filename")
    if custom_fn:
        custom_fn = re.sub(r'[^a-zA-Z0-9_.-]', '-', custom_fn)
        if not custom_fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            custom_fn += ".jpg"
        filename = custom_fn
    else:
        filename = f"{domain}-{yt_id}.jpg"

    final_alt = (descs.get("alt_text") or alt_text or post_title).strip()
    final_title = (descs.get("title") or post_title or f"Thumbnail {yt_id}").strip()
    caption = (descs.get("caption") or f"Miniatura wideo: {post_title}").strip()
    description = (descs.get("description") or f"Zdjęcie miniatury wideo dla artykułu: {post_title} ({yt_id})").strip()

    # Dedup: check if already uploaded
    search_term = filename.replace('.jpg', '').replace('.png', '').replace('.webp', '')
    search_url = f"{wp_base_url}/wp-json/wp/v2/media?search={search_term}&per_page=1"

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
            _set_media_alt(media_id, final_alt, final_title, wp_base_url, auth, caption, description)
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
            if set_resp.status_code in (200, 201):
                _set_media_alt(media_id, final_alt, final_title, wp_base_url, auth, caption, description)
                logger.info("  THUMB: uploaded + set as featured (media #%s)", media_id)
                return media_id
        logger.warning("  THUMB: upload failed HTTP %s", upload_resp.status_code)
    except Exception as exc:
        logger.error("  THUMB: upload exception: %s", exc)
    return None


# ============================================================
# D11: UPLOAD SCREENSHOT TO WP MEDIA LIBRARY
# ============================================================

def _upload_image_to_wp(
    image_path: str,
    descriptions: dict,
    wp_base_url: str,
    wp_user: str,
    wp_app_password: str,
    image_url: Optional[str] = None,
) -> Optional[dict]:
    """Upload an image to WordPress Media Library with SEO descriptions.

    CO: Uploaduje screenshot wideo do WP Media Library z opisami z SAAS/LLM.

    PO CO: Obrazki w artykule muszą być hostowane w WP (nie z YouTube CDN)
    żeby Google je indeksował. Alt text z keyphrase podnosi Image SEO.
    WP Media Library daje pełną kontrolę nad metadanymi obrazu.

    JAK: POST /wp/v2/media z pliku lokalnego lub pobranego przez HTTP z image_url.
    Ustawia w WP Media Library 5 pól: filename, alt_text, title, caption, description.
    Zwraca dict z id, url, width, height lub None na błąd.

    Args:
        image_path: Local path to the image file (optional if image_url provided).
        descriptions: Dict with alt_text, title, caption, description, filename keys.
        wp_base_url: WordPress site base URL.
        wp_user: WordPress username.
        wp_app_password: WordPress Application Password.
        image_url: Optional remote URL to download image if image_path doesn't exist.

    Returns:
        Dict with id, url, width, height keys, or None on failure.
    """
    auth = _make_auth(wp_user, wp_app_password)
    wp_base_url = wp_base_url.rstrip("/")

    image_data: Optional[bytes] = None

    if image_path and os.path.isfile(image_path):
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
        except Exception as e:
            logger.warning("  D11 upload: error reading %s: %s", image_path, e)

    if (not image_data or len(image_data) < 1000) and image_url:
        try:
            r = requests.get(image_url, timeout=20)
            if r.status_code == 200 and len(r.content) >= 1000:
                image_data = r.content
                logger.info("  D11 upload: downloaded image from HTTP %s (%d bytes)", image_url, len(image_data))
            else:
                logger.warning(
                    "  D11 upload: HTTP fetch from %s failed: status=%s len=%d",
                    image_url, r.status_code, len(r.content) if r.content else 0,
                )
        except Exception as exc:
            logger.warning("  D11 upload: could not fetch image_url %s: %s", image_url, exc)

    if not image_data or len(image_data) < 1000:
        logger.warning("  D11 upload: no valid image bytes (file=%s, url=%s)", image_path, image_url)
        return None

    # Determine filename
    raw_fn = descriptions.get("filename") or (os.path.basename(image_path) if image_path else "vse-image.jpg")
    raw_fn = re.sub(r'[^a-zA-Z0-9_.-]', '-', raw_fn)
    if not raw_fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        raw_fn = raw_fn + ".jpg"
    filename = raw_fn

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/jpeg",
    }

    try:
        upload_resp = requests.post(
            f"{wp_base_url}/wp-json/wp/v2/media",
            headers=headers,
            data=image_data,
            auth=auth,
            timeout=30,
        )
        if upload_resp.status_code not in (200, 201):
            logger.warning(
                "  D11 upload: HTTP %s for %s: %s",
                upload_resp.status_code, filename, upload_resp.text[:200],
            )
            return None

        media_data = upload_resp.json()
        media_id = media_data["id"]
        media_url = media_data.get("source_url", "")

        # Set alt_text, title, caption, description via PATCH
        meta_payload = {}
        alt_text = descriptions.get("alt_text", "").strip()
        title = descriptions.get("title", "").strip()
        caption = descriptions.get("caption", "").strip()
        description = descriptions.get("description", "").strip()

        if alt_text:
            meta_payload["alt_text"] = alt_text
        if title:
            meta_payload["title"] = title
        if caption:
            meta_payload["caption"] = caption
        if description:
            meta_payload["description"] = description

        if meta_payload:
            resp_meta = requests.post(
                f"{wp_base_url}/wp-json/wp/v2/media/{media_id}",
                json=meta_payload,
                auth=auth,
                timeout=10,
            )
            if resp_meta.status_code not in (200, 201):
                logger.error(
                    "  D11 upload: media metadata update failed for media #%s: HTTP %s | %s",
                    media_id, resp_meta.status_code, resp_meta.text[:200]
                )
            else:
                logger.info("  D11 upload: media metadata updated OK for media #%s", media_id)

        # Get dimensions from WP response
        media_details = media_data.get("media_details", {})
        width = media_details.get("width", 1280)
        height = media_details.get("height", 720)

        logger.info(
            "  D11 upload OK: media #%s | %s | alt=%r",
            media_id, media_url[:60] if media_url else "?", alt_text[:40],
        )
        return {
            "id": media_id,
            "url": media_url,
            "width": width,
            "height": height,
        }

    except Exception as exc:
        logger.error("  D11 upload exception: %s", exc)
        return None


# ============================================================
# BUILD SCHEMA JSON-LD — VideoObject + Clip + FAQPage + Quotation + ImageObject
# ============================================================

def build_schema_jsonld(
    seo: dict,
    yt_id: str,
    upload_date: str,
    yt_api_key: Optional[str] = None,
    target_lang: Optional[str] = None,
) -> list[dict]:
    """Build the full JSON-LD schema list for a video post.

    Produces: VideoObject (with optional interactionStatistic + hasPart clips),
    FAQPage (if faq present), Quotation per polished quote.

    D11: Adds "image" field with ImageObject array to VideoObject schema.
    Always includes ImageObject objects with robust fallbacks:
      1) uploaded_images (from WP Media Library)
      2) image_data (from PressAI Vision / LLM)
      3) YouTube maxresdefault thumbnail

    Note: Quotation schema is kept for completeness; Google does not render it.
    Do NOT add new Quotation items — preserve existing if already injected.

    Args:
        seo: SEO result dict from generator.process_video().
        yt_id: YouTube video ID.
        upload_date: ISO 8601 datetime string with timezone.
        yt_api_key: Optional YouTube Data API key for live view count fetch.
        target_lang: Optional explicit 2-letter target language override.

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

    resolved_lang = (target_lang or seo.get("target_lang") or "pl").lower()[:2]
    try:
        from core.generator import SUPPORTED_LANGUAGES
        watch_label = SUPPORTED_LANGUAGES.get(resolved_lang, SUPPORTED_LANGUAGES["pl"])["WatchAction"]
    except Exception:
        watch_label = "Obejrzyj wideo"

    post_url = (seo.get("post_url") or seo.get("link") or yt_url).strip()
    video_id_uri = f"{post_url}#video" if post_url else f"{yt_url}#video"

    seek_action = {
        "@type": "SeekToAction",
        "target": f"{yt_url}&t={{seek_to_second_number}}",
        "startOffset-input": "required name=seek_to_second_number",
    }

    video_schema: dict = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "@id": video_id_uri,
        "name": seo.get("seo_title", ""),
        "description": seo.get("video_description", ""),
        "thumbnailUrl": f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg",
        "uploadDate": upload_date,
        "contentUrl": yt_url,
        "embedUrl": f"https://www.youtube.com/embed/{yt_id}",
        "duration": iso_dur,
        "inLanguage": resolved_lang,
        "potentialAction": [
            {
                "@type": "WatchAction",
                "name": watch_label,
                "target": yt_url,
            },
            seek_action,
        ],
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

    # D11: ImageObject — ALWAYS ensure full ImageObject list
    image_objects: list[dict] = []
    post_title_val = (seo.get("post_title") or seo.get("seo_title") or f"Wideo {yt_id}").strip()
    focus_kp_val = (seo.get("focus_keyphrase") or "").strip()

    # Source 1: uploaded_images from WP Media Library
    uploaded_images = seo.get("uploaded_images", [])
    if uploaded_images:
        for img in uploaded_images:
            img_url = img.get("wp_url") or img.get("url", "")
            if not img_url:
                continue
            caption = img.get("caption") or img.get("alt_text") or post_title_val
            name = img.get("title") or img.get("alt_text") or focus_kp_val or post_title_val
            img_obj = {
                "@type": "ImageObject",
                "url": img_url,
                "width": int(img.get("width") or 1280),
                "height": int(img.get("height") or 720),
            }
            if caption:
                img_obj["caption"] = caption
            if name:
                img_obj["name"] = name
            image_objects.append(img_obj)

    # Source 2: fallback to image_data from pipeline (PressAI Vision / LLM descriptions)
    if not image_objects and seo.get("image_data"):
        for img in seo["image_data"]:
            img_url = img.get("url") or img.get("path", "")
            if not img_url or not str(img_url).startswith("http"):
                continue
            descs = img.get("descriptions") or {}
            caption = descs.get("caption") or descs.get("alt_text") or img.get("caption") or img.get("alt_text") or post_title_val
            name = descs.get("title") or descs.get("alt_text") or img.get("title") or focus_kp_val or post_title_val
            img_obj = {
                "@type": "ImageObject",
                "url": img_url,
                "width": int(img.get("width") or 1280),
                "height": int(img.get("height") or 720),
            }
            if caption:
                img_obj["caption"] = caption
            if name:
                img_obj["name"] = name
            image_objects.append(img_obj)

    # Source 3: ultimate fallback when both empty — YouTube thumbnail
    if not image_objects:
        fallback_thumb = seo.get("thumbnail_url") or f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg"
        image_objects.append({
            "@type": "ImageObject",
            "url": fallback_thumb,
            "width": 1280,
            "height": 720,
            "caption": post_title_val,
            "name": focus_kp_val or post_title_val,
        })

    video_schema["image"] = image_objects
    logger.info("  D11 schema: %d ImageObject(s) added to VideoObject", len(image_objects))

    from urllib.parse import urlparse
    parsed_url = urlparse(post_url)
    wp_site_url = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else "https://vse.impresjapr.pl"

    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "@id": f"{post_url}#article" if post_url else f"{yt_url}#article",
        "headline": post_title_val,
        "description": (seo.get("meta_description") or seo.get("lead") or seo.get("video_description", "")).strip(),
        "datePublished": upload_date,
        "dateModified": upload_date,
        "mainEntityOfPage": post_url or yt_url,
        "inLanguage": resolved_lang,
        "video": {"@id": video_id_uri},
    }
    if image_objects:
        article_schema["image"] = image_objects

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Strona główna",
                "item": wp_site_url,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": (seo.get("seo_title") or seo.get("post_title") or "Wideo").strip(),
                "item": post_url or yt_url,
            },
        ],
    }

    schemas: list[dict] = [video_schema, article_schema, breadcrumb_schema]

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
            "inLanguage": resolved_lang,
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
# ARTICLE STRUCTURE HELPER — split first paragraph
# ============================================================

def _split_first_paragraph(html: str) -> tuple[str, str]:
    """Extract the first <p> element from HTML body text.

    CO: Wyodrębnia pierwszy akapit z HTML article_body.

    PO CO: Potrzebujemy umieścić pierwszy akapit PRZED embedem YouTube,
    żeby Google miało crawlowalny tekst nad foldą oraz żeby czytelnik dostał
    kontekst artykułu zanim zobaczy player wideo. To ważny sygnał UX i SEO.

    JAK: Szuka pierwszego <p>...</p> w HTML (DOTALL). Jeśli znaleziony —
    zwraca go i resztę body. Jeśli HTML nie ma <p> — zwraca pusty string
    i cały html jako rest (graceful fallback).

    Args:
        html: Full HTML string of article_body from LLM.

    Returns:
        Tuple of (first_p, rest_html). If no <p> found, returns ('', html).
    """
    cleaned = re.sub(r'^\s*<h2[^>]*>.*?</h2>\s*', '', html, count=1, flags=re.I | re.S)
    match = re.search(r'(<p[^>]*>.*?</p>)', cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        # Include anything before the first <p> (like <aside class="context-box"> or <hr id='system-readmore' />)
        first_p = cleaned[:match.end()].strip()
        rest = cleaned[match.end():].strip()
        return first_p, rest
    return "", cleaned


# ============================================================
# D11: BUILD FIGURE BLOCKS FOR SCREENSHOTS
# ============================================================

def _build_figure_blocks(uploaded_images: list[dict]) -> list[str]:
    """Build WP figure blocks from uploaded image data.

    CO: Generuje bloki <figure> z <img> dla screenshotów wideo.

    PO CO: Obrazki w artykule podnoszą engagement i SEO scoring.
    Google Discover wymaga co najmniej 1 obrazka 1200px.
    RankMath daje punkty za ImageObject + alt z keyphrase.

    JAK: Każdy obraz to WP Gutenberg image block z:
    - <img> z src, alt, width, height
    - <figcaption> z caption
    - Lazy loading (loading="lazy")

    Args:
        uploaded_images: List of dicts with url, alt_text, caption, width, height.

    Returns:
        List of HTML strings (WP Gutenberg image blocks).
    """
    blocks: list[str] = []
    for img in uploaded_images:
        url = img.get("url", "")
        alt = img.get("alt_text", "").replace('"', '&quot;')
        caption = img.get("caption", "")
        width = img.get("width", 1280)
        height = img.get("height", 720)

        if not url:
            continue

        fig_html = (
            f'<!-- wp:image {{"sizeSlug":"large"}} -->\n'
            f'<figure class="wp-block-image size-large">'
            f'<img src="{url}" alt="{alt}" '
            f'width="{width}" height="{height}" loading="lazy" />'
        )
        if caption:
            fig_html += f'<figcaption class="wp-element-caption">{caption}</figcaption>'
        fig_html += '</figure>\n<!-- /wp:image -->'

        blocks.append(fig_html)

    return blocks


# ============================================================
# BUILD POST CONTENT — WP blocks + seekTo JS
# ============================================================


def _build_responsive_embed(yt_id: str, yt_url: str = "") -> str:
    """Build responsive 16:9 YouTube iframe embed with inline styles (TASK-03)."""
    url = yt_url or f"https://www.youtube.com/watch?v={yt_id}"
    embed_json = json.dumps({
        "url": url, "type": "video", "providerNameSlug": "youtube",
        "responsive": True, "className": "wp-embed-aspect-16-9 wp-has-aspect-ratio",
    })
    return (
        f'<!-- wp:embed {embed_json} -->\n'
        f'<figure class="wp-block-embed is-type-video is-provider-youtube '
        f'wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio" '
        f'style="aspect-ratio:16/9;width:100%;max-width:100%;position:relative;overflow:hidden;">\n'
        f'<div class="wp-block-embed__wrapper" style="position:relative;width:100%;padding-bottom:56.25%;height:0;overflow:hidden;">\n'
        f'<iframe src="https://www.youtube.com/embed/{yt_id}?enablejsapi=1" '
        f'title="YouTube video player" '
        f'style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" '
        f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        f'allowfullscreen loading="lazy"></iframe>\n'
        f'</div></figure>\n'
        f'<!-- /wp:embed -->'
    )


def _build_internal_links_block(seo: dict) -> str:
    """TASK-06: Build deterministic internal links fallback box."""
    internal_links = seo.get("internal_links") or []
    if not internal_links or not isinstance(internal_links, list):
        return ""
    article_body = seo.get("article_body", "") or ""
    unwoven = []
    for link in internal_links:
        if isinstance(link, dict) and link.get("url"):
            u = link["url"].strip()
            if u and u not in article_body:
                unwoven.append(link)
    if not unwoven:
        return ""
    items = unwoven[:3]
    li_html = "".join(f'<li><a href="{l["url"]}">{l.get("anchor") or l.get("title") or l["url"]}</a></li>' for l in items)
    return (
        f'<!-- wp:html -->\n'
        f'<div class="vse-related-links-box" style="margin:24px 0;padding:16px 20px;border-left:4px solid #2563eb;background:#f8fafc;border-radius:4px;">\n'
        f'<h4 style="margin:0 0 10px 0;font-size:16px;color:#1e293b;">Warto również przeczytać:</h4>\n'
        f'<ul style="margin:0;padding-left:20px;color:#334155;">\n'
        f'{li_html}\n'
        f'</ul>\n'
        f'</div>\n'
        f'<!-- /wp:html -->'
    )

def build_post_content(
    seo: dict,
    yt_id: str,
    upload_date: str,
    yt_api_key: Optional[str] = None,
    profile: Optional[dict] = None,
) -> str:
    """Build full WordPress post content with blocks, schema JSON-LD, and seekTo JS.

    Produces (in order): lead paragraph → <!-- more --> → first paragraph of
    article_body → [screenshot 1 if available] → YT embed → chapters list →
    rest of article_body → [screenshot 2 if available] → external link (D4) →
    Podsumowanie (polished quotes) → FAQ collapsible →
    JSON-LD schemas → player JS.

    D11: Screenshots are inserted as <figure> blocks:
    - First screenshot after first paragraph (before embed)
    - Second screenshot after rest of article_body (before external link)

    The first paragraph of article_body is placed before the embed so Google
    has crawlable text above the fold and readers get article context before
    the video player (D2 fix, 2026-06-19).

    External link is injected from profile's seo_external_link config to satisfy
    RankMath's requirement for at least one external link (D4, 2026-06-20).

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

    # D11: Build figure blocks from uploaded images
    uploaded_images = seo.get("uploaded_images", [])
    figure_blocks = _build_figure_blocks(uploaded_images)

    # Strip leading <h2>...</h2> from the very start of article_body before splitting
    article_body = re.sub(r'^\s*<h2[^>]*>.*?</h2>\s*', '', article_body, count=1, flags=re.I | re.S)

    # D2: Split article_body into first paragraph + rest
    first_p, rest_body = _split_first_paragraph(article_body)

    # Lead block
    lead_block = (
        f"<!-- wp:paragraph -->\n<p>{lead_html}</p>\n<!-- /wp:paragraph -->\n\n"
        f"<!-- wp:more -->\n<!--more-->\n<!-- /wp:more -->"
    )

    # Intro block — first paragraph of article_body (before embed)
    intro_block = (
        f"<!-- wp:html -->\n{first_p}\n<!-- /wp:html -->"
        if first_p else ""
    )

    # D11: First screenshot — after first paragraph, before embed
    screenshot_1_block = figure_blocks[0] if len(figure_blocks) >= 1 else ""

    # YouTube embed (TASK-03)
    embed_block = _build_responsive_embed(yt_id, yt_url)

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

    # Rest of article body (after first paragraph)
    body_rest_block = (
        f"<!-- wp:html -->\n{rest_body}\n<!-- /wp:html -->"
        if rest_body else ""
    )

    # D11: Second screenshot — after rest of article body, before external link
    screenshot_2_block = figure_blocks[1] if len(figure_blocks) >= 2 else ""

    # D4: External link block — RankMath requires at least 1 external link
    external_link_block = _build_external_link_block(profile)

    # D3: Polished quotes with seekTo links — heading renamed to 'Podsumowanie'
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
            "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">Podsumowanie</h2>\n<!-- /wp:heading -->\n\n"
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

    internal_links_block = _build_internal_links_block(seo)

    # D2+D4+D11+W1: Article order
    # lead → first_p → screenshot_1 → embed → chapters → rest_body → internal_links → screenshot_2 →
    # external_link → quotes (Podsumowanie) → faq → schema → js
    parts = [
        lead_block, intro_block, screenshot_1_block, embed_block, chapters_block,
        body_rest_body := body_rest_block, internal_links_block, screenshot_2_block, external_link_block, quotes_section,
        faq_section, schema_block, js_block,
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
    saas_data: Optional[dict] = None,
    post_format: str = "video",
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
        saas_data: Optional SAAS enrichment data for D5 multi-keyword merge.

    Returns:
        Tuple of (http_status_code, post_url_or_message).
    """
    wp_base_url = wp_base_url.rstrip("/")
    upload_date = get_post_date(wp_id, wp_base_url, auth)
    logger.info("  uploadDate: %s", upload_date)

    logger.info("injecting article_body: %d chars, engine=%s", 
        len(seo.get('article_body', '')), 
        seo.get('article_engine', 'unknown'))

    content = build_post_content(seo, yt_id, upload_date, yt_api_key, profile=profile)

    if dry_run:
        rankmath_meta = _build_rankmath_meta(seo, saas_data)
        logger.info("  DRY RUN — skipping PATCH for WP#%s", wp_id)
        logger.info("  Would set: keyphrase=%r", rankmath_meta.get("rank_math_focus_keyword", "-"))
        return 0, "DRY_RUN"

    url = f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}"
    # NOTE: WP REST 'meta' field silently ignores rank_math_* keys —
    # use update_rankmath_meta() separately for the correct endpoint.
    wp_format = (post_format or "video").strip().lower()
    if wp_format in ("", "standard", "full_article", "article_only"):
        wp_format = "video"
    payload: dict = {"content": content, "format": wp_format}

    # Post title — update only if provided by generator
    post_title_val = seo.get("post_title", "").strip()
    if post_title_val:
        payload["title"] = post_title_val
        logger.info("  WP title -> %r", post_title_val[:60])

    try:
        resp = requests.post(url, json=payload, auth=auth, timeout=30)
        debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
        if debug_mode and resp.status_code >= 400:
            logger.error("  [DEBUG] WP Error Payload: %s", json.dumps(payload))
            logger.error("  [DEBUG] WP Error Response: %s", resp.text)
        link = resp.json().get("link", "?")
        logger.info("  REST API: %s | %s", resp.status_code, link)
        if resp.status_code != 200:
            logger.error("  PATCH failed for WP#%s: %s", wp_id, resp.text[:300])
        return resp.status_code, link
    except Exception as exc:
        logger.error("  update_post WP#%s exception: %s", wp_id, exc)
        raise


# ============================================================
# FULL INJECTION PIPELINE — thumbnail + screenshots + content
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
    saas_data: Optional[dict] = None,
    post_format: str = "video",
) -> dict:
    """Run the full injection pipeline for a single video post.

    Steps: thumbnail → D11 screenshots upload → WP content/excerpt → RankMath meta → YT description.

    D11 (vse-dev-26): Uploads screenshots from image_data to WP Media Library.
    Sets uploaded_images in seo dict for build_post_content() and build_schema_jsonld().

    YT description update is controlled by the 'yt_update_enabled' flag
    in the portal profile. Portals without OAuth (e.g. kurier365) should set
    yt_update_enabled: false to avoid EnvironmentError noise in logs.

    D5 (vse-dev-19): Accepts optional saas_data parameter. If provided,
    build_focus_keywords() merges GSC + Trends + LLM keyphrases into
    rank_math_focus_keyword (comma-separated, max 5 phrases).

    D6a (vse-dev-20): YT update gated by profile['yt_update_enabled'] flag.
    Default: False — no YT update unless explicitly enabled in portal profile.

    T1 (vse-dev-t1): Supports PressAI Vision image_meta in set_youtube_thumbnail
    and ensures image_url HTTP download when local file doesn't exist.

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
        saas_data: Optional SAAS enrichment data for D5 multi-keyword merge.

    Returns:
        Dict with keys: wp_id, yt_id, ok, status, link,
        thumbnail_media_id, rankmath_ok, yt_desc_ok, images_uploaded.
    """
    auth = _make_auth(wp_user, wp_app_pass)
    wp_base_url = wp_base_url.rstrip("/")
    logger.info("Injecting WP#%s | YT:%s", wp_id, yt_id)

    # ALT text: focus keyphrase + portal brand for SEO
    site_brand = "Portal"
    if profile:
        site_brand = profile.get("site_brand", "Portal")
    elif saas_data and saas_data.get("site_brand"):
        site_brand = saas_data.get("site_brand")

    focus_kw = seo.get("focus_keyphrase", "").strip()
    img_alt = f"{focus_kw} | {site_brand}" if focus_kw else seo.get("seo_title", "")[:80]

    media_id = None
    if not skip_thumbnail and not dry_run:
        image_data = seo.get("image_data", [])
        primary_meta = None
        if image_data:
            primary_meta = image_data[0].get("descriptions") if isinstance(image_data[0].get("descriptions"), dict) else image_data[0]
        media_id = set_youtube_thumbnail(
            wp_id, yt_id, seo.get("original_title", "") or seo.get("post_title", ""), wp_base_url, auth,
            alt_text=img_alt,
            image_meta=primary_meta,
        )

    # D11: Upload screenshots to WP Media Library
    uploaded_images: list[dict] = []
    image_data = seo.get("image_data", [])
    if image_data and not dry_run:
        for idx, img in enumerate(image_data):
            img_path = img.get("path", "")
            img_url = img.get("url", "")
            descs = img.get("descriptions", {}) or {}

            # Don't skip if img_path doesn't exist on disk, as long as img_url is available!
            if (not img_path or not os.path.isfile(img_path)) and not img_url:
                logger.warning("  D11 inject: image[%d] neither file nor url available", idx)
                continue

            wp_media = _upload_image_to_wp(
                image_path=img_path or "",
                descriptions=descs,
                wp_base_url=wp_base_url,
                wp_user=wp_user,
                wp_app_password=wp_app_pass,
                image_url=img_url,
            )
            if wp_media:
                uploaded_images.append({
                    "id": wp_media["id"],
                    "url": wp_media["url"],
                    "wp_url": wp_media["url"],
                    "width": wp_media["width"],
                    "height": wp_media["height"],
                    "alt_text": descs.get("alt_text", ""),
                    "title": descs.get("title", ""),
                    "caption": descs.get("caption", ""),
                    "description": descs.get("description", ""),
                    "description_source": img.get("description_source", "unknown"),
                })

        logger.info(
            "  D11 inject: %d/%d screenshots uploaded to WP",
            len(uploaded_images), len(image_data),
        )

        # If featured_media was not set, but we uploaded an image, set the first one as featured
        if not media_id and uploaded_images:
            try:
                first_media_id = uploaded_images[0]["id"]
                set_resp = requests.post(
                    f"{wp_base_url}/wp-json/wp/v2/posts/{wp_id}",
                    json={"featured_media": first_media_id},
                    auth=auth,
                    timeout=15,
                )
                if set_resp.status_code in (200, 201):
                    media_id = first_media_id
                    logger.info("  D11 inject: set first uploaded screenshot as featured_media #%s", media_id)
            except Exception as set_err:
                logger.warning("  D11 inject: failed setting featured_media from uploaded screenshot: %s", set_err)

    elif dry_run and image_data:
        logger.info("  D11 DRY RUN: would upload %d screenshots", len(image_data))

    # Attach uploaded_images to seo for build_post_content() and build_schema_jsonld()
    seo["uploaded_images"] = uploaded_images

    status, link = update_post(
        wp_id, seo, yt_id, wp_base_url, auth, yt_api_key, dry_run,
        profile=profile, saas_data=saas_data, post_format=post_format,
    )

    # RankMath SEO meta — via dedicated rankmath/v1/updateMeta endpoint
    # D5: pass saas_data for multi-keyword merge
    rankmath_ok = False
    if not dry_run and status == 200:
        rankmath_ok = update_rankmath_meta(wp_id, seo, wp_base_url, auth, saas_data=saas_data)
    elif dry_run:
        rankmath_meta = _build_rankmath_meta(seo, saas_data)
        logger.info(
            "  DRY RUN RankMath — would set keyphrase=%r",
            rankmath_meta.get("rank_math_focus_keyword", "-"),
        )

    # D6a: YouTube title + description update — gated by yt_update_enabled flag
    yt_update_ok = False
    yt_enabled = (profile or {}).get('yt_update_enabled', False)
    if yt_enabled and not dry_run and status == 200:
        try:
            from core.yt_admin import update_video_title_and_description  # type: ignore
            yt_update_ok = update_video_title_and_description(yt_id, seo, link, dry_run=False)
        except EnvironmentError as exc:
            logger.info("  YT update skipped — OAuth not configured: %s", exc)
        except Exception as exc:
            logger.warning("  YT title+desc update failed for %s: %s", yt_id, exc)
    elif yt_enabled and dry_run:
        logger.info(
            "  DRY RUN YT — would update title=%r desc for %s",
            seo.get("yt_title", "?")[:60], yt_id,
        )
    else:
        logger.debug("  YT update disabled for portal %s", (profile or {}).get('portal_id', '?'))

    return {
        "wp_id": wp_id,
        "yt_id": yt_id,
        "status": status,
        "link": link,
        "thumbnail_media_id": media_id,
        "rankmath_ok": rankmath_ok,
        "yt_update_ok": yt_update_ok,
        "wp_title_updated": bool(seo.get("post_title", "").strip()),
        "wp_slug_set": False,
        "images_uploaded": len(uploaded_images),
        "ok": status == 200 or dry_run,
    }


# ============================================================
# VSE WP PLUGIN v3.0 — ARTICLE & SECTION HTML BUILDERS
# ============================================================

def build_wp_article_sections(
    seo: dict,
    yt_id: str,
    schemas: Optional[list[dict]] = None,
    include_embed: bool = True,
) -> dict:
    """Build modular HTML sections and full article HTML for VSE WP Plugin v3.0.

    Returns dict with keys:
      - post_title: str
      - full_article_html: str
      - article_body_html: str
      - tldr_html: str
      - chapters_html: str
      - faq_html: str
      - summary_bullets: list[str]
      - faq: list[dict]
      - quotes: list[dict]
    """
    post_title = (seo.get("post_title") or seo.get("seo_title") or "").strip()
    lead_html = (seo.get("lead") or "").strip()
    raw_body = (seo.get("article_body") or "").strip()
    cleaned_body = re.sub(r"^\s*<h2[^>]*>.*?</h2>\s*", "", raw_body, count=1, flags=re.I | re.S).strip()

    chapters = seo.get("chapters") or []
    faq = seo.get("faq") or []
    quotes = seo.get("quotes") or []
    yt_url = seo.get("yt_url") or f"https://www.youtube.com/watch?v={yt_id}"

    # Extract or synthesize summary bullets (TL;DR)
    raw_bullets = seo.get("summary_bullets") or seo.get("tldr_bullets") or seo.get("key_takeaways") or []
    summary_bullets: list[str] = []
    if isinstance(raw_bullets, list):
        summary_bullets = [str(b).strip() for b in raw_bullets if str(b).strip()]
    if not summary_bullets and quotes:
        for q in quotes[:4]:
            qt = str(q.get("text") or "").strip()
            if qt:
                summary_bullets.append(qt)
    if not summary_bullets and chapters:
        for ch in chapters[:5]:
            lbl = str(ch.get("label") or ch.get("title") or "").strip()
            if lbl:
                summary_bullets.append(lbl)

    # TL;DR HTML
    tldr_parts: list[str] = []
    if lead_html:
        tldr_parts.append(f"<!-- wp:paragraph -->\n<p><strong>{lead_html}</strong></p>\n<!-- /wp:paragraph -->")
    if summary_bullets:
        li_html = "\n".join(f"<li>{b}</li>" for b in summary_bullets)
        tldr_parts.append(
            "<!-- wp:group {\"className\":\"vse-tldr-box\"} -->\n"
            "<div class=\"wp-block-group vse-tldr-box\">"
            "<h3>Najważniejsze wnioski (TL;DR)</h3>\n"
            f"<ul>\n{li_html}\n</ul>"
            "</div>\n<!-- /wp:group -->"
        )
    tldr_html = "\n\n".join(tldr_parts)

    # Chapters HTML
    ch_items: list[str] = []
    for ch in chapters:
        t = int(ch.get("time", 0) or 0)
        m, s = divmod(t, 60)
        label = str(ch.get("label") or ch.get("title") or "").strip()
        if label:
            ch_items.append(
                f'<li><a href="{yt_url}&t={t}s" class="vse-chapter" data-time="{t}">'
                f"<strong>{m:02d}:{s:02d}</strong> — {label}</a></li>"
            )
    chapters_html = ""
    if ch_items:
        chapters_html = (
            '<!-- wp:heading -->\n<h2 class="wp-block-heading">Rozdziały nagrania</h2>\n<!-- /wp:heading -->\n\n'
            '<!-- wp:list -->\n<ul class="vse-chapters-list">\n'
            + "\n".join(ch_items)
            + "\n</ul>\n<!-- /wp:list -->"
        )

    # Quotes HTML
    quotes_blocks: list[str] = []
    for q in quotes:
        t = int(q.get("time", 0) or 0)
        m, s = divmod(t, 60)
        q_text = str(q.get("text") or "").strip()
        q_speaker = str(q.get("speaker") or "Wypowiedź").strip()
        if q_text:
            quotes_blocks.append(
                "<!-- wp:quote -->\n"
                f'<blockquote class="wp-block-quote"><p>{q_text}</p>'
                f'<cite>— {q_speaker} (<a href="{yt_url}&t={t}s" class="vse-chapter" data-time="{t}">{m:02d}:{s:02d}</a>)</cite>'
                "</blockquote>\n<!-- /wp:quote -->"
            )
    quotes_html = ""
    if quotes_blocks:
        quotes_html = (
            '<!-- wp:heading -->\n<h2 class="wp-block-heading">Kluczowe wypowiedzi i podsumowanie</h2>\n<!-- /wp:heading -->\n\n'
            + "\n".join(quotes_blocks)
        )

    # FAQ HTML
    faq_blocks: list[str] = []
    for item in faq:
        q_str = str(item.get("question") or "").strip()
        a_str = str(item.get("answer") or "").strip()
        if q_str and a_str:
            faq_blocks.append(
                f"<details><summary><strong>{q_str}</strong></summary>"
                f"<p>{a_str}</p></details>"
            )
    faq_html = ""
    if faq_blocks:
        faq_html = (
            '<!-- wp:heading -->\n<h2 class="wp-block-heading">Najczęściej zadawane pytania (FAQ)</h2>\n<!-- /wp:heading -->\n\n'
            "<!-- wp:html -->\n" + "\n".join(faq_blocks) + "\n<!-- /wp:html -->"
        )

    # Article body HTML (standalone body with lead)
    article_body_parts: list[str] = []
    if lead_html:
        article_body_parts.append(f"<!-- wp:paragraph -->\n<p>{lead_html}</p>\n<!-- /wp:paragraph -->")
    if cleaned_body:
        article_body_parts.append(f"<!-- wp:html -->\n{cleaned_body}\n<!-- /wp:html -->")
    article_body_html = "\n\n".join(article_body_parts)

    # Full Article HTML (Lead -> First P -> YT Embed -> Chapters -> Rest of Body -> Quotes -> FAQ -> Player JS)
    first_p, rest_body = _split_first_paragraph(cleaned_body)
    full_parts: list[str] = []
    if lead_html:
        full_parts.append(
            f"<!-- wp:paragraph -->\n<p>{lead_html}</p>\n<!-- /wp:paragraph -->\n\n"
            "<!-- wp:more -->\n<!--more-->\n<!-- /wp:more -->"
        )
    if first_p:
        full_parts.append(f"<!-- wp:html -->\n{first_p}\n<!-- /wp:html -->")
    if include_embed and yt_id and not str(yt_id).startswith("audio"):
        full_parts.append(_build_responsive_embed(yt_id, yt_url))
    if chapters_html:
        full_parts.append(chapters_html)
    if rest_body:
        full_parts.append(f"<!-- wp:html -->\n{rest_body}\n<!-- /wp:html -->")
    internal_links_block = _build_internal_links_block(seo)
    if internal_links_block:
        full_parts.append(internal_links_block)
    if quotes_html:
        full_parts.append(quotes_html)
    if faq_html:
        full_parts.append(faq_html)

    player_js = _build_player_js(seek_fn="vseSeek", chapter_class="vse-chapter")
    full_parts.append(f"<!-- wp:html -->\n{player_js}\n<!-- /wp:html -->")

    full_article_html = "\n\n".join(p for p in full_parts if p)

    return {
        "post_title": post_title,
        "full_article_html": full_article_html,
        "article_body_html": article_body_html,
        "tldr_html": tldr_html,
        "chapters_html": chapters_html,
        "faq_html": faq_html,
        "summary_bullets": summary_bullets,
        "faq": faq,
        "quotes": quotes,
    }


def build_wp_post_html(
    seo: dict,
    yt_id: str,
    schemas: Optional[list[dict]] = None,
    include_embed: bool = True,
    post_format: str = "full_article",
) -> str:
    """Build complete WordPress post HTML for VSE WP Plugin v3.0 (push/pull)."""
    sections = build_wp_article_sections(
        seo=seo,
        yt_id=yt_id,
        schemas=schemas,
        include_embed=include_embed,
    )
    if post_format == "article_only":
        return sections["article_body_html"]
    return sections["full_article_html"]
