"""VSE API — Pydantic output models.

All response models include a `status` field ("ok" | "error").
"""
from typing import Optional
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
    """Response from the generate-only endpoint."""

    status: str
    video_id: str
    processing_time_s: float = 0.0
    schema_data: Optional[dict] = None
    error: Optional[str] = None


class InjectResponse(BaseModel):
    """Response from the inject-only endpoint."""

    status: str
    wp_post_id: int
    video_id: str
    rankmath_ok: bool = False
    youtube_updated: bool = False
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
