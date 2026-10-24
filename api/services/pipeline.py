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

KROK B (2026-10-20, vse-dev-01):
  CO: Systemowa naprawa pobierania transkryptów + twarda blokada anty-konfabulacyjna.
  PO CO: Zapobieganie generowaniu artykułów z samego tytułu (konfabulacja AI)
         oraz poprawne dopasowanie kanału YouTube OAuth po channel_id filmu.
  JAK:
    1. OAuth Captions: pobiera wszystkie aktywne kanały użytkownika z youtube_channels,
       dopasowuje channel_id filmu z YouTube API v3 (snippet.channelId), a w razie
       potrzeby próbuje kolejne kanały użytkownika (sortowane po updated_at DESC).
    2. DB Cache: przed utworzeniem nowego joba sprawdza w transcript_jobs istniejący
       rekord z niepustym transkryptem (len >= 50) dla danego video_id.
    3. Local Runner: LOCAL_RUNNER_POLL_TIMEOUT=90s, LOCAL_RUNNER_POLL_INTERVAL=2.0s
       + in-memory asyncio.Event per job_id wybudzający _wait_for_transcript w 0.001s
       natychmiast po odebraniu POST /v1/jobs/{job_id}/result (z fallbackiem 2.0s DB poll).
    4. Twarda blokada anty-konfabulacyjna: jeśli po wszystkich próbach brak transkryptu
       (< 50 znaków), rzuca ValueError (0 pobranych kredytów, brak wywołania LLM).

K4 (2026-10-21, vse-dev-k4):
  - Tworzenie job_id (status=processing, wiersz per kliknięcie) na początku run_generate().
  - Scoping user_id (R1/R2) w _get_cached_transcript_from_db: nigdy nie czytaj transkryptu innego usera.
  - run_inject rezolwuje profile_id/schema z req.portal_id lub req.job_id, usuwając ślepe zapytanie o ostatni job.

K4.1 (2026-10-24, vse-dev-k4-1):
  - Local runner reuse existing_job_id in _create_transcript_job to eliminate duplicate rows.
"""
import asyncio
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import requests
from requests.auth import HTTPBasicAuth
from sqlalchemy import select, desc
from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob
from api.models.portal import WpPortal

logger = logging.getLogger(__name__)

# Timeout pollowania na transkrypt od Local Runner'a (domyślnie 90s, interwał 2.0s + natychmiastowe wybudzenie asyncio.Event)
LOCAL_RUNNER_POLL_INTERVAL = float(os.environ.get("LOCAL_RUNNER_POLL_INTERVAL", "2.0"))
LOCAL_RUNNER_POLL_TIMEOUT = int(os.environ.get("LOCAL_RUNNER_POLL_TIMEOUT", "90"))

# In-memory event map do natychmiastowego (0.001s) wybudzania _wait_for_transcript po POST /v1/jobs/{id}/result
_job_completion_events: dict[str, asyncio.Event] = {}


def notify_job_transcript_ready(job_id: str) -> None:
    """Wybudza oczekujący _wait_for_transcript natychmiast po zapisaniu transkryptu przez Local Runner."""
    ev = _job_completion_events.get(str(job_id))
    if ev is not None:
        ev.set()


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL or return as-is."""
    if not url:
        return ""
    if url.startswith("audio://"):
        return url[len("audio://"):]
    if url.startswith("audio_"):
        return url
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


async def _get_cached_transcript_from_db(
    video_id: str,
    user_id: Optional[str | uuid.UUID] = None,
) -> Optional[str]:
    """Sprawdza w tabeli transcript_jobs czy dla danego video_id i usera istnieje już niepusty transkrypt (>= 50 znaków).

    R1/R2 Security: Nigdy nie czytaj transkrypcji innego użytkownika.
    """
    if not video_id:
        return None
    try:
        uid = None
        if user_id:
            try:
                uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
            except (ValueError, TypeError):
                pass

        async with AsyncSessionLocal() as db:
            stmt = (
                select(TranscriptJob)
                .where(TranscriptJob.video_url.contains(video_id))
                .where(TranscriptJob.transcript.isnot(None))
            )
            if uid is not None:
                stmt = stmt.where(TranscriptJob.user_id == uid)
            else:
                stmt = stmt.where(TranscriptJob.user_id.is_(None))

            result = await db.execute(
                stmt.order_by(desc(TranscriptJob.updated_at), desc(TranscriptJob.created_at)).limit(5)
            )
            jobs = result.scalars().all()
            for job in jobs:
                if job.transcript and len(job.transcript.strip()) >= 50:
                    logger.info(
                        "[pipeline] DB Cache HIT for %s (user_id=%s): job %s (%d chars, status=%s)",
                        video_id, uid, job.id, len(job.transcript), job.status,
                    )
                    return job.transcript
    except Exception as exc:
        logger.warning("[pipeline] DB transcript cache check failed for %s: %s", video_id, exc)
    return None


