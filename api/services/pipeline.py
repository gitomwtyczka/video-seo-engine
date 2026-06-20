"""VSE Pipeline Orchestration Service.

Wraps synchronous core/ functions for async FastAPI context.
All CPU/IO-bound core calls use asyncio.to_thread() to avoid blocking
the event loop.

Pipeline for POST /v1/process:
  1. Fetch: core.fetcher.process_video → metadata + VTT
  2. Match:  core.matcher (if wp_post_id not provided)
  3. Generate: core.generator.process_video → SEO schema dict
  4. Inject: core.injector.inject_video → WP REST patch

Local Runner Mode (LOCAL_RUNNER_MODE=true):
  Zamiast pobierać transkrypt bezpośrednio na VPS (zablokowane przez
  YouTube dla Oracle Cloud IP), pipeline tworzy job w tabeli transcript_jobs
  i czeka na wynik od Local Runner'a (Windows Service na PC Usera).

  Obsługa formatu __VTT__ (od v2.0, 2026-06-16):
  Runner wysyła segmenty z timestampami jako __VTT__ format.
  Pipeline konwertuje ten format do prawdziwego WebVTT (.vtt) pliku
  który core.generator.parse_vtt_full() może sparsowarc do anchor-matchowania.
  Bez tej konwersji chaptery pokazywały time=0.

SAAS Enrichment (2026-06-17, vse-dev-14):
  Krok 0 w run_generate(): jeśli SAAS_API_URL skonfigurowany w .env,
  pipeline pobiera frazy kluczowe z GSC i top pages portalu docelowego.
  Dane są przekazywane do generatora jako priority_keywords + internal_links.
  Integracja jest opcjonalna — jeśli SAAS niedostępny, pipeline działa jak dotać.

GSC Status Surfacing (2026-06-17, sup-worker-01, KROK 4):
  run_generate() teraz zwraca pole "gsc" z status/message/connect_url/upgrade_url.
  Generowanie artykułu NIE jest blokowane przez brak GSC.
  Caller (UI / API klient) widzi jawnie czy GSC było dostępne.

D5 Multi-keyword (2026-06-20, vse-dev-19):
  _fetch_saas_enrichment() zwraca pełny saas_data dict (nie tylko keywords).
  run_generate() zwraca saas_data w wynikowym dict.
  run_process() i run_inject() przekazują saas_data do inject_video() →
  build_focus_keywords() merguje GSC + Trends + LLM keyphrases.

D6b (2026-06-20, vse-dev-21):
  run_generate() accepts publication_type parameter and passes it to generator.
  run_process() reads publication_type from options dict.
"""
import asyncio
import logging
import os
import tempfile
import time
import uuid
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# Timeout pollowania na transkrypt od Local Runner'a
LOCAL_RUNNER_POLL_INTERVAL = 2    # sekund między check'ami
LOCAL_RUNNER_POLL_TIMEOUT = 120  # max sekund czekania


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


def _vtt_runner_to_webvtt(vtt_runner_text: str) -> str:
    """Konwertuje format __VTT__ z Local Runner'a do prawdziwego WebVTT."""
    import re
    lines = vtt_runner_text.split("\n")
    webvtt_parts = ["WEBVTT", ""]
    cue_index = 1
    segments = []

    pattern = re.compile(r'^\[(\d{2}):(\d{2})\] (.+)$')
    for line in lines:
        if line == "__VTT__" or not line.strip():
            continue
        m = pattern.match(line.strip())
        if m:
            minutes = int(m.group(1))
            seconds = int(m.group(2))
            text = m.group(3)
            start_sec = minutes * 60 + seconds
            segments.append((start_sec, text))

    for i, (start_sec, text) in enumerate(segments):
        if i + 1 < len(segments):
            end_sec = segments[i + 1][0]
        else:
            end_sec = start_sec + 5

        start_h, start_m, start_s = start_sec // 3600, (start_sec % 3600) // 60, start_sec % 60
        end_h, end_m, end_s = end_sec // 3600, (end_sec % 3600) // 60, end_sec % 60

        start_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d}.000"
        end_str = f"{end_h:02d}:{end_m:02d}:{end_s:02d}.000"

        webvtt_parts.append(str(cue_index))
        webvtt_parts.append(f"{start_str} --> {end_str}")
        webvtt_parts.append(text)
        webvtt_parts.append("")
        cue_index += 1

    result = "\n".join(webvtt_parts)
    logger.info(
        "[pipeline] Converted __VTT__ to WebVTT: %d segments, %d chars",
        len(segments), len(result),
    )
    return result


