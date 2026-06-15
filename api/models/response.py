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
