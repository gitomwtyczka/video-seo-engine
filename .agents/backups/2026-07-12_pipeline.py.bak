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
  który core.generator.parse_vtt_full() może sparować do anchor-matchowania.
  Bez tej konwersji chaptery pokazywały time=0.

SAAS Enrichment (2026-06-17, vse-dev-14):
  Krok 0 w run_generate(): jeśli SAAS_API_URL skonfigurowany w .env,
  pipeline pobiera frazy kluczowe z GSC i top pages portalu docelowego.
  Dane są przekazywane do generatora jako priority_keywords + internal_links.
  Integracja jest opcjonalna — jeśli SAAS niedostępny, pipeline działa jak dotad.

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

D8 Internal Links (2026-06-20, vse-dev-24):
  CO: Fallback internal links z WP REST API gdy SAAS nie zwraca top_pages.
  PO CO: SAAS wymaga GSC (nie podłączony) → top_pages puste → LLM nie dostaje
  linków wewnętrznych → RankMath obniża scoring. WP API jest zawsze dostępne.
  JAK: _fetch_wp_internal_links() pobiera ostatnie posty z WP REST API,
  filtruje self-links (ten sam video_id), i przekazuje do generatora.
  Fallback aktywuje się TYLKO gdy SAAS nie zwrócił internal_links.

D9 (2026-06-20, vse-dev-23):
  run_generate() accepts profile_id parameter.
  When profile_id is provided, loads profiles/{id}.yaml to determine:
    - site_url for SAAS enrichment (from wp_base_url)
    - site_brand for generator
  Backward compatible — without profile_id, falls back to env vars.

D11 Video Screenshots (2026-06-21, vse-dev-26):
  CO: Pobiera thumbnails z YouTube + opisy z SAAS Vision API (lub LLM fallback).
  PO CO: Artykuły z obrazkami rankują wyżej w Google i Google Discover.
         ImageObject w JSON-LD jest wymagany przez RankMath do 80+ score.
  JAK: Po Step 1 (fetch) dodaje Step 1b (thumbnails) + Step 1c (SAAS Vision API
       opisy obrazów). SAAS primary, LLM fallback. Wynik w seo["image_data"].

FIX A (2026-07-10, vse-dev-01):
  CO: Graceful degradation — pipeline nie crasha gdy brak transkryptu.
  PO CO: Filmy bez napisów (np. livestreamy, część treningowych) do tej pory
  rzucały RuntimeError i user dostał komunikat błędu zamiast SEO.
  Teraz pipeline generuje częściowe SEO z tytułu + opisu — bez chapterków/FAQ.
  JAK:
    - LOCAL_RUNNER_MODE=true: RuntimeError z "No transcript available" → vtt_path=None
    - LOCAL_RUNNER_MODE=false: brak vtt_path w meta → vtt_path=None (nie rzucamy)
    - generate_schema() wywołane z vtt_path=None → generate_schema_without_transcript()
    - run_generate() zwraca has_transcript=False, partial_result=True w wyniku
    - meta przekazywane do generate_schema dla opisu/duration w trybie partial