async def _create_transcript_job(
    video_url: str,
    user_id: Optional[str] = None,
    existing_job_id: Optional[str] = None,
) -> str:
    """Tworzy lub aktualizuje job transkrypcji w DB i zwraca jego ID."""
    uid = None
    if user_id:
        try:
            uid = uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            pass

    async with AsyncSessionLocal() as db:
        if existing_job_id:
            try:
                j_uuid = uuid.UUID(str(existing_job_id))
                job = await db.get(TranscriptJob, j_uuid)
                if job:
                    job.status = "pending"
                    job.updated_at = datetime.now(timezone.utc)
                    if uid is not None and job.user_id is None:
                        job.user_id = uid
                    await db.commit()
                    logger.info("[pipeline] Reusing existing transcript job %s (user_id=%s) for %s", existing_job_id, uid, video_url)
                    return str(job.id)
            except (ValueError, TypeError) as exc:
                logger.warning("[pipeline] Invalid existing_job_id %s: %s", existing_job_id, exc)

        job = TranscriptJob(video_url=video_url, status="pending", user_id=uid)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = str(job.id)
        logger.info("[pipeline] Created transcript job %s (user_id=%s) for %s", job_id, uid, video_url)
        return job_id


async def _wait_for_transcript(job_id: str) -> str:
    """Czeka na transkrypt z job'a Local Runner'a: natychmiastowe wybudzenie przez asyncio.Event (0.001s) + fallback DB poll co 2.0s."""
    deadline = time.time() + LOCAL_RUNNER_POLL_TIMEOUT
    job_uuid = uuid.UUID(job_id)
    job_key = str(job_uuid)
    ev = _job_completion_events.setdefault(job_key, asyncio.Event())

    try:
        while time.time() < deadline:
            async with AsyncSessionLocal() as db:
                job = await db.get(TranscriptJob, job_uuid)
                if not job:
                    raise RuntimeError(f"Job {job_id} disappeared from DB")

                if job.transcript and len(job.transcript.strip()) >= 50:
                    logger.info(
                        "[pipeline] Job %s transcript ready (status=%s): %d chars — proceeding immediately!",
                        job_id, job.status, len(job.transcript),
                    )
                    return job.transcript

                if job.status in ("fetched", "done") and job.transcript:
                    logger.info(
                        "[pipeline] Job %s fetched: %d chars",
                        job_id, len(job.transcript),
                    )
                    return job.transcript

                if job.status == "failed":
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

            remaining = deadline - time.time()
            if remaining <= 0:
                break
            wait_timeout = min(LOCAL_RUNNER_POLL_INTERVAL, remaining)
            try:
                await asyncio.wait_for(ev.wait(), timeout=wait_timeout)
                ev.clear()
            except asyncio.TimeoutError:
                pass
    finally:
        _job_completion_events.pop(job_key, None)

    # Po upływie timeoutu brak odpowiedzi od Local Runnera — oznacz job jako cloud_fallback, aby nie wisiał w pending
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(TranscriptJob, job_uuid)
            if job and job.status == "pending":
                job.status = "cloud_fallback"
                await db.commit()
    except Exception:
        pass

    raise RuntimeError(
        f"Local Runner timeout: job {job_id} not fetched within "
        f"{LOCAL_RUNNER_POLL_TIMEOUT}s — switching to Cloud Fetch."
    )


