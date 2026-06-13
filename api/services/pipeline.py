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
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
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


async def run_inject(wp_post_id: int, video_url: str, schema_data: dict,
                     site_config: dict) -> dict:
    """Inject pre-generated schema into a WP post.

    Args:
        wp_post_id: WordPress post ID.
        video_url: YouTube video URL (for video_id extraction).
        schema_data: Pre-generated SEO dict from /v1/generate.
        site_config: Dict with wp_base_url, wp_user, wp_app_password.

    Returns:
        Dict compatible with InjectResponse.
    """
    from core.injector import inject_video

    video_id = _extract_video_id(video_url)
    logger.info("[inject] wp_id=%s video_id=%s", wp_post_id, video_id)

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
        "error": None if result.get("ok") else "Injection failed — check logs",
    }
