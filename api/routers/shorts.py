"""
ShortMachine API Router — endpointy dla propozycji i renderowania shortów.

CO: REST API dla ShortMachine.
PO CO: Frontend (Next.js) i Local Runner komunikują się przez te endpointy.
JAK: 7 endpointów: kandydaci, historia, render, pending (dla Local Runner), result, status, title.
"""
import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.job import TranscriptJob
from api.models.short_job import ShortJob
from api.models.short_candidate import ShortCandidateSet
from api.models.short_srt import ShortSrtPackage
from core.shorts import propose_shorts, get_vtt_segments_for_candidate, get_segments_for_range

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/shorts", tags=["shorts"])


# --- Pydantic Models ---

class CandidatesRequest(BaseModel):
    youtube_url: Optional[str] = None
    vtt_path: Optional[str] = None       # ścieżka do VTT na VPS
    youtube_id: Optional[str] = None
    custom_query: str = ""
    count_emotional: int = 2
    count_professional: int = 2
    count_custom: int = 3
    provider: Optional[str] = None
    portal_id: Optional[str] = None


class RenderRequest(BaseModel):
    youtube_url: Optional[str] = None
    local_path: Optional[str] = None     # ścieżka na PC użytkownika
    youtube_id: Optional[str] = None
    start_sec: float
    end_sec: float
    candidate_data: Optional[dict] = None
    render_format: str = "9:16"          # '9:16' | '16:9' | 'both'
    subtitles: str = "none"             # 'none' | 'srt' | 'karaoke'
    output_dir: str = r"C:\VSE\Shorts"
    portal_id: Optional[str] = None


class ResultRequest(BaseModel):
    status: str                          # 'done' | 'error'
    result_paths: Optional[dict] = None  # {raw, social, srt}
    error: Optional[str] = None


class TitleRequest(BaseModel):
    youtube_id: str
    start_sec: float
    end_sec: float


# --- Helpers ---

def _extract_youtube_id(url_or_id: Optional[str]) -> Optional[str]:
    """Wyciąga 11-znakowy identyfikator wideo YouTube z URL lub stringu."""
    if not url_or_id:
        return None
    cleaned = url_or_id.strip()
    if re.match(r'^[a-zA-Z0-9_-]{11}$', cleaned):
        return cleaned
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, cleaned)
        if m:
            return m.group(1)
    return None


def _convert_transcript_to_webvtt(transcript: str) -> str:
    """Konwertuje transkrypt z bazy danych (format __VTT__ / [MM:SS] / plain text) do standardowego WebVTT."""
    transcript = transcript.strip()
    if transcript.startswith("WEBVTT"):
        return transcript

    if transcript.startswith("__VTT__"):
        transcript = transcript[len("__VTT__"):].lstrip("\n")

    lines = transcript.split("\n")
    segments = []
    ts_pattern = re.compile(r'^(?:\[)?(?:(\d{1,2}):)?(\\d{2}):(\\d{2})(?:\.\d+)?(?:\])?\s*(.*)$')

    for line in lines:
        line_s = line.strip()
        if not line_s or line_s == "__VTT__":
            continue
        m = ts_pattern.match(line_s)
        if m:
            h_str, m_str, s_str, text = m.groups()
            hours = int(h_str) if h_str else 0
            mins = int(m_str)
            secs = int(s_str)
            start_sec = hours * 3600 + mins * 60 + secs
            clean_text = text.strip()
            if clean_text:
                segments.append((start_sec, clean_text))
        else:
            if segments:
                last_time, last_text = segments[-1]
                segments[-1] = (last_time, f"{last_text} {line_s}")
            else:
                segments.append((0, line_s))

    if not segments:
        return f"WEBVTT\n\n1\n00:00:00.000 --> 00:01:00.000\n{transcript}\n"

    webvtt_parts = ["WEBVTT", ""]
    for i, (start_sec, text) in enumerate(segments):
        if i + 1 < len(segments):
            end_sec = max(segments[i + 1][0], start_sec + 1)
        else:
            end_sec = start_sec + 5

        start_h, start_m, start_s = start_sec // 3600, (start_sec % 3600) // 60, start_sec % 60
        end_h, end_m, end_s = end_sec // 3600, (end_sec % 3600) // 60, end_sec % 60

        start_fmt = f"{start_h:02d}:{start_m:02d}:{start_s:02d}.000"
        end_fmt = f"{end_h:02d}:{end_m:02d}:{end_s:02d}.000"

        webvtt_parts.append(str(i + 1))
        webvtt_parts.append(f"{start_fmt} --> {end_fmt}")
        webvtt_parts.append(text)
        webvtt_parts.append("")

    return "\n".join(webvtt_parts)