async def _create_transcript_job(video_url: str) -> str:
    """Tworzy job transkrypcji w DB i zwraca jego ID."""
    from api.db import AsyncSessionLocal
    from api.models.job import TranscriptJob

    async with AsyncSessionLocal() as db:
        job = TranscriptJob(video_url=video_url, status="pending")
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = str(job.id)
        logger.info("[pipeline] Created transcript job %s for %s", job_id, video_url)
        return job_id


async def _wait_for_transcript(job_id: str) -> str:
    """Polluje DB na transkrypt z job'a Local Runner'a."""
    from api.db import AsyncSessionLocal
    from api.models.job import TranscriptJob

    deadline = time.time() + LOCAL_RUNNER_POLL_TIMEOUT
    job_uuid = uuid.UUID(job_id)

    while time.time() < deadline:
        async with AsyncSessionLocal() as db:
            job = await db.get(TranscriptJob, job_uuid)
            if not job:
                raise RuntimeError(f"Job {job_id} disappeared from DB")

            if job.status == "fetched" and job.transcript:
                logger.info(
                    "[pipeline] Job %s fetched: %d chars",
                    job_id, len(job.transcript),
                )
                return job.transcript

            if job.status == "failed":
                raise RuntimeError(
                    f"Local Runner failed for job {job_id}: {job.error}"
                )

            logger.debug(
                "[pipeline] Job %s still %s — waiting...", job_id, job.status
            )

        await asyncio.sleep(LOCAL_RUNNER_POLL_INTERVAL)

    raise RuntimeError(
        f"Local Runner timeout: job {job_id} not fetched within "
        f"{LOCAL_RUNNER_POLL_TIMEOUT}s. Check if VSELocalRunner service is running."
    )


async def _fetch_transcript_local_runner(video_url: str) -> str:
    """Pełny flow pobrania transkryptu przez Local Runner."""
    job_id = await _create_transcript_job(video_url)
    logger.info(
        "[pipeline] LOCAL_RUNNER_MODE: job %s created, waiting for runner...",
        job_id,
    )
    transcript = await _wait_for_transcript(job_id)
    return transcript


async def _fetch_saas_enrichment(site_url: str) -> tuple[list[str], list[dict], dict, dict]:
    """Fetch SAAS SEO enrichment data for a portal."""
    _gsc_unavailable = {
        "status": "unavailable",
        "message": None,
        "connect_url": None,
        "upgrade_url": None,
    }
    _empty_saas: dict = {}

    saas_url = os.environ.get("SAAS_API_URL", "").strip()
    if not saas_url:
        logger.debug("[pipeline] SAAS_API_URL not set — skipping enrichment")
        return [], [], _gsc_unavailable, _empty_saas

    try:
        from api.services.saas_enricher import (
            get_saas_seo_data,
            extract_priority_keywords,
            extract_internal_links,
        )

        saas_data = await get_saas_seo_data(site_url)
        priority_keywords = extract_priority_keywords(saas_data)
        internal_links = extract_internal_links(saas_data)

        gsc_meta = {
            "status": saas_data.get("gsc_status", "unavailable"),
            "message": saas_data.get("gsc_message"),
            "connect_url": saas_data.get("gsc_connect_url"),
            "upgrade_url": saas_data.get("gsc_upgrade_url"),
        }

        logger.info(
            "[pipeline] SAAS enrichment for %s: %d keywords, %d links, %d trends, gsc_status=%s",
            site_url, len(priority_keywords), len(internal_links),
            len(saas_data.get("trends_keywords", [])), gsc_meta["status"],
        )
        return priority_keywords, internal_links, gsc_meta, saas_data

    except Exception as exc:
        logger.warning(
            "[pipeline] SAAS enrichment failed for %s: %s — continuing without",
            site_url, exc,
        )
        return [], [], _gsc_unavailable, _empty_saas


