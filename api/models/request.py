"""VSE API — Pydantic input models.

All per-request credentials are passed inline (stateless multi-tenant design).
No session state, no database — each request is fully self-contained.
"""
from typing import Optional
from pydantic import BaseModel


class SiteConfig(BaseModel):
    """WordPress site credentials and endpoint for one tenant."""

    wp_base_url: str
    wp_user: str
    wp_app_password: str


class ProcessOptions(BaseModel):
    """Processing behaviour flags per request."""

    auto_inject: bool = True
    update_youtube: bool = False
    llm_provider: str = "claude"  # "claude" | "gemini"
    lang: str = "pl"


class ProcessRequest(BaseModel):
    """Full pipeline: fetch → generate schema → inject to WP."""

    video_url: str
    site_config: SiteConfig
    options: ProcessOptions = ProcessOptions()
    wp_post_id: Optional[int] = None  # if known; matcher used when None


class GenerateRequest(BaseModel):
    """Generate SEO schema for a video (no WP write)."""

    video_url: str
    llm_provider: str = "claude"
    lang: str = "pl"
    post_title: Optional[str] = None  # override title from metadata


class InjectRequest(BaseModel):
    """Inject pre-generated schema JSON into a WordPress post.

    CO: Model wejściowy dla endpointu POST /v1/inject.

    PO CO: Pozwala klientowi wstrzyknąć wygenerowane wcześniej dane SEO
    do WordPressa bez uruchamiania całego pipeline. W modelu freemium
    używany przez plan pro/agency w sekcji 'Opublikuj' dashboardu.

    JAK:
    - Gdy wp_post_id podane → aktualizuje istniejący post (PATCH/POST do /posts/{id}).
    - Gdy wp_post_id = None → WordPress tworzy nowy post (POST do /posts bez ID).
      Nowy post zawiera pełną treść + SEO schema, domyślnie jako draft.
    """

    wp_post_id: Optional[int] = None  # None = utwórz nowy post; int = aktualizuj istniejący
    video_url: str
    schema_data: dict
    site_config: SiteConfig
    post_status: str = "draft"  # "draft" | "publish" — dla nowych postów
    post_format: str = "video"  # WordPress post format: "standard" | "video" | "gallery" | "quote"


class MonitorStartRequest(BaseModel):
    """Start background YouTube channel monitor."""

    channel_id: str
    site_config: SiteConfig
    check_interval_min: int = 60


class SitemapRequest(BaseModel):
    """Generate video sitemap XML for a tenant site."""

    site_config: SiteConfig
    output_path: Optional[str] = None
