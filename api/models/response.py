"""VSE API — Pydantic output models.

All response models include a `status` field ("ok" | "error").
"""
from typing import Optional, List
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    llm_default: str


class ProcessResponse(BaseModel):
    """Response from the full pipeline endpoint."""

    status: str  # "ok" | "error"
    video_id: str
    wp_post_id: Optional[int] = None
    schema_generated: bool = False
    injected: bool = False
    youtube_updated: bool = False
    processing_time_s: float = 0.0
    focus_keyphrase: Optional[str] = None
    post_title: Optional[str] = None
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    """Response from the generate-only endpoint.

    FIX D (2026-07-10, vse-dev-01):
      - error_code: machine-readable error code for frontend handling.
        Values: 'NO_TRANSCRIPT', 'VIDEO_UNAVAILABLE', 'UNKNOWN_ERROR', None.

    FIX A (2026-07-10, vse-dev-01):
      - transcript_available: True when transcript was used for generation.
      - partial_result: True when schema generated without transcript (degraded mode).
    """

    status: str
    video_id: str
    processing_time_s: float = 0.0
    schema_data: Optional[dict] = None
    error: Optional[str] = None
    error_code: Optional[str] = None  # FIX D: 'NO_TRANSCRIPT' | 'VIDEO_UNAVAILABLE' | 'UNKNOWN_ERROR' | None
    transcript_available: Optional[bool] = None  # FIX A: True = with transcript, False = partial
    partial_result: Optional[bool] = None  # FIX A: True = generated without transcript


class InjectResponse(BaseModel):
    """Response from the inject-only endpoint.

    CO: Model odpowiedzi dla POST /v1/inject.

    PO CO: Informuje klienta o wyniku operacji wstrzykiwania SEO.
    wp_post_id jest Optional — gdy tworzono nowy post, zwraca ID nadane przez WP;
    gdy aktualizowano istniejący, zwraca to samo ID co w requeście.
    created: True gdy WP utworzył nowy post (wp_post_id był None w requeście).
    """

    status: str
    wp_post_id: Optional[int] = None  # None tylko przy błędzie tworzenia posta
    video_id: str
    rankmath_ok: bool = False
    youtube_updated: bool = False
    created: bool = False  # True = nowy post został utworzony; False = aktualizacja
    post_url: Optional[str] = None  # URL nowego/zaktualizowanego posta (gdy dostępny)
    yt_channels: List[dict] = []
    error: Optional[str] = None


class MonitorResponse(BaseModel):
    """Response from monitor start."""

    status: str
    channel_id: str
    check_interval_min: int
    message: str


class SitemapResponse(BaseModel):
    """Response from sitemap generation."""

    status: str
    videos_count: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None


class AsyncJobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