"""
import asyncio
import logging
import os
import tempfile
import time
import uuid
from typing import Optional

import httpx
import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy import select, desc
from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob
from api.models.portal import WpPortal

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
                # FIX A: propagate runner failure reason for upstream handling
                error_msg = job.error or ""
                if "No transcript" in error_msg or "no transcript" in error_msg.lower():
                    raise RuntimeError(
                        f"No transcript available for job {job_id}: {error_msg}"
                    )
                raise RuntimeError(
                    f"Local Runner failed for job {job_id}: {error_msg}"
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
    return ""


def _load_profile_config(profile_id: str) -> Optional[dict]:
    """Load a YAML profile by ID for pipeline configuration."""
    import yaml

    profile_path = os.path.join(os.getcwd(), "profiles", f"{profile_id}.yaml")
    if not os.path.isfile(profile_path):
        logger.warning("[pipeline] Profile '%s' not found at %s", profile_id, profile_path)
        return None

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            logger.info("[pipeline] Loaded profile '%s': %s", profile_id, data.get("display_name", "?"))
            return data
    except Exception as exc:
        logger.error("[pipeline] Failed to load profile '%s': %s", profile_id, exc)

    return None


def _resolve_site_url_from_profile(profile: dict) -> str:
    """Resolve site URL from profile config for SAAS enrichment."""
    wp_url = profile.get("wp_base_url", "").strip().rstrip("/")
    # wp_base_url may contain ${env_var} placeholders — resolve them
    if wp_url.startswith("${") and wp_url.endswith("}"):
        env_var = wp_url[2:-1]
        wp_url = os.environ.get(env_var, "").strip().rstrip("/")
    if wp_url:
        return wp_url + "/"
    return _resolve_site_url_from_env()


async def _fetch_wp_internal_links(
    wp_base_url: str,
    current_video_id: str = "",
    max_links: int = 10,
) -> list[dict]:
    """Fetch recent published posts from WP REST API as internal link suggestions."""
    endpoint = f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/posts"
    params = {
        "per_page": max_links + 5,  # fetch extra to account for self-link filtering
        "orderby": "date",
        "status": "publish",
        "_fields": "id,title,link",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, params=params)

        if response.status_code != 200:
            logger.warning(
                "[pipeline] D8 WP internal links: HTTP %d from %s",
                response.status_code, wp_base_url,
            )
            return []

        posts = response.json()
        links: list[dict] = []
        for post in posts:
            url = post.get("link", "")
            title_obj = post.get("title", {})
            title = (
                title_obj.get("rendered", "")
                if isinstance(title_obj, dict)
                else str(title_obj)
            )

            if not url:
                continue
            # Skip self-link: if current video_id appears in post URL
            if current_video_id and current_video_id in url:
                continue

            links.append({"url": url, "title": title})
            if len(links) >= max_links:
                break

        logger.info(
            "[pipeline] D8 WP internal links: %d links from %s (filtered from %d posts)",
            len(links), wp_base_url, len(posts),
        )
        return links

    except Exception as exc:
        logger.warning(
            "[pipeline] D8 WP internal links failed for %s: %s — continuing without",
            wp_base_url, exc,
        )
        return []


# ============================================================
# D11: SAAS Vision API — image description via GPT-4o Vision
# ============================================================

async def _describe_image_via_saas(
    image_url: str,
    article_title: str,
    focus_keywords: list[str],
    site_brand: str = "",
) -> Optional[dict]:
    """Call SAAS Vision API to get SEO-optimized image description."""
    saas_url = os.environ.get("SAAS_API_URL", "").strip().rstrip("/")
    token = os.environ.get("EXTERNAL_API_TOKEN", "").strip()
    if not saas_url or not token:
        logger.debug("[pipeline] D11 SAAS Vision: URL or token not set — skipping")
        return None

    endpoint = f"{saas_url}/api/external/describe-image"
    payload = {
        "image_url": image_url,
        "context": {
            "article_title": article_title,
            "focus_keywords": focus_keywords,
            "site_brand": site_brand,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            descriptions = data.get("descriptions")
            if descriptions:
                logger.info(
                    "[pipeline] D11 SAAS Vision OK: alt=%r",
                    descriptions.get("alt_text", "?")[:60],
                )
                return descriptions
            logger.warning("[pipeline] D11 SAAS Vision: 200 but no descriptions in response")
            return None
        logger.warning(
            "[pipeline] D11 SAAS Vision: HTTP %d from %s",
            resp.status_code, endpoint,
        )
        return None
    except Exception as exc:
        logger.warning("[pipeline] D11 SAAS Vision failed: %s — using LLM fallback", exc)
        return None


async def run_generate(
    video_url: str,
    llm_provider: str,
    lang: str,
    post_title_override: Optional[str] = None,
    publication_type: str = "full_analysis",
    portal_id: Optional[str] = None,
) -> dict:
    """Fetch transcript + generate SEO schema. No WP write.

    FIX A: When transcript is unavailable, continues with vtt_path=None
    and generates partial SEO schema (VideoObject + meta, no chapters/FAQ).
    Returns has_transcript=False and partial_result=True in result dict.
    """
    from core.fetcher import process_video as fetch_video
    from core.fetcher import fetch_video_thumbnails
    from core.generator import process_video as generate_schema

    video_id = _extract_video_id(video_url)
    logger.info("[generate] video_id=%s provider=%s type=%s portal_id=%s",
                video_id, llm_provider, publication_type, portal_id)

    profile_config = None
    site_brand = None
    profile_id = None

    # D9/VSE-DEV: Load profile config via portal_id
    if portal_id:
        async with AsyncSessionLocal() as db:
            try:
                uid = uuid.UUID(portal_id)
                portal = await db.get(WpPortal, uid)
                if portal and portal.profile_id:
                    profile_id = portal.profile_id
            except ValueError:
                pass

        if profile_id:
            profile_config = _load_profile_config(profile_id)
            if profile_config:
                site_brand = profile_config.get("site_brand")

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

    if profile_config:
        site_url = _resolve_site_url_from_profile(profile_config)
    else:
        site_url = _resolve_site_url_from_env()

    if site_url:
        priority_keywords, internal_links, gsc_meta, saas_data = await _fetch_saas_enrichment(site_url)
    else:
        priority_keywords, internal_links, gsc_meta, saas_data = [], [], {
            "status": "unavailable",
            "message": None,
            "connect_url": None,
            "upgrade_url": None,
        }, {}

    if not internal_links:
        wp_internal = await _fetch_wp_internal_links(site_url, video_id)
        if wp_internal:
            internal_links = wp_internal
            logger.info(
                "[generate] D8 internal links fallback: %d links from WP API",
                len(internal_links),
            )

    with tempfile.TemporaryDirectory() as tmp_dir:
        meta = await asyncio.to_thread(fetch_video, video_id, tmp_dir, lang)
        if not meta or meta.get("error"):
            raise RuntimeError(f"Fetch failed for {video_id}: {meta.get('error', 'unknown')}")

        num_screenshots = 2 if publication_type in ("full_analysis", "discover") else 1
        thumbnails = await asyncio.to_thread(
            fetch_video_thumbnails, video_id, tmp_dir, num_screenshots
        )
        logger.info(
            "[generate] D11 thumbnails: %d downloaded for %s (wanted %d)",
            len(thumbnails), video_id, num_screenshots,
        )

        image_data: list[dict] = []
        post_title_for_desc = post_title_override or meta.get("title", video_id)
        keyphrases_for_desc = priority_keywords[:3] if priority_keywords else []

        for idx, thumb in enumerate(thumbnails):
            yt_thumb_url = thumb.get("url", "")
            if not yt_thumb_url:
                continue

            saas_desc = await _describe_image_via_saas(
                yt_thumb_url,
                post_title_for_desc,
                keyphrases_for_desc,
                site_brand or "",
            )
            if saas_desc:
                image_data.append({
                    "path": thumb["path"],
                    "url": yt_thumb_url,
                    "width": thumb.get("width", 1280),
                    "height": thumb.get("height", 720),
                    "source": thumb.get("source", "youtube"),
                    "descriptions": saas_desc,
                    "description_source": "saas_vision",
                })
                logger.info(
                    "[generate] D11 image[%d]: SAAS Vision description OK", idx,
                )
            else:
                image_data.append({
                    "path": thumb["path"],
                    "url": yt_thumb_url,
                    "width": thumb.get("width", 1280),
                    "height": thumb.get("height", 720),
                    "source": thumb.get("source", "youtube"),
                    "descriptions": None,
                    "description_source": "pending_llm_fallback",
                })
                logger.info(
                    "[generate] D11 image[%d]: SAAS Vision unavailable — LLM fallback pending", idx,
                )

        # FIX A: Transcript branch with graceful degradation
        vtt_path: Optional[str] = None
        has_transcript = True

        if local_runner_mode:
            logger.info(
                "[generate] LOCAL_RUNNER_MODE=true — delegating transcript to Local Runner"
            )
            try:
                transcript_text = await _fetch_transcript_local_runner(
                    f"https://www.youtube.com/watch?v={video_id}"
                )

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

            except RuntimeError as e:
                exc_str = str(e)
                # FIX A: Graceful degradation — no transcript → continue without
                if "No transcript available" in exc_str:
                    logger.warning(
                        "[generate] FIX A: No transcript available for %s — "
                        "continuing without (partial_result=True)", video_id
                    )
                    vtt_path = None
                    has_transcript = False
                else:
                    # Other errors (timeout, DB failure) — re-raise
                    raise RuntimeError(f"Local Runner transcript failed: {e}") from e
        else:
            # FIX A: No hard RuntimeError when vtt_path missing — graceful degradation
            vtt_path = meta.get("vtt_path")
            if not vtt_path:
                logger.warning(
                    "[generate] FIX A: No transcript (vtt_path) for %s — "
                    "continuing without (partial_result=True)", video_id
                )
                has_transcript = False

        post_title = post_title_override or meta.get("title", video_id)
        yt_url = meta.get("webpage_url", f"https://www.youtube.com/watch?v={video_id}")
        wp_id_placeholder = 0

        seo = await asyncio.to_thread(
            generate_schema,
            video_id,
            wp_id_placeholder,
            post_title,
            yt_url,
            vtt_path,  # FIX A: may be None — generator handles it
            api_key,
            None,
            0,
            llm_provider,
            priority_keywords if priority_keywords else None,
            internal_links if internal_links else None,
            site_brand,
            publication_type,
            meta,  # FIX A: pass meta for partial schema (description, duration)
        )

        llm_img_descs = seo.get("image_descriptions", [])
        for idx, img in enumerate(image_data):
            if img["descriptions"] is None and idx < len(llm_img_descs):
                llm_desc = llm_img_descs[idx]
                img["descriptions"] = {
                    "alt_text": llm_desc.get("alt_text", ""),
                    "title": llm_desc.get("alt_text", "")[:100],
                    "caption": llm_desc.get("caption", ""),
                    "description": llm_desc.get("caption", ""),
                    "filename": None,
                }
                img["description_source"] = "llm_fallback"
                logger.info(
                    "[generate] D11 image[%d]: filled from LLM fallback alt=%r",
                    idx, img["descriptions"]["alt_text"][:60],
                )
            elif img["descriptions"] is None:
                focus_kp = seo.get("focus_keyphrase", "")
                img["descriptions"] = {
                    "alt_text": f"{focus_kp} — kadr z materiału wideo" if focus_kp else "Kadr z materiału wideo",
                    "title": seo.get("post_title", "")[:100],
                    "caption": f"Kadr z nagrania: {seo.get('post_title', '')[:80]}",
                    "description": "",
                    "filename": None,
                }
                img["description_source"] = "generic_fallback"
                logger.warning(
                    "[generate] D11 image[%d]: using generic fallback (no SAAS, no LLM desc)", idx,
                )

        seo["image_data"] = image_data

    partial_result = not has_transcript
    logger.info(
        "[generate] done: video_id=%s keyphrases=%r saas=%s gsc_status=%s type=%s "
        "portal_id=%s images=%d has_transcript=%s partial=%s",
        video_id, seo.get("focus_keyphrases", seo.get("focus_keyphrase", "?")),
        "enriched" if seo.get("saas_enriched") else "standalone",
        gsc_meta["status"], publication_type, portal_id, len(image_data),
        has_transcript, partial_result,
    )
    return {
        "video_id": video_id,
        "meta": meta,
        "seo": seo,
        "gsc": gsc_meta,
        "saas_data": saas_data,
        "has_transcript": has_transcript,    # FIX A
        "partial_result": partial_result,    # FIX A
    }


async def run_process(video_url: str, site_config: dict, options: dict,
                      wp_post_id: Optional[int] = None) -> dict:
    """Full pipeline: fetch → generate → inject."""
    from core.injector import inject_video

    start = time.time()
    llm_provider = options.get("llm_provider", "claude")
    lang = options.get("lang", "pl")
    publication_type = options.get("publication_type", "full_analysis")

    gen_result = await run_generate(
        video_url, llm_provider, lang,
        publication_type=publication_type,
    )
    video_id = gen_result["video_id"]
    seo = gen_result["seo"]
    meta = gen_result["meta"]
    saas_data = gen_result.get("saas_data")

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
            None,
            False,
            False,
            None,
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
    wp_base_url: str,
    wp_user: str,
    wp_app_pass: str,
    profile_config: Optional[dict] = None,
    post_status: str = "draft",
    post_format: str = "video",
    saas_data: Optional[dict] = None,
) -> dict:
    """Create a brand-new WordPress post via REST API and inject SEO schema."""
    from core.injector import inject_video, _make_auth, _strip_html

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
        profile_config,
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
    yt_channel_ids: Optional[list[str]] = None,
) -> dict:
    """Inject pre-generated schema into a WP post, or create a new post."""
    from core.injector import inject_video

    video_id = _extract_video_id(video_url)

    # Resolving Profile Config from DB via Job (Do NOT overwrite site_config credentials!)
    wp_base_url = site_config["wp_base_url"]
    wp_user = site_config["wp_user"]
    wp_app_password = site_config["wp_app_password"]
    profile_config = None

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TranscriptJob)
            .where(TranscriptJob.video_url.contains(video_id))
            .order_by(desc(TranscriptJob.created_at))
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job and job.portal_id:
            try:
                uid = uuid.UUID(job.portal_id)
                portal = await db.get(WpPortal, uid)
                if portal and portal.profile_id:
                    profile_config = _load_profile_config(portal.profile_id)
            except ValueError:
                pass

    logger.info(
        "[inject] wp_post_id=%s video_id=%s post_status=%s post_format=%s portal_overridden=%s",
        wp_post_id, video_id,
        post_status if wp_post_id is None else "n/a",
        post_format if wp_post_id is None else "n/a",
        bool(profile_config is not None)
    )

    if wp_post_id is None:
        logger.info("[inject] No wp_post_id — creating new WP post (status=%s, format=%s)", post_status, post_format)
        final_result = await asyncio.to_thread(
            _create_wp_post,
            schema_data,
            video_id,
            wp_base_url,
            wp_user,
            wp_app_password,
            profile_config,
            post_status,
            post_format,
            saas_data,
        )
    else:
        raw_result = await asyncio.to_thread(
            inject_video,
            wp_post_id,
            video_id,
            schema_data,
            wp_base_url,
            wp_user,
            wp_app_password,
            None,
            False,
            False,
            profile_config,
            saas_data,
        )
        final_result = {
            "status": "ok" if raw_result.get("ok") else "error",
            "wp_post_id": wp_post_id,
            "video_id": video_id,
            "rankmath_ok": raw_result.get("rankmath_ok", False),
            "youtube_updated": raw_result.get("yt_update_ok", False),
            "created": False,
            "post_url": raw_result.get("link") or None,
            "error": None if raw_result.get("ok") else "Injection failed — check logs",
        }

    post_url = final_result.get("post_url")
    yt_results = []

    final_result["yt_channels"] = yt_results
    return final_result