def _resolve_site_url_from_env() -> str:
    """Resolve the target portal URL for SAAS enrichment."""
    wp_url = os.environ.get("WP_BASE_URL", "").strip().rstrip("/")
    if wp_url:
        return wp_url + "/"
    return "https://prawy.pl/"


async def run_generate(
    video_url: str,
    llm_provider: str,
    lang: str,
    post_title_override: Optional[str] = None,
    publication_type: str = "full_analysis",
) -> dict:
    """Fetch transcript + generate SEO schema. No WP write.

    D6b: Accepts publication_type to control article format.
    Passes it to core.generator.process_video().

    Args:
        video_url: YouTube video URL or ID.
        llm_provider: 'claude' or 'gemini'.
        lang: Transcript language code (default 'pl').
        post_title_override: Optional title override instead of yt-dlp metadata.
        publication_type: Article type: 'full_analysis', 'watching_page', 'discover'.

    Returns:
        Dict with 'video_id', 'meta', 'seo', 'gsc', 'saas_data' keys.

    Raises:
        ValueError: On invalid URL or missing API key.
        RuntimeError: On fetcher/generator failure.
    """
    from core.fetcher import process_video as fetch_video
    from core.generator import process_video as generate_schema

    video_id = _extract_video_id(video_url)
    logger.info("[generate] video_id=%s provider=%s type=%s", video_id, llm_provider, publication_type)

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

    local_runner_mode = os.environ.get("LOCAL_RUNNER_MODE", "false").lower() == "true"

    # Step 0: SAAS enrichment
    site_url = _resolve_site_url_from_env()
    priority_keywords, internal_links, gsc_meta, saas_data = await _fetch_saas_enrichment(site_url)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Fetch metadata + transcript
        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)
        if not meta or meta.get("error"):
            raise RuntimeError(f"Fetch failed for {video_id}: {meta.get('error', 'unknown')}")

        if local_runner_mode:
            logger.info(
                "[generate] LOCAL_RUNNER_MODE=true — delegating transcript to Local Runner"
            )
            try:
                transcript_text = await _fetch_transcript_local_runner(
                    f"https://www.youtube.com/watch?v={video_id}"
                )
            except RuntimeError as e:
                raise RuntimeError(f"Local Runner transcript failed: {e}") from e

            import pathlib
            vtt_path = str(pathlib.Path(tmp_dir) / f"{video_id}.vtt")

            if transcript_text.startswith("__VTT__"):
                logger.info(
                    "[generate] __VTT__ format detected — converting to WebVTT for generator"
                )
                webvtt_content = _vtt_runner_to_webvtt(transcript_text)
                pathlib.Path(vtt_path).write_text(webvtt_content, encoding="utf-8")
            else:
                logger.warning(
                    "[generate] Plain text transcript (no timestamps) — "
                    "chapters will have approximate times. Upgrade runner to v2.0."
                )
                pathlib.Path(vtt_path).write_text(transcript_text, encoding="utf-8")

            meta["vtt_path"] = vtt_path
        else:
            vtt_path = meta.get("vtt_path")
            if not vtt_path:
                raise RuntimeError(
                    f"No transcript available for {video_id}. "
                    "Hint: set LOCAL_RUNNER_MODE=true and run VSELocalRunner on local PC."
                )

        post_title = post_title_override or meta.get("title", video_id)
        yt_url = meta.get("webpage_url", f"https://www.youtube.com/watch?v={video_id}")
        wp_id_placeholder = 0  # no WP ID for generate-only

        # 2. Generate schema (sync → thread) with SAAS enrichment + publication_type
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
            priority_keywords if priority_keywords else None,
            internal_links if internal_links else None,
            None,  # site_brand
            publication_type,  # D6b: publication type
        )

    logger.info("[generate] done: video_id=%s keyphrases=%r saas=%s gsc_status=%s type=%s",
                video_id, seo.get("focus_keyphrases", seo.get("focus_keyphrase", "?")),
                "enriched" if seo.get("saas_enriched") else "standalone",
                gsc_meta["status"], publication_type)
    return {
        "video_id": video_id,
        "meta": meta,
        "seo": seo,
        "gsc": gsc_meta,
        "saas_data": saas_data,
    }


