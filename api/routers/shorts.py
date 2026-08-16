"""
ShortMachine API Router — endpointy dla propozycji i renderowania shortów.

CO: REST API dla ShortMachine.
PO CO: Frontend (Next.js) i Local Runner komunikują się przez te endpointy.
JAK: 5 endpointów: kandydaci, render, pending (dla Local Runner), result, status.
"""
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.short_job import ShortJob
from core.shorts import propose_shorts
from sqlalchemy import select

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
    provider: str = "gemini"


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


# --- Endpoints ---

@router.post("/candidates")
async def get_candidates(req: CandidatesRequest):
    """Analizuje transkrypt VTT i zwraca propozycje kandydatów na shorty."""
    api_key = os.getenv("GEMINI_API_KEY", "") if req.provider == "gemini" else os.getenv("ANTHROPIC_API_KEY", "")
    
    # Znajdź VTT path na podstawie youtube_id
    vtt_path = req.vtt_path
    if not vtt_path and req.youtube_id:
        # Spróbuj typowych lokalizacji VTT na VPS
        candidates_paths = [
            f"/home/ubuntu/video-seo-engine/data/vtt/{req.youtube_id}.vtt",
            f"/tmp/{req.youtube_id}.vtt",
        ]
        for p in candidates_paths:
            if os.path.exists(p):
                vtt_path = p
                break
    
    if not vtt_path or not os.path.exists(vtt_path):
        raise HTTPException(status_code=404, detail=f"VTT file not found for youtube_id={req.youtube_id}")
    
    candidates = propose_shorts(
        vtt_path=vtt_path,
        count_emotional=req.count_emotional,
        count_professional=req.count_professional,
        custom_query=req.custom_query,
        count_custom=req.count_custom,
        api_key=api_key,
        provider=req.provider,
    )
    
    return {
        "candidates": [c.to_dict() for c in candidates],
        "total": len(candidates),
    }


@router.post("/render")
async def render_short(req: RenderRequest, db: Session = Depends(get_db)):
    """Zleca wycięcie i renderowanie wybranego kandydata."""
    if not req.youtube_url and not req.local_path:
        raise HTTPException(status_code=400, detail="Wymagany youtube_url lub local_path")
    
    job = ShortJob(
        status="pending",
        youtube_url=req.youtube_url,
        local_path=req.local_path,
        youtube_id=req.youtube_id,
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
    logger.info("ShortJob created: %s (%.1f–%.1fs)", job.id, req.start_sec, req.end_sec)
    return {"job_id": str(job.id), "status": "pending"}


@router.get("/pending")
async def get_pending_shorts(db: Session = Depends(get_db)):
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
async def submit_short_result(job_id: UUID, req: ResultRequest, db: Session = Depends(get_db)):
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


@router.get("/{job_id}")
async def get_short_status(job_id: UUID, db: Session = Depends(get_db)):
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