async def _resolve_vtt_path(youtube_id: str, db: AsyncSession) -> Optional[str]:
    """
    CO: Znajduje plik VTT dla danego youtube_id.
    PO CO: Współdzielona logika szukania VTT — używana przez /candidates i /title.
    JAK: Sprawdza dysk VPS, potem bazę danych TranscriptJob.
    
    Returns:
        Ścieżka do pliku VTT (może być plikiem tymczasowym) lub None.
        Jeśli zwrócił plik tymczasowy, caller musi go usuńąć po użyciu.
    """
    # 1. Sprawdz dysk VPS
    candidates_paths = [
        f"/home/ubuntu/video-seo-engine/data/vtt/{youtube_id}.vtt",
        f"/tmp/{youtube_id}.vtt",
    ]
    for p in candidates_paths:
        if os.path.exists(p):
            return p

    # 2. Pobierz z bazy danych
    query = (
        select(TranscriptJob)
        .where(TranscriptJob.transcript.isnot(None))
        .where(TranscriptJob.video_url.contains(youtube_id))
        .order_by(desc(TranscriptJob.created_at))
        .limit(1)
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job and job.transcript:
        webvtt_content = _convert_transcript_to_webvtt(job.transcript)
        tmp_fd, tmp_file = tempfile.mkstemp(suffix=".vtt", prefix=f"vse_{youtube_id}_title_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(webvtt_content)
        logger.info("_resolve_vtt_path: VTT from DB job %s -> %s", job.id, tmp_file)
        return tmp_file

    return None


# --- SRT Generators ---

def _seconds_to_srt_time(seconds: float) -> str:
    """Konwertuje sekundy do formatu SRT: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _generate_pelny_film_srt(vtt_path: str) -> str:
    """
    CO: Generuje pełny plik SRT z transkryptu VTT.
    PO CO: YouTube Closed Captions dla pełnego wideo.
    """
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        entries = []
        i = 0
        
        # Skip WEBVTT header
        while i < len(lines) and not '-->' in lines[i]:
            i += 1
        
        counter = 1
        while i < len(lines):
            line = lines[i].strip()
            if '-->' in line:
                # Parse timestamp line: 00:00:05.000 --> 00:00:10.000
                parts = line.split(' --> ')
                if len(parts) == 2:
                    start_vtt = parts[0].strip().replace('.', ',')
                    end_vtt = parts[1].strip().split(' ')[0].replace('.', ',')
                    # Collect text lines
                    text_lines = []
                    i += 1
                    while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                        text_line = lines[i].strip()
                        # Remove VTT tags like <c.colorE5E5E5> </c>
                        import re as _re
                        text_line = _re.sub(r'<[^>]+>', '', text_line)
                        if text_line:
                            text_lines.append(text_line)
                        i += 1
                    if text_lines:
                        entries.append(f"{counter}\n{start_vtt} --> {end_vtt}\n" + '\n'.join(text_lines))
                        counter += 1
                    continue
            i += 1
        
        return '\n\n'.join(entries) + '\n'
    except Exception as e:
        logger.error("_generate_pelny_film_srt error: %s", e)
        return ""


def _generate_napisy_shortow_srt(candidates: list) -> str:
    """
    CO: Generuje SRT tylko z napisami w obszarach shortow.
    PO CO: Import do Premiere/DaVinci — montazysta widzi tekst tylko w obszarach do cięcia.
    """
    entries = []
    counter = 1
    
    for c in candidates:
        start_sec = c.get('start_sec', 0)
        end_sec = c.get('end_sec', start_sec + 60)
        title = c.get('suggested_title') or c.get('title') or f"Short {counter}"
        hook = c.get('hook_text', '')
        punchline = c.get('punchline_text', '')
        
        # Header entry for this short
        entries.append(
            f"{counter}\n"
            f"{_seconds_to_srt_time(start_sec)} --> {_seconds_to_srt_time(start_sec + 2)}\n"
            f"[SHORT: {title}]"
        )
        counter += 1
        
        # VTT segments within this range
        vtt_segs = c.get('vtt_segments', [])
        for seg in vtt_segs:
            ts = seg.get('ts', 0)
            if start_sec <= ts <= end_sec:
                seg_text = seg.get('text', '').strip()
                if seg_text:
                    seg_end = min(ts + 4, end_sec)
                    entries.append(
                        f"{counter}\n"
                        f"{_seconds_to_srt_time(ts)} --> {_seconds_to_srt_time(seg_end)}\n"
                        f"{seg_text}"
                    )
                    counter += 1
    
    return '\n\n'.join(entries) + '\n' if entries else ""


def _generate_shorts_markers_srt(candidates: list) -> str:
    """
    CO: Generuje SRT z dużymi blokami czasowymi dla każdego shorta.
    PO CO: Import do Premiere = wizualne markery cięć na osi czasu.
            Montazysta przeciaga plik na ścieżkę Captions, widzi bloki, tnie żyletką.
    """
    entries = []
    
    for i, c in enumerate(candidates, 1):
        start_sec = c.get('start_sec', 0)
        end_sec = c.get('end_sec', start_sec + 60)
        title = c.get('suggested_title') or c.get('title') or f"Short {i}"
        short_type = c.get('type', 'short').upper()
        score = c.get('score', 0)
        stars = '\u2605' * round(score * 5) + '\u2606' * (5 - round(score * 5))
        
        entries.append(
            f"{i}\n"
            f"{_seconds_to_srt_time(start_sec)} --> {_seconds_to_srt_time(end_sec)}\n"
            f"[SHORT {i}: {title}]\n"
            f"{short_type} | {stars} | {int(end_sec - start_sec)}s"
        )
    
    return '\n\n'.join(entries) + '\n' if entries else ""


# --- Endpoints ---

@router.get("/candidates/{youtube_id}")
async def get_saved_candidates(youtube_id: str, portal_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Pobiera ostatnio zapisanych kandydatów dla youtube_id z DB."""
    # Sanitize: extract 11-char ID from full URL if needed [szortownia-4]
    yt_id = _extract_youtube_id(youtube_id) or youtube_id
    conditions = [ShortCandidateSet.youtube_id == yt_id]
    if portal_id:
        conditions.append(ShortCandidateSet.portal_id == portal_id)
    
    query = select(ShortCandidateSet).where(*conditions).order_by(desc(ShortCandidateSet.created_at)).limit(1)
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        return {"candidates": [], "total": 0, "from_cache": False}
    return {
        "candidates": record.candidates,
        "total": len(record.candidates),
        "from_cache": True,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "custom_query": record.custom_query,
    }

@router.post("/candidates/{youtube_id}/save")
async def save_candidates(youtube_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Zapisuje kandydatów do DB (wywoływane przez frontend po analizie)."""
    record = ShortCandidateSet(
        youtube_id=youtube_id,
        youtube_url=body.get("youtube_url"),
        portal_id=body.get("portal_id"),
        custom_query=body.get("custom_query"),
        candidates=body.get("candidates", []),
    )
    db.add(record)
    await db.commit()
    return {"id": str(record.id), "saved": len(record.candidates)}

@router.post("/candidates")
async def get_candidates(req: CandidatesRequest, db: AsyncSession = Depends(get_db)):
    """Analizuje transkrypt VTT i zwraca propozycje kandydatów na shorty."""
    provider = req.provider or os.getenv("DEFAULT_LLM_PROVIDER", "claude")
    api_key = os.getenv("ANTHROPIC_API_KEY", "") if provider == "claude" else os.getenv("GEMINI_API_KEY", "")

    # Fallback jeśli wybrany provider nie ma klucza w środowisku
    if not api_key:
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "claude"
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        elif os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY", "")

    yt_id = _extract_youtube_id(req.youtube_id) or _extract_youtube_id(req.youtube_url) or req.youtube_id
    vtt_path = req.vtt_path
    tmp_file = None

    # 1. Sprawdz plik na dysku jeśli podano youtube_id / youtube_url
    if not vtt_path and yt_id:
        candidates_paths = [
            f"/home/ubuntu/video-seo-engine/data/vtt/{yt_id}.vtt",
            f"/tmp/{yt_id}.vtt",
        ]
        for p in candidates_paths:
            if os.path.exists(p):
                vtt_path = p
                break

    # 2. Jeśli brak pliku na dysku — pobierz transkrypt z bazy PostgreSQL
    if not vtt_path or not os.path.exists(vtt_path):
        conditions = [TranscriptJob.transcript.isnot(None)]
        if yt_id:
            conditions.append(TranscriptJob.video_url.contains(yt_id))
        elif req.youtube_url:
            conditions.append(TranscriptJob.video_url == req.youtube_url)

        query = (
            select(TranscriptJob)
            .where(*conditions)
            .order_by(desc(TranscriptJob.created_at))
            .limit(1)
        )
        result = await db.execute(query)
        job = result.scalar_one_or_none()

        if job and job.transcript:
            webvtt_content = _convert_transcript_to_webvtt(job.transcript)
            tmp_fd, tmp_file = tempfile.mkstemp(suffix=".vtt", prefix=f"vse_{yt_id or 'shorts'}_")
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(webvtt_content)
            vtt_path = tmp_file
            logger.info("candidates: VTT extracted from DB job %s -> %s", job.id, tmp_file)

    if not vtt_path or not os.path.exists(vtt_path):
        raise HTTPException(
            status_code=404,
            detail=f"VTT not found for youtube_id={yt_id or req.youtube_id or req.youtube_url or 'unknown'}. Generate SEO first to fetch transcript."
        )

    try:
        candidates = propose_shorts(
            vtt_path=vtt_path,
            count_emotional=req.count_emotional,
            count_professional=req.count_professional,
            custom_query=req.custom_query,
            count_custom=req.count_custom,
            api_key=api_key,
            provider=provider,
        )
        result_candidates = []
        for c in candidates:
            c_dict = c.to_dict()
            # Dodaj segmenty VTT dla tego kandydata (+/-60s kontekstu)
            c_dict["vtt_segments"] = get_vtt_segments_for_candidate(
                vtt_path=vtt_path,
                start_sec=c.start_sec,
                end_sec=c.end_sec,
                context_sec=60.0,
            )
            result_candidates.append(c_dict)

        if yt_id and result_candidates:
            try:
                record = ShortCandidateSet(
                    youtube_id=yt_id,
                    youtube_url=req.youtube_url,
                    custom_query=req.custom_query,
                    candidates=result_candidates,
                    portal_id=req.portal_id
                )
                db.add(record)
                await db.commit()
                logger.info("Saved %d candidates for youtube_id=%s", len(result_candidates), yt_id)
            except Exception as e:
                logger.warning("Could not save candidates to DB: %s", e)

        return {
            "candidates": result_candidates,
            "total": len(result_candidates),
        }
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error("candidates: unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception as e:
                logger.warning("Failed to remove temp VTT file %s: %s", tmp_file, e)


@router.post("/title")
async def regenerate_title(req: TitleRequest, db: AsyncSession = Depends(get_db)):
    """
    CO: Regeneruje tytuł i tagi dla shorta na podstawie nowych czasów.
    PO CO: Gdy user zmienia start/end sekund, tytuł powinien odzwierciedlać nowy zakres.
    JAK: Wyciąga segmenty VTT z pliku/DB, buduje krótki prompt, zwraca title+tags.
    """
    import json
    from core.generator import _call_llm

    yt_id = _extract_youtube_id(req.youtube_id) or req.youtube_id
    tmp_file = None

    try:
        vtt_path = await _resolve_vtt_path(yt_id, db)
        if not vtt_path:
            raise HTTPException(status_code=404, detail=f"VTT not found for youtube_id={yt_id}. Generate SEO first.")

        # Jeśli _resolve_vtt_path stworzył plik tymczasowy, zapamiętaj go do usunięcia
        if vtt_path.startswith("/tmp/") and "_title_" in vtt_path:
            tmp_file = vtt_path

        segments = get_segments_for_range(vtt_path, req.start_sec, req.end_sec, context_sec=3.0)
        if not segments:
            raise HTTPException(status_code=404, detail="No segments found for given range")

        vtt_text = "\n".join([
            f"[{s['time_str']}] {s['text']}" for s in segments if s['in_range']
        ])
        if not vtt_text.strip():
            # Fallback: użyj wszystkich segmentów z kontekstem
            vtt_text = "\n".join([f"[{s['time_str']}] {s['text']}" for s in segments])

        prompt = f"""Na podstawie tego fragmentu transkryptu wygeneruj:
1. suggested_title: chwytliwy tytuł shorta (5-9 słów po polsku)
2. tags: do 10 hashtagów (format #słowo)

Transkrypt:
{vtt_text}

Odpowiedź TYLKO JSON: {{"suggested_title": "...", "tags": ["#tag1", "#tag2"]}}"""

        provider = os.getenv("DEFAULT_LLM_PROVIDER", "claude")
        api_key = os.getenv("ANTHROPIC_API_KEY", "") if provider == "claude" else os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            if os.getenv("ANTHROPIC_API_KEY"):
                provider, api_key = "claude", os.getenv("ANTHROPIC_API_KEY", "")
            elif os.getenv("GEMINI_API_KEY"):
                provider, api_key = "gemini", os.getenv("GEMINI_API_KEY", "")

        raw = _call_llm(prompt, api_key, provider)
        raw = raw.strip().lstrip("```json").rstrip("```").strip()
        try:
            data = json.loads(raw)
            return {"title": data.get("suggested_title", ""), "tags": data.get("tags", [])}
        except Exception:
            logger.warning("regenerate_title: JSON parse failed, raw=%s", raw[:200])
            return {"title": "", "tags": []}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("regenerate_title: unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception as cleanup_err:
                logger.warning("Failed to remove temp VTT file %s: %s", tmp_file, cleanup_err)


@router.post("/render")
async def render_short(req: RenderRequest, db: AsyncSession = Depends(get_db)):
    """Zleca wycięcie i renderowanie wybranego kandydata."""
    if not req.youtube_url and not req.local_path:
        raise HTTPException(status_code=400, detail="Wymagany youtube_url lub local_path")

    yt_id = _extract_youtube_id(req.youtube_id) or _extract_youtube_id(req.youtube_url) or req.youtube_id

    job = ShortJob(
        status="pending",
        youtube_url=req.youtube_url,
        local_path=req.local_path,
        youtube_id=yt_id,
        start_sec=req.start_sec,
        end_sec=req.end_sec,
        candidate_data=req.candidate_data,
        render_config={
            "format": req.render_format,
            "subtitles": req.subtitles,
            "output_dir": req.output_dir,
        },
        portal_id=req.portal_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info("ShortJob created: %s (%.1f-%.1fs)", job.id, req.start_sec, req.end_sec)
    return {"job_id": str(job.id), "status": "pending"}


@router.get("/pending")
async def get_pending_shorts(db: AsyncSession = Depends(get_db)):
    """Zwraca oczekujące zadania dla Local Runner — endpoint pollingu."""
    query = select(ShortJob).where(ShortJob.status == "pending").limit(5)
    result_jobs = await db.execute(query)
    jobs = result_jobs.scalars().all()

    result = []
    for job in jobs:
        job.status = "processing"
        result.append({
            "id": str(job.id),
            "youtube_url": job.youtube_url,
            "local_path": job.local_path,
            "start_sec": job.start_sec,
            "end_sec": job.end_sec,
            "render_config": job.render_config,
            "candidate_data": job.candidate_data,
        })
    await db.commit()
    return {"jobs": result}


@router.post("/{job_id}/result")
async def submit_short_result(job_id: UUID, req: ResultRequest, db: AsyncSession = Depends(get_db)):
    """Local Runner raportuje wynik renderowania."""
    query = select(ShortJob).where(ShortJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = req.status
    job.result_paths = req.result_paths
    job.error_message = req.error
    job.completed_at = datetime.utcnow()
    await db.commit()
    logger.info("ShortJob %s: %s paths=%s", job_id, req.status, req.result_paths)
    return {"ok": True}


@router.get("/history/{youtube_id}")
async def get_shorts_history(youtube_id: str, portal_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Pobiera historię szortów (kandydaci + joby renderowania) dla danego wideo.
    
    CO: Endpoint odtwarzania stanu ShortMachine po odświeżeniu strony (F5).
    PO CO: smJobStatus żyje wyłącznie w RAM przeglądarki — po F5 znika.
           Ten endpoint pozwala frontendowi odtworzyć stan z bazy danych.
    JAK: Zwraca ostatni ShortCandidateSet + ostatnie 20 ShortJob dla youtube_id.
         Frontend dopasowuje joby do kandydatów po start_sec/end_sec.
    
    UWAGA: Zadeklarowany przed /{job_id} żeby FastAPI nie próbował parsować
           "history" jako UUID.
    """
    yt_id = _extract_youtube_id(youtube_id) or youtube_id

    # 1. Pobierz ostatni ShortCandidateSet dla tego wideo
    cand_conditions = [ShortCandidateSet.youtube_id == yt_id]
    if portal_id:
        cand_conditions.append(ShortCandidateSet.portal_id == portal_id)

    cand_query = (
        select(ShortCandidateSet)
        .where(*cand_conditions)
        .order_by(desc(ShortCandidateSet.created_at))
        .limit(1)
    )
    cand_res = await db.execute(cand_query)
    cand_set = cand_res.scalar_one_or_none()

    # 2. Pobierz ostatnie 20 jobów renderowania dla tego wideo
    jobs_query = (
        select(ShortJob)
        .where(ShortJob.youtube_id == yt_id)
        .order_by(desc(ShortJob.created_at))
        .limit(20)
    )
    jobs_res = await db.execute(jobs_query)
    jobs = jobs_res.scalars().all()

    return {
        "youtube_id": yt_id,
        "candidates": cand_set.candidates if cand_set else [],
        "candidates_created_at": cand_set.created_at.isoformat() if cand_set else None,
        "jobs": [
            {
                "id": str(j.id),
                "status": j.status,
                "start_sec": j.start_sec,
                "end_sec": j.end_sec,
                "result_paths": j.result_paths,
                "error": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@router.post("/generate-srt/{youtube_id}")
async def generate_srt_package(youtube_id: str, portal_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    CO: Generuje pakiet 3 plików SRT dla danego wideo YouTube.
    PO CO: SRT-Only Shorts workflow — montazysci pobieraja SRT i tna ręcznie w Premiere.
    JAK:
        1. Pobiera kandydatów z short_candidate_sets
        2. Pobiera VTT z dysku/DB
        3. Generuje 3 pliki SRT
        4. Zapisuje do short_srt_packages
        5. Zwraca JSON z treścią plików
    """
    yt_id = _extract_youtube_id(youtube_id) or youtube_id
    
    # 1. Pobierz kandydatów
    cand_conditions = [ShortCandidateSet.youtube_id == yt_id]
    if portal_id:
        cand_conditions.append(ShortCandidateSet.portal_id == portal_id)
    
    cand_query = select(ShortCandidateSet).where(*cand_conditions).order_by(desc(ShortCandidateSet.created_at)).limit(1)
    cand_res = await db.execute(cand_query)
    cand_set = cand_res.scalar_one_or_none()
    
    candidates = cand_set.candidates if cand_set else []
    
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"Brak kandydatów dla youtube_id={yt_id}. Najpierw wygeneruj kandydatów przez /v1/shorts/candidates."
        )
    
    # 2. Pobierz VTT
    tmp_file = None
    vtt_path = await _resolve_vtt_path(yt_id, db)
    if vtt_path and vtt_path.startswith("/tmp/") and "_title_" in vtt_path:
        tmp_file = vtt_path
    
    try:
        # 3. Generuj SRT
        pelny_film = _generate_pelny_film_srt(vtt_path) if vtt_path else ""
        napisy_shortow = _generate_napisy_shortow_srt(candidates)
        shorts_markers = _generate_shorts_markers_srt(candidates)
        
        # 4. Zapisz do bazy
        srt_package = ShortSrtPackage(
            youtube_id=yt_id,
            portal_id=portal_id,
            candidate_count=len(candidates),
            pelny_film_srt=pelny_film,
            napisy_shortow_srt=napisy_shortow,
            shorts_markers_srt=shorts_markers,
        )
        db.add(srt_package)
        await db.commit()
        await db.refresh(srt_package)
        
        logger.info("SRT package generated for youtube_id=%s, id=%s", yt_id, srt_package.id)
        
        # 5. Zwroc pakiet
        return {
            "id": str(srt_package.id),
            "youtube_id": yt_id,
            "candidate_count": len(candidates),
            "files": {
                "pelny_film": {
                    "filename": f"{yt_id}_pelny_film.srt",
                    "content": pelny_film,
                    "size_bytes": len(pelny_film.encode('utf-8')),
                },
                "napisy_shortow": {
                    "filename": f"{yt_id}_napisy_shortow.srt",
                    "content": napisy_shortow,
                    "size_bytes": len(napisy_shortow.encode('utf-8')),
                },
                "shorts_markers": {
                    "filename": f"{yt_id}_shorts_markers.srt",
                    "content": shorts_markers,
                    "size_bytes": len(shorts_markers.encode('utf-8')),
                },
            },
            "created_at": srt_package.created_at.isoformat(),
        }
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass


@router.get("/srt/{youtube_id}")
async def get_srt_package(youtube_id: str, portal_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    CO: Pobiera ostatnio wygenerowany pakiet SRT dla youtube_id.
    PO CO: Frontend może sprawdzić czy SRT już istnieje przed regeneracją.
    """
    yt_id = _extract_youtube_id(youtube_id) or youtube_id
    
    conditions = [ShortSrtPackage.youtube_id == yt_id]
    if portal_id:
        conditions.append(ShortSrtPackage.portal_id == portal_id)
    
    query = select(ShortSrtPackage).where(*conditions).order_by(desc(ShortSrtPackage.created_at)).limit(1)
    result = await db.execute(query)
    pkg = result.scalar_one_or_none()
    
    if not pkg:
        return {"exists": False, "youtube_id": yt_id}
    
    return {
        "exists": True,
        "id": str(pkg.id),
        "youtube_id": yt_id,
        "candidate_count": pkg.candidate_count,
        "created_at": pkg.created_at.isoformat(),
        "files": {
            "pelny_film": {
                "filename": f"{yt_id}_pelny_film.srt",
                "content": pkg.pelny_film_srt or "",
                "size_bytes": len((pkg.pelny_film_srt or "").encode('utf-8')),
            },
            "napisy_shortow": {
                "filename": f"{yt_id}_napisy_shortow.srt",
                "content": pkg.napisy_shortow_srt or "",
                "size_bytes": len((pkg.napisy_shortow_srt or "").encode('utf-8')),
            },
            "shorts_markers": {
                "filename": f"{yt_id}_shorts_markers.srt",
                "content": pkg.shorts_markers_srt or "",
                "size_bytes": len((pkg.shorts_markers_srt or "").encode('utf-8')),
            },
        },
    }


@router.get("/{job_id}")
async def get_short_status(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Sprawdza status zadania i zwraca ścieżki do plików."""
    query = select(ShortJob).where(ShortJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": str(job.id),
        "status": job.status,
        "result_paths": job.result_paths,
        "error": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