async def run_process(video_url: str, site_config: dict, options: dict,
                      wp_post_id: Optional[int] = None) -> dict:
    """Full pipeline: fetch → generate → inject.

    D6b: Reads publication_type from options and passes to run_generate().
    """
    from core.injector import inject_video

    start = time.time()
    llm_provider = options.get("llm_provider", "claude")
    lang = options.get("lang", "pl")
    publication_type = options.get("publication_type", "full_analysis")  # D6b

    # Step 1+2: Generate schema
    gen_result = await run_generate(
        video_url, llm_provider, lang,
        publication_type=publication_type,  # D6b
    )
    video_id = gen_result["video_id"]
    seo = gen_result["seo"]
    meta = gen_result["meta"]
    saas_data = gen_result.get("saas_data")

    # Determine WP post ID
    final_wp_id = wp_post_id
    if final_wp_id is None:
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
        inject_result = await asyncio.to_thread(
            inject_video,
            final_wp_id,
            video_id,
            seo,
            site_config["wp_base_url"],
            site_config["wp_user"],
            site_config["wp_app_password"],
            None,   # yt_api_key
            False,  # dry_run
            False,  # skip_thumbnail
            None,   # profile
            saas_data,
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
    post_format: str = "video",
    saas_data: Optional[dict] = None,
) -> dict:
    """Create a brand-new WordPress post via REST API and inject SEO schema."""
    from core.injector import inject_video, _make_auth, _strip_html

    wp_base_url = site_config["wp_base_url"]
    wp_user = site_config["wp_user"]
    wp_app_pass = site_config["wp_app_password"]
    auth = _make_auth(wp_user, wp_app_pass)

    post_title = seo.get("post_title", "").strip() or seo.get("seo_title", "").strip() or video_id
    excerpt = _strip_html(seo.get("lead", ""))[:300] if seo.get("lead") else ""

    create_payload: dict = {
        "title": post_title,
        "status": post_status,
        "content": "",
        "format": post_format,
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
    logger.info("[inject] New WP post created: #%s | %s | format=%s", new_post_id, post_link, post_format)

    inject_result = inject_video(
        new_post_id,
        video_id,
        seo,
        wp_base_url,
        wp_user,
        wp_app_pass,
        None,
        False,
        False,
        None,
        saas_data,
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
    post_format: str = "video",
    saas_data: Optional[dict] = None,
) -> dict:
    """Inject pre-generated schema into a WP post, or create a new post."""
    from core.injector import inject_video

    video_id = _extract_video_id(video_url)
    logger.info(
        "[inject] wp_post_id=%s video_id=%s post_status=%s post_format=%s",
        wp_post_id, video_id,
        post_status if wp_post_id is None else "n/a",
        post_format if wp_post_id is None else "n/a",
    )

    if wp_post_id is None:
        logger.info("[inject] No wp_post_id — creating new WP post (status=%s, format=%s)", post_status, post_format)
        result = await asyncio.to_thread(
            _create_wp_post,
            schema_data,
            video_id,
            site_config,
            post_status,
            post_format,
            saas_data,
        )
        return result

    result = await asyncio.to_thread(
        inject_video,
        wp_post_id,
        video_id,
        schema_data,
        site_config["wp_base_url"],
        site_config["wp_user"],
        site_config["wp_app_password"],
        None,
        False,
        False,
        None,
        saas_data,
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