async def _fetch_transcript_local_runner(
    video_url: str,
    user_id: Optional[str] = None,
    existing_job_id: Optional[str] = None,
) -> str:
    """Pełny flow pobrania transkryptu przez Local Runner (z uprzednim sprawdzeniem DB Cache)."""
    video_id = _extract_video_id(video_url)
    cached = await _get_cached_transcript_from_db(video_id, user_id=user_id)
    if cached:
        return cached

    job_id = await _create_transcript_job(video_url, user_id=user_id, existing_job_id=existing_job_id)
    logger.info(
        "[pipeline] LOCAL_RUNNER_MODE: job %s created/reused (user_id=%s), waiting up to %ds for runner...",
        job_id,
        user_id,
        LOCAL_RUNNER_POLL_TIMEOUT,
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


async def fetch_yt_description_from_pressai(
    vtt_content: str,
    video_title: str,
    video_id: str,
    chapters: list,
    focus_keyphrases: list,
    wp_url: str,
    portal_name: str = "",
    portal_topic: str = "",
) -> dict | None:
    """
    Wywołuje PressAI API po opis YouTube.
    Zwraca dict z polami: youtube_description_body, youtube_mid_cta,
    youtube_credits, youtube_hashtags.
    Zwraca None jeśli PressAI niedostępny (fallback do generatora).
    """
    import httpx
    saas_url = (os.environ.get("SAAS_API_URL") or os.environ.get("PRESSAI_API_URL") or "").strip().rstrip("/")
    saas_token = (os.environ.get("SAAS_API_TOKEN") or os.environ.get("PRESSAI_EXTERNAL_TOKEN") or os.environ.get("EXTERNAL_API_TOKEN") or "").strip()
    if not saas_url or not saas_token:
        logger.warning("[pipeline] SAAS_API_URL/TOKEN not set — skipping PressAI YT generation")
        return None

    endpoint = f"{saas_url}/api/external/generate-yt-description"
    payload = {
        "vtt_content": vtt_content[:80000] if vtt_content else "",
        "video_title": video_title,
        "video_id": video_id,
        "chapters": chapters,
        "focus_keyphrases": focus_keyphrases,
        "wp_url": wp_url,
        "portal_name": portal_name,
        "portal_topic": portal_topic,
    }
    headers = {"Authorization": f"Bearer {saas_token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("[pipeline] PressAI YT description received for %s", video_id)
            return data
        else:
            logger.warning("[pipeline] PressAI YT endpoint HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as exc:
        logger.warning("[pipeline] PressAI YT endpoint error: %s — using fallback", exc)
        return None


async def _get_user_yt_access_tokens(
    user_id: Optional[str],
    preferred_channel_id: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Pobiera i odświeża tokeny OAuth 2.0 YouTube dla wszystkich aktywnych kanałów użytkownika.

    Zwraca listę krotek (youtube_channel_id, access_token) posortowaną tak, że:
      1. Jeśli podano preferred_channel_id (channel_id filmu z YouTube API v3), kanał będący
         właścicielem filmu jest na pierwszym miejscu!
      2. Pozostałe aktywne kanały użytkownika są posortowane według updated_at DESC (od najnowszego).
    """
    if not user_id:
        return []
    try:
        uid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return []

    tokens: list[tuple[str, str]] = []
    try:
        from google.auth.transport.requests import Request
        from api.models.youtube_channel import YouTubeChannel
        from api.core.youtube_publish import _build_credentials, _save_refreshed_token

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(YouTubeChannel)
                .where(
                    YouTubeChannel.user_id == uid,
                    YouTubeChannel.is_active == True,  # noqa: E712
                )
                .order_by(
                    YouTubeChannel.updated_at.desc().nullslast(),
                    YouTubeChannel.is_default.desc(),
                    YouTubeChannel.created_at.desc(),
                )
            )
            channels = list(result.scalars().all())
            if preferred_channel_id:
                channels.sort(
                    key=lambda ch: 0 if ch.youtube_channel_id == preferred_channel_id else 1
                )

            for channel in channels:
                if not channel.refresh_token:
                    continue
                try:
                    creds = _build_credentials(channel)
                    await asyncio.to_thread(creds.refresh, Request())
                    if creds.refresh_token and creds.refresh_token != channel.refresh_token:
                        channel.refresh_token = creds.refresh_token
                    if hasattr(channel, "access_token"):
                        setattr(channel, "access_token", creds.token)
                    if hasattr(channel, "token_expiry") and getattr(creds, "expiry", None):
                        setattr(channel, "token_expiry", creds.expiry)
                    channel.updated_at = datetime.now(timezone.utc)
                    await db.commit()
                    if creds.token:
                        logger.info(
                            "[pipeline] Refreshed YT OAuth access_token for channel %s (%s, user=%s)",
                            channel.youtube_channel_id, channel.title or "?", uid,
                        )
                        tokens.append((channel.youtube_channel_id, creds.token))
                except Exception as ch_exc:
                    logger.warning(
                        "[pipeline] Could not refresh YT OAuth token for channel %s: %s",
                        channel.youtube_channel_id, ch_exc,
                    )
    except Exception as exc:
        logger.warning("[pipeline] _get_user_yt_access_tokens failed for user %s: %s", user_id, exc)
    return tokens


async def _get_user_yt_access_token(
    user_id: Optional[str],
    preferred_channel_id: Optional[str] = None,
) -> Optional[str]:
    """Backward-compatible helper returning the best matching OAuth access_token for the user."""
    tokens = await _get_user_yt_access_tokens(user_id, preferred_channel_id=preferred_channel_id)
    return tokens[0][1] if tokens else None


def _count_real_transcript_chars(vtt_path: Optional[str]) -> int:
    """Zwraca liczbę znaków faktycznego tekstu wypowiedzi w pliku VTT/transkrypcie."""
    if not vtt_path or not os.path.exists(vtt_path):
        return 0
    try:
        import re
        with open(vtt_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        clean_lines = []
        for line in content.splitlines():
            s = line.strip()
            if (
                not s
                or s == "__VTT__"
                or s.startswith("WEBVTT")
                or "-->" in s
                or s.startswith("Kind:")
                or s.startswith("Language:")
                or s.isdigit()
            ):
                continue
            s = re.sub(r"^\[\d{2}:\d{2}\]\s*", "", s)
            s = re.sub(r"<[^>]+>", "", s).strip()
            if s:
                clean_lines.append(s)
        return len(" ".join(clean_lines).strip())
    except Exception:
        return 0


async def run_generate(
    video_url: str,
    llm_provider: str,
    lang: str,
    post_title_override: Optional[str] = None,
    publication_type: str = "full_analysis",
    portal_id: Optional[str] = None,
    user_id: Optional[str] = None,
    target_lang: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Fetch transcript + generate SEO schema. No WP write.

    KROK B (Hard Anti-Confabulation Guard):
      - Nigdy nie generuje artykułu ani pakietu SEO bez transkryptu (>= 50 znaków).
      - Gdy brak transkryptu po wyczerpaniu OAuth Captions, DB Cache, Local Runner (90s)
        oraz Cloud Fetch, rzuca ValueError (HTTP 422, 0 pobranych kredytów).
    """
    from core.fetcher import (
        process_video as fetch_video,
        fetch_metadata_api_v3,
        fetch_transcript_api_v3,
        fetch_video_thumbnails,
        detect_transcript_language,
    )
    from core.generator import process_video as generate_schema

    resolved_target_lang = (target_lang or lang or "pl").lower()[:2]
    video_id = _extract_video_id(video_url)
    is_audio = video_url.startswith("audio://") or video_url.startswith("audio_")
    logger.info("[generate] video_id=%s is_audio=%s provider=%s type=%s portal_id=%s target_lang=%s",
                video_id, is_audio, llm_provider, publication_type, portal_id, resolved_target_lang)

    # K4: Create new row per click with status='processing' if job_id not pre-provided
    uid = None
    if user_id:
        try:
            uid = uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            pass

    if not job_id:
        async with AsyncSessionLocal() as db_job:
            new_job = TranscriptJob(
                video_url=video_url,
                status="processing",
                publication_type=publication_type,
                portal_id=portal_id,
                user_id=uid,
            )
            db_job.add(new_job)
            await db_job.commit()
            await db_job.refresh(new_job)
            job_id = str(new_job.id)
            logger.info(
                "[generate] K4 created processing job %s for %s (type=%s, user_id=%s)",
                job_id, video_url, publication_type, uid,
            )
    else:
        logger.info("[generate] Using pre-existing job_id %s", job_id)

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

    if not internal_links and site_url:
        wp_internal = await _fetch_wp_internal_links(site_url, video_id)
        if wp_internal:
            internal_links = wp_internal
            logger.info(
                "[generate] D8 internal links fallback: %d links from WP API",
                len(internal_links),
            )

    try:
        if is_audio:
            # Audio path: faster-whisper on VPS
            meta = {
                "id": video_id,
                "title": post_title_override or f"Audio {video_id}",
                "webpage_url": video_url,
                "duration": 0,
                "source": "audio",
                "media_id": video_id,
            }
            image_data: list[dict] = []
            vtt_path: Optional[str] = None
            for p in [f"/tmp/{video_id}.vtt", f"/home/ubuntu/video-seo-engine/data/vtt/{video_id}.vtt"]:
                if os.path.exists(p):
                    vtt_path = p
                    break

            if not vtt_path:
                cached_tr = await _get_cached_transcript_from_db(video_id, user_id=user_id)
                if cached_tr:
                    vtt_path = f"/tmp/{video_id}.vtt"
                    with open(vtt_path, "w", encoding="utf-8") as f:
                        f.write(cached_tr)

            real_chars = _count_real_transcript_chars(vtt_path)
            if not vtt_path or real_chars < 50:
                raise ValueError(
                    "Brak transkryptu wideo: nie udało się pobrać napisów z pliku audio. "
                    "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów)."
                )
            has_transcript = True

            source_lang = "pl"
            if vtt_path and os.path.exists(vtt_path):
                try:
                    with open(vtt_path, "r", encoding="utf-8", errors="replace") as vf:
                        source_lang = detect_transcript_language(vf.read(16000))
                except Exception:
                    source_lang = "pl"
            meta["source_lang"] = source_lang

            post_title = post_title_override or meta.get("title", video_id)
            yt_url = video_url
            wp_id_placeholder = 0

            seo = await asyncio.to_thread(
                generate_schema,
                video_id,
                wp_id_placeholder,
                post_title,
                yt_url,
                vtt_path,
                api_key,
                None,
                0,
                llm_provider,
                priority_keywords if priority_keywords else None,
                internal_links if internal_links else None,
                site_brand,
                publication_type,
                meta,
                resolved_target_lang,
                source_lang,
            )

            seo["source"] = "audio"
            seo["media_id"] = video_id
            seo["thumbnail_url"] = None
            seo["image_data"] = image_data

            # --- PressAI YT Description ---
            vtt_content = ""
            if vtt_path and os.path.exists(vtt_path):
                with open(vtt_path, "r", encoding="utf-8") as f:
                    vtt_content = f.read()

            pressai_yt = (
                await fetch_yt_description_from_pressai(
                    vtt_content=vtt_content,
                    video_title=seo.get("post_title", ""),
                    video_id=video_id,
                    chapters=seo.get("chapters", []),
                    focus_keyphrases=seo.get("focus_keyphrases", []),
                    wp_url="",
                    portal_name=site_brand or "",
                    portal_topic="",
                )
                if resolved_target_lang == "pl"
                else None
            )

            if pressai_yt:
                seo["youtube_description_body"] = pressai_yt.get("youtube_description_body", "")
                seo["youtube_mid_cta"] = pressai_yt.get("youtube_mid_cta", "")
                seo["youtube_credits"] = pressai_yt.get("youtube_credits", {})
                if pressai_yt.get("youtube_hashtags"):
                    seo["youtube_hashtags"] = pressai_yt["youtube_hashtags"]
                logger.info("[pipeline] PressAI YT fields merged into schema_data (audio)")
            else:
                logger.info("[pipeline] Using fallback: youtube_description_hook from generator (audio)")

        else:
            # Standard YouTube flow (with Phase 5.1 OAuth Captions Priority 0 + Multi-Channel Matching)
            yt_api_key = os.environ.get("YOUTUBE_API_KEY", "")
            channel_tokens = await _get_user_yt_access_tokens(user_id)
            initial_access_token = channel_tokens[0][1] if channel_tokens else None

            with tempfile.TemporaryDirectory() as tmp_dir:
                vtt_path = None
                has_transcript = True

                # Step 1: Fetch metadata first so we know video's channel_id (snippet.channelId)
                meta = await asyncio.to_thread(
                    fetch_metadata_api_v3, video_id, yt_api_key, initial_access_token
                )
                if (not meta or meta.get("error")) and len(channel_tokens) > 1:
                    for ch_id, tok in channel_tokens[1:]:
                        meta = await asyncio.to_thread(fetch_metadata_api_v3, video_id, yt_api_key, tok)
                        if meta and not meta.get("error"):
                            break

                if not meta or meta.get("error"):
                    raise RuntimeError(f"Fetch metadata failed for {video_id}: {(meta or {}).get('error', 'unknown')}")

                video_channel_id = meta.get("channel_id") or ""
                if video_channel_id and channel_tokens:
                    # Re-order user's OAuth tokens so the channel owning this video is tried FIRST!
                    channel_tokens.sort(key=lambda item: 0 if item[0] == video_channel_id else 1)

                matched_access_token = channel_tokens[0][1] if channel_tokens else None

                import pathlib
                oauth_vtt = None
                oauth_lang = None

                # Priority 0: Try OAuth Captions across user's authorized channels (owner channel first!)
                if channel_tokens:
                    for ch_id, tok in channel_tokens:
                        logger.info(
                            "[generate] Priority 0 YT OAuth Captions: trying channel %s (video_channel=%s) for %s...",
                            ch_id, video_channel_id or "?", video_id,
                        )
                        oauth_vtt, oauth_lang = await asyncio.to_thread(
                            fetch_transcript_api_v3, video_id, resolved_target_lang, yt_api_key, tok
                        )
                        if oauth_vtt and len(oauth_vtt.strip()) >= 50:
                            matched_access_token = tok
                            logger.info(
                                "[generate] Priority 0 YT OAuth Captions succeeded via channel %s (%d chars)!",
                                ch_id, len(oauth_vtt),
                            )
                            break

                if oauth_vtt and len(oauth_vtt.strip()) >= 50:
                    vtt_path = str(pathlib.Path(tmp_dir) / f"{video_id}.{oauth_lang or resolved_target_lang}.vtt")
                    pathlib.Path(vtt_path).write_text(oauth_vtt, encoding="utf-8")
                    meta["vtt_path"] = vtt_path
                    meta["vtt_language"] = oauth_lang or resolved_target_lang
                    meta["source_lang"] = detect_transcript_language(
                        oauth_vtt,
                        metadata_lang=meta.get("default_audio_language"),
                        track_lang=oauth_lang,
                    )
                else:
                    # Priority 1: Check DB Cache in transcript_jobs before delegating to Local Runner
                    cached_transcript = await _get_cached_transcript_from_db(video_id, user_id=user_id)
                    if cached_transcript:
                        vtt_path = str(pathlib.Path(tmp_dir) / f"{video_id}.vtt")
                        if cached_transcript.startswith("__VTT__"):
                            webvtt_content = _vtt_runner_to_webvtt(cached_transcript)
                            pathlib.Path(vtt_path).write_text(webvtt_content, encoding="utf-8")
                            meta["source_lang"] = detect_transcript_language(
                                webvtt_content,
                                metadata_lang=meta.get("default_audio_language"),
                            )
                        else:
                            pathlib.Path(vtt_path).write_text(cached_transcript, encoding="utf-8")
                            meta["source_lang"] = detect_transcript_language(
                                cached_transcript,
                                metadata_lang=meta.get("default_audio_language"),
                            )
                        meta["vtt_path"] = vtt_path

                    elif local_runner_mode:
                        logger.info(
                            "[generate] LOCAL_RUNNER_MODE=true — delegating transcript to Local Runner (timeout=%ds)",
                            LOCAL_RUNNER_POLL_TIMEOUT,
                        )
                        try:
                            transcript_text = await _fetch_transcript_local_runner(
                                f"https://www.youtube.com/watch?v={video_id}",
                                user_id=user_id,
                                existing_job_id=job_id,
                            )

                            vtt_path = str(pathlib.Path(tmp_dir) / f"{video_id}.vtt")

                            if transcript_text.startswith("__VTT__"):
                                logger.info(
                                    "[generate] __VTT__ format detected — converting to WebVTT for generator"
                                )
                                webvtt_content = _vtt_runner_to_webvtt(transcript_text)
                                pathlib.Path(vtt_path).write_text(webvtt_content, encoding="utf-8")
                                meta["source_lang"] = detect_transcript_language(
                                    webvtt_content,
                                    metadata_lang=meta.get("default_audio_language"),
                                )
                            else:
                                logger.warning(
                                    "[generate] Plain text transcript (no timestamps) — "
                                    "chapters will have approximate times. Upgrade runner to v2.0."
                                )
                                pathlib.Path(vtt_path).write_text(transcript_text, encoding="utf-8")
                                meta["source_lang"] = detect_transcript_language(
                                    transcript_text,
                                    metadata_lang=meta.get("default_audio_language"),
                                )

                            meta["vtt_path"] = vtt_path

                        except RuntimeError as e:
                            exc_str = str(e)
                            logger.info(
                                "[generate] Local Runner unavailable/failed (%s) — trying Cloud Fetch fallback on VPS for %s",
                                exc_str, video_id,
                            )
                            cloud_meta = await asyncio.to_thread(
                                fetch_video, video_url, tmp_dir, resolved_target_lang, yt_api_key, matched_access_token
                            )
                            if cloud_meta and not cloud_meta.get("error"):
                                meta = cloud_meta
                                vtt_path = meta.get("vtt_path")
                            else:
                                vtt_path = None
                    else:
                        cloud_meta = await asyncio.to_thread(
                            fetch_video, video_url, tmp_dir, resolved_target_lang, yt_api_key, matched_access_token
                        )
                        if not cloud_meta or cloud_meta.get("error"):
                            raise RuntimeError(f"Fetch failed for {video_id}: {(cloud_meta or {}).get('error', 'unknown')}")
                        meta = cloud_meta
                        vtt_path = meta.get("vtt_path")

                # ============================================================
                # KROK B.C: TWARDA BLOKADA ANTY-KONFABULACYJNA
                # ============================================================
                real_transcript_chars = _count_real_transcript_chars(vtt_path)
                if not vtt_path or real_transcript_chars < 50:
                    logger.error(
                        "[generate] HARD STOP (Anti-Confabulation): vtt_path=%r real_chars=%d for %s — aborting LLM generation!",
                        vtt_path, real_transcript_chars, video_id,
                    )
                    raise ValueError(
                        "Brak transkryptu wideo: nie udało się pobrać napisów z YouTube "
                        "(sprawdź czy działa VSE Local Runner na komputerze lub czy film posiada napisy na YouTube). "
                        "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów)."
                    )

                source_lang = meta.get("source_lang") or detect_transcript_language(
                    meta.get("description") or meta.get("title") or "",
                    metadata_lang=meta.get("default_audio_language"),
                    track_lang=meta.get("vtt_language"),
                )
                meta["source_lang"] = source_lang

                num_screenshots = 2 if publication_type in ("full_analysis", "discover") else 1
                thumbnails = await asyncio.to_thread(
                    fetch_video_thumbnails, video_id, tmp_dir, num_screenshots
                )
                logger.info(
                    "[generate] D11 thumbnails: %d downloaded for %s (wanted %d)",
                    len(thumbnails), video_id, num_screenshots,
                )

                image_data = []
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

                post_title = post_title_override or meta.get("title", video_id)
                yt_url = meta.get("webpage_url", f"https://www.youtube.com/watch?v={video_id}")
                wp_id_placeholder = 0

                seo = await asyncio.to_thread(
                    generate_schema,
                    video_id,
                    wp_id_placeholder,
                    post_title,
                    yt_url,
                    vtt_path,
                    api_key,
                    None,
                    0,
                    llm_provider,
                    priority_keywords if priority_keywords else None,
                    internal_links if internal_links else None,
                    site_brand,
                    publication_type,
                    meta,
                    resolved_target_lang,
                    source_lang,
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

                # --- PressAI YT Description ---
                vtt_content = ""
                if vtt_path and os.path.exists(vtt_path):
                    with open(vtt_path, "r", encoding="utf-8") as f:
                        vtt_content = f.read()

                pressai_yt = (
                    await fetch_yt_description_from_pressai(
                        vtt_content=vtt_content,
                        video_title=seo.get("post_title", ""),
                        video_id=video_id,
                        chapters=seo.get("chapters", []),
                        focus_keyphrases=seo.get("focus_keyphrases", []),
                        wp_url="",
                        portal_name=site_brand or "",
                        portal_topic="",
                    )
                    if resolved_target_lang == "pl"
                    else None
                )

                if pressai_yt:
                    seo["youtube_description_body"] = pressai_yt.get("youtube_description_body", "")
                    seo["youtube_mid_cta"] = pressai_yt.get("youtube_mid_cta", "")
                    seo["youtube_credits"] = pressai_yt.get("youtube_credits", {})
                    if pressai_yt.get("youtube_hashtags"):
                        seo["youtube_hashtags"] = pressai_yt["youtube_hashtags"]
                    logger.info("[pipeline] PressAI YT fields merged into schema_data")
                else:
                    logger.info("[pipeline] Using fallback: youtube_description_hook from generator")

        partial_result = False
        logger.info(
            "[generate] done: video_id=%s keyphrases=%r saas=%s gsc_status=%s type=%s "
            "portal_id=%s images=%d has_transcript=%s partial=%s lang=%s->%s",
            video_id, seo.get("focus_keyphrases", seo.get("focus_keyphrase", "?")),
            "enriched" if seo.get("saas_enriched") else "standalone",
            gsc_meta["status"], publication_type, portal_id, len(image_data),
            has_transcript, partial_result, seo.get("source_lang"), seo.get("target_lang"),
        )
        if job_id and vtt_path and os.path.exists(vtt_path):
            try:
                with open(vtt_path, "r", encoding="utf-8", errors="replace") as vf:
                    vtt_text = vf.read()
                if vtt_text.strip():
                    async with AsyncSessionLocal() as db_tr:
                        j_tr = await db_tr.get(TranscriptJob, uuid.UUID(str(job_id)))
                        if j_tr and not j_tr.transcript:
                            j_tr.transcript = vtt_text
                            await db_tr.commit()
            except Exception as tr_err:
                logger.warning("[generate] Could not persist transcript to job %s: %s", job_id, tr_err)

        if meta and meta.get("channel_id"):
            seo["channel_id"] = meta["channel_id"]

        return {
            "job_id": str(job_id),
            "video_id": video_id,
            "meta": meta,
            "seo": seo,
            "gsc": gsc_meta,
            "saas_data": saas_data,
            "has_transcript": True,
            "partial_result": False,
            "source_lang": seo.get("source_lang") or meta.get("source_lang", "pl"),
            "target_lang": seo.get("target_lang", resolved_target_lang),
            "input_tokens": seo.get("input_tokens", 0),
            "output_tokens": seo.get("output_tokens", 0),
            "estimated_cost_usd": seo.get("estimated_cost_usd", 0.0),
            "llm_provider": seo.get("llm_provider", llm_provider),
        }

    except Exception as exc:
        if job_id:
            try:
                async with AsyncSessionLocal() as db_fail:
                    failed_job = await db_fail.get(TranscriptJob, uuid.UUID(str(job_id)))
                    if failed_job and failed_job.status == "processing":
                        failed_job.status = "failed"
                        failed_job.error = str(exc)
                        failed_job.updated_at = datetime.now(timezone.utc)
                        await db_fail.commit()
            except Exception as update_err:
                logger.warning("[generate] Could not update failed job %s status: %s", job_id, update_err)
        raise


async def run_process(video_url: str, site_config: dict, options: dict,
                      wp_post_id: Optional[int] = None,
                      user_id: Optional[str] = None) -> dict:
    """Full pipeline: fetch → generate → inject."""
    from core.injector import inject_video

    start = time.time()
    llm_provider = options.get("llm_provider", "claude")
    lang = options.get("lang", "pl")
    target_lang = options.get("target_lang") or lang or "pl"
    publication_type = options.get("publication_type", "full_analysis")

    gen_result = await run_generate(
        video_url, llm_provider, lang,
        publication_type=publication_type,
        user_id=user_id,
        target_lang=target_lang,
    )
    video_id = gen_result["video_id"]
    seo = gen_result["seo"]
    meta = gen_result["meta"]
    saas_data = gen_result.get("saas_data")

    final_wp_id = wp_post_id
    injected = False
    youtube_updated = False

    if options.get("auto_inject", True):
        if final_wp_id is None:
            logger.info("[process] No wp_post_id provided — creating new WP post via _create_wp_post")
            create_res = await asyncio.to_thread(
                _create_wp_post,
                seo,
                video_id,
                site_config["wp_base_url"],
                site_config["wp_user"],
                site_config["wp_app_password"],
                None,
                "draft",
                "video",
                saas_data,
            )
            final_wp_id = create_res.get("wp_post_id")
            injected = create_res.get("status") == "ok"
            youtube_updated = create_res.get("youtube_updated", False)
        else:
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
        logger.info("[process] inject done: ok=%s yt_updated=%s wp_id=%s", injected, youtube_updated, final_wp_id)

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
        "source_lang": gen_result.get("source_lang", "pl"),
        "target_lang": gen_result.get("target_lang", target_lang),
        "input_tokens": gen_result.get("input_tokens", 0),
        "output_tokens": gen_result.get("output_tokens", 0),
        "estimated_cost_usd": gen_result.get("estimated_cost_usd", 0.0),
        "llm_provider": gen_result.get("llm_provider", llm_provider),
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

    # Determine default categories
    categories = None
    if profile_config and profile_config.get("default_categories"):
        categories = profile_config.get("default_categories")
    elif seo.get("categories"):
        categories = seo.get("categories")
    elif "prawy.pl" in wp_base_url:
        categories = [2, 2472]  # Polska (2) + Prawy TV (2472)

    create_payload: dict = {
        "title": post_title,
        "status": post_status,
        "content": "",
        "format": post_format,
    }
    if categories:
        create_payload["categories"] = categories

    # excerpt removed — lead is displayed in post_content only (fix lead-excerpt 2026-07-23)

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
    portal_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Inject pre-generated schema into a WP post, or create a new post."""
    from core.injector import inject_video

    video_id = _extract_video_id(video_url)

    # Resolving Profile Config and schema from portal_id or job_id (K4: never from 'last job')
    wp_base_url = site_config["wp_base_url"]
    wp_user = site_config["wp_user"]
    wp_app_password = site_config["wp_app_password"]
    profile_config = None

    resolved_portal_id = portal_id
    if job_id:
        try:
            j_uuid = uuid.UUID(str(job_id))
            async with AsyncSessionLocal() as db:
                job = await db.get(TranscriptJob, j_uuid)
                if job:
                    if (not schema_data or not isinstance(schema_data, dict)) and job.schema_data:
                        schema_data = job.schema_data
                    if not resolved_portal_id and job.portal_id:
                        resolved_portal_id = job.portal_id
        except (ValueError, TypeError) as exc:
            logger.warning("[inject] Invalid job_id %s: %s", job_id, exc)

    if resolved_portal_id:
        try:
            uid = uuid.UUID(str(resolved_portal_id))
            async with AsyncSessionLocal() as db:
                portal = await db.get(WpPortal, uid)
                if portal and portal.profile_id:
                    profile_config = _load_profile_config(portal.profile_id)
        except (ValueError, TypeError) as exc:
            logger.warning("[inject] Invalid portal_id %s: %s", resolved_portal_id, exc)

    # FIX: Scenariusz A obsługuje YT — wyłącz legacy
    if yt_channel_ids and profile_config:
        if profile_config.get("yt_update_enabled"):
            logger.info("[inject] yt_channel_ids present -> disabling legacy yt_update_enabled")
            profile_config["yt_update_enabled"] = False

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
