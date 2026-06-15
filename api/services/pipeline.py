"""VSE Pipeline Orchestration Service.

Wraps synchronous core/ functions for async FastAPI context.
All CPU/IO-bound core calls use asyncio.to_thread() to avoid blocking
the event loop.

Pipeline for POST /v1/process:
  1. Fetch: core.fetcher.process_video → metadata + VTT
  2. Match:  core.matcher (if wp_post_id not provided)
  3. Generate: core.generator.process_video → SEO schema dict
  4. Inject: core.injector.inject_video → WP REST patch
"""
import asyncio
import logging
import os
import tempfile
import time
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL or return as-is."""
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    import re as _re
    if _re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    raise ValueError(f"Cannot extract video ID from: {url}")


async def run_generate(video_url: str, llm_provider: str, lang: str,
                       post_title_override: Optional[str] = None) -> dict:
    """Fetch transcript + generate SEO schema. No WP write.

    Args:
        video_url: YouTube video URL or ID.
        llm_provider: 'claude' or 'gemini'.
        lang: Transcript language code (default 'pl').
        post_title_override: Optional title override instead of yt-dlp metadata.

    Returns:
        Dict with 'video_id', 'meta', 'seo' keys.

    Raises:
        ValueError: On invalid URL or missing API key.
        RuntimeError: On fetcher/generator failure.
    """
    from core.fetcher import process_video as fetch_video
    from core.generator import process_video as generate_schema

    video_id = _extract_video_id(video_url)
    logger.info("[generate] video_id=%s provider=%s", video_id, llm_provider)

    # Determine API key based on provider
    if llm_provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
    elif llm_provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider!r}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Fetch metadata + transcript (sync → thread)
        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)
        if not meta or meta.get("error"):
            raise RuntimeError(f"Fetch failed for {video_id}: {meta.get('error', 'unknown')}")

        vtt_path = meta.get("vtt_path")
        if not vtt_path:
            raise RuntimeError(f"No transcript available for {video_id}")

        post_title = post_title_override or meta.get("title", video_id)
        yt_url = meta.get("webpage_url", f"https://www.youtube.com/watch?v={video_id}")
        wp_id_placeholder = 0  # no WP ID for generate-only

        # 2. Generate schema (sync → thread)
        seo = await asyncio.to_thread(
            generate_schema,
            video_id,
            wp_id_placeholder,
            post_title,
            yt_url,
            vtt_path,
            api_key,
            None,  # out_dir — do not save file
            0,     # sleep_between
            llm_provider,
        )

    logger.info("[generate] done: video_id=%s keyphrase=%r",
                video_id, seo.get("focus_keyphrase", "?"))
    return {"video_id": video_id, "meta": meta, "seo": seo}


async def run_process(video_url: str, site_config: dict, options: dict,
                      wp_post_id: Optional[int] = None) -> dict:
    """Full pipeline: fetch → generate → inject.

    Args:
        video_url: YouTube video URL or ID.
        site_config: Dict with wp_base_url, wp_user, wp_app_password.
        options: Dict with auto_inject, update_youtube, llm_provider, lang.
        wp_post_id: Known WP post ID (skips matcher if provided).

    Returns:
        Pipeline result dict compatible with ProcessResponse.

    Raises:
        ValueError: On invalid config or missing env vars.
        RuntimeError: On pipeline step failure.
    """
    from core.injector import inject_video

    start = time.time()
    llm_provider = options.get("llm_provider", "claude")
    lang = options.get("lang", "pl")

    # Step 1+2: Generate schema
    gen_result = await run_generate(video_url, llm_provider, lang)
    video_id = gen_result["video_id"]
    seo = gen_result["seo"]
    meta = gen_result["meta"]

    # Determine WP post ID
    final_wp_id = wp_post_id
    if final_wp_id is None:
        # Matcher: try to find WP post by youtube_id in WP REST API
        # For MVP: if not provided, we cannot inject — return schema only
        logger.warning("[process] No wp_post_id provided — skipping injection")
        return {
            "status": "ok",
            "video_id": video_id,
            "wp_post_id": None,
            "schema_generated": True,
            "injected": False,
            "youtube_updated": False,
            "processing_time_s": round(time.time() - start, 2),
            "focus_keyphrase": seo.get("focus_keyphrase"),
            "post_title": seo.get("post_title"),
            "error": None,
        }

    injected = False
    youtube_updated = False

    if options.get("auto_inject", True):
        # Step 3: Inject (sync → thread)
        inject_result = await asyncio.to_thread(
            inject_video,
            final_wp_id,
            video_id,
            seo,
            site_config["wp_base_url"],
            site_config["wp_user"],
            site_config["wp_app_password"],
            None,   # yt_api_key — optional, from env
            False,  # dry_run
            False,  # skip_thumbnail
            None,   # profile
        )
        injected = inject_result.get("ok", False)
        youtube_updated = inject_result.get("yt_update_ok", False)
        logger.info("[process] inject done: ok=%s yt_updated=%s", injected, youtube_updated)

    return {
        "status": "ok",
        "video_id": video_id,
        "wp_post_id": final_wp_id,
        "schema_generated": True,
        "injected": injected,
        "youtube_updated": youtube_updated,
        "processing_time_s": round(time.time() - start, 2),
        "focus_keyphrase": seo.get("focus_keyphrase"),
        "post_title": seo.get("post_title"),
        "error": None,
    }


def _create_wp_post(
    seo: dict,
    video_id: str,
    site_config: dict,
    post_status: str = "draft",
) -> dict:
    """Create a brand-new WordPress post via REST API and inject SEO schema.

    CO: Pomocnicza funkcja synchroniczna — wywoływana przez asyncio.to_thread.

    PO CO: Gdy /v1/inject nie otrzyma wp_post_id (nowy film, brak artykułu),
    automatycznie tworzy post na WordPressie zamiast wymagać podania ID.
    Używane przez pro/agency w trybie 'nowy artykuł' na dashboardzie.

    JAK:
    1. POST /wp/v2/posts bez ID — WP zwraca nowo nadany ID posta.
    2. inject_video() na nowym ID — wstrzykuje pełną treść + SEO schema.
    3. Zwraca dict zgodny z InjectResponse.

    Args:
        seo: SEO result dict from /v1/generate (schema_data w InjectRequest).
        video_id: YouTube video ID (wyodrębniony z video_url).
        site_config: Dict z wp_base_url, wp_user, wp_app_password.
        post_status: 'draft' lub 'publish'.

    Returns:
        Dict kompatybilny z InjectResponse.

    Raises:
        RuntimeError: Gdy WP REST API odmówi tworzenia posta.
    """
    from core.injector import inject_video, _make_auth, _strip_html

    wp_base_url = site_config["wp_base_url"]
    wp_user = site_config["wp_user"]
    wp_app_pass = site_config["wp_app_password"]
    auth = _make_auth(wp_user, wp_app_pass)

    # Build minimal post payload — title + status
    post_title = seo.get("post_title", "").strip() or seo.get("seo_title", "").strip() or video_id
    excerpt = _strip_html(seo.get("lead", ""))[:300] if seo.get("lead") else ""

    create_payload: dict = {
        "title": post_title,
        "status": post_status,
        "content": "",  # zostanie nadpisany przez inject_video.update_post
    }
    if excerpt:
        create_payload["excerpt"] = excerpt

    create_url = f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/posts"
    try:
        resp = requests.post(create_url, json=create_payload, auth=auth, timeout=20)
    except Exception as exc:
        logger.error("[inject] create_wp_post request failed: %s", exc)
        raise RuntimeError(f"WP REST create post failed: {exc}") from exc

    if resp.status_code not in (200, 201):
        logger.error(
            "[inject] create_wp_post HTTP %s: %s",
            resp.status_code, resp.text[:300],
        )
        raise RuntimeError(
            f"WP REST POST /posts returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    new_post_id: int = resp.json()["id"]
    post_link: str = resp.json().get("link", "")
    logger.info("[inject] New WP post created: #%s | %s", new_post_id, post_link)

    # Full SEO injection on the freshly created post
    inject_result = inject_video(
        new_post_id,
        video_id,
        seo,
        wp_base_url,
        wp_user,
        wp_app_pass,
        None,   # yt_api_key
        False,  # dry_run
        False,  # skip_thumbnail
        None,   # profile
    )

    return {
        "status": "ok" if inject_result.get("ok") else "error",
        "wp_post_id": new_post_id,
        "video_id": video_id,
        "rankmath_ok": inject_result.get("rankmath_ok", False),
        "youtube_updated": inject_result.get("yt_update_ok", False),
        "created": True,
        "post_url": inject_result.get("link") or post_link or None,
        "error": None if inject_result.get("ok") else "Injection failed after post creation — check logs",
    }


async def run_inject(
    wp_post_id: Optional[int],
    video_url: str,
    schema_data: dict,
    site_config: dict,
    post_status: str = "draft",
) -> dict:
    """Inject pre-generated schema into a WP post, or create a new post.

    CO: Główna funkcja pipeline dla endpointu POST /v1/inject.

    PO CO: Pozwala dashboardowi pro/agency wywołać jeden endpoint niezależnie
    od tego czy artykuł już istnieje na WordPressie. Usuwa konieczność szukania
    ID przed publikacją — jeśli brak ID, WP sam tworzy nowy post.

    JAK:
    - wp_post_id=None → _create_wp_post() → POST /wp/v2/posts + inject
    - wp_post_id=int  → inject_video()    → PATCH /wp/v2/posts/{id}

    Args:
        wp_post_id: WordPress post ID do aktualizacji. None = utwórz nowy.
        video_url: YouTube video URL (for video_id extraction).
        schema_data: Pre-generated SEO dict from /v1/generate.
        site_config: Dict with wp_base_url, wp_user, wp_app_password.
        post_status: Status nowego posta ('draft' | 'publish'). Ignorowany
            przy aktualizacji istniejącego posta.

    Returns:
        Dict compatible with InjectResponse.
    """
    from core.injector import inject_video

    video_id = _extract_video_id(video_url)
    logger.info(
        "[inject] wp_post_id=%s video_id=%s post_status=%s",
        wp_post_id, video_id, post_status if wp_post_id is None else "n/a",
    )

    if wp_post_id is None:
        # Brak ID → utwórz nowy post na WordPress
        logger.info("[inject] No wp_post_id — creating new WP post (status=%s)", post_status)
        result = await asyncio.to_thread(
            _create_wp_post,
            schema_data,
            video_id,
            site_config,
            post_status,
        )
        return result

    # Podane ID → aktualizuj istniejący post
    result = await asyncio.to_thread(
        inject_video,
        wp_post_id,
        video_id,
        schema_data,
        site_config["wp_base_url"],
        site_config["wp_user"],
        site_config["wp_app_password"],
        None,   # yt_api_key
        False,  # dry_run
        False,  # skip_thumbnail
        None,   # profile
    )
    return {
        "status": "ok" if result.get("ok") else "error",
        "wp_post_id": wp_post_id,
        "video_id": video_id,
        "rankmath_ok": result.get("rankmath_ok", False),
        "youtube_updated": result.get("yt_update_ok", False),
        "created": False,
        "post_url": result.get("link") or None,
        "error": None if result.get("ok") else "Injection failed — check logs",
    }
