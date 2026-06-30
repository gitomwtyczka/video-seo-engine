"""Router: /v1/profiles — list and create server-side YAML profiles.

CO: Endpointy do listowania i tworzenia profili portali z katalogu profiles/.

PO CO: Dashboard potrzebuje listy profili do dropdown selektora portalu.
       Użytkownik wybiera profil (np. Prawy.pl, Kurier365) PRZED generowaniem
       artykułu, co determinuje konfigurację SEO i domyślny typ publikacji.
       Inline profile creation pozwala tworzyć nowe profile z poziomu UI
       bez ręcznej edycji plików YAML na serwerze.

JAK:
  GET  /v1/profiles — skanuje profiles/*.yaml, parsuje YAML, filtruje active=true,
       zwraca id + display_name + publication_types + default_type.
       NIE zawiera credentials (bezpieczeństwo).
  POST /v1/profiles — tworzy nowy plik YAML z szablonu, waliduje typy publikacji.

D9  (2026-06-20, vse-dev-23): New endpoint for dashboard portal selector
D35 (2026-06-30, vse-dev-01): POST /v1/profiles — inline profile creation
"""
import glob
import logging
import os
import re
from typing import List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/v1", tags=["profiles"])
logger = logging.getLogger(__name__)

# Publication types available for selection in the dashboard
AVAILABLE_PUBLICATION_TYPES = ["full_analysis", "watching_page", "discover"]

# Display names for publication types (used in frontend)
PUBLICATION_TYPE_LABELS = {
    "watching_page": "Film",
    "discover": "Discover",
    "full_analysis": "Full Analysis",
}


class ProfileInfo(BaseModel):
    """Public profile metadata — no credentials."""
    id: str
    display_name: str
    active: bool
    publication_types: List[str]
    default_type: str
    site_brand: Optional[str] = None


class ProfileListResponse(BaseModel):
    """List of active profiles."""
    profiles: List[ProfileInfo]
    total: int


class CreateProfileRequest(BaseModel):
    """Request body for POST /v1/profiles.

    CO: Dane potrzebne do wygenerowania nowego pliku YAML profilu.
    PO CO: User tworzy profil z poziomu AddPortalModal — bez SSH na serwer.
    JAK: Walidacja portal_id regex + default_type enum, potem generacja YAML.
    """
    portal_id: str
    display_name: str
    site_brand: str
    wp_base_url: str
    default_type: str = "full_analysis"
    seo_language: str = "pl"
    seo_external_link_url: Optional[str] = None
    seo_external_link_anchor: Optional[str] = None

    @field_validator("portal_id")
    @classmethod
    def validate_portal_id(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9][a-z0-9_-]{1,48}[a-z0-9]$", v):
            raise ValueError(
                "portal_id musi mieć 3-50 znaków: małe litery, cyfry, - lub _"
            )
        return v

    @field_validator("default_type")
    @classmethod
    def validate_default_type(cls, v: str) -> str:
        if v not in AVAILABLE_PUBLICATION_TYPES:
            raise ValueError(
                f"default_type musi być jednym z: {', '.join(AVAILABLE_PUBLICATION_TYPES)}"
            )
        return v

    @field_validator("seo_language")
    @classmethod
    def validate_seo_language(cls, v: str) -> str:
        allowed = {"pl", "en", "de", "fr", "es"}
        if v not in allowed:
            raise ValueError(f"seo_language musi być jednym z: {', '.join(sorted(allowed))}")
        return v


def _load_profiles() -> List[ProfileInfo]:
    """Load all active profiles from profiles/*.yaml.

    CO: Parsuje pliki YAML profili z katalogu profiles/.
    PO CO: Centralne źródło danych o dostępnych portalach.
    JAK: glob profiles/*.yaml → yaml.safe_load → filtruj active=True.
    """
    profiles_dir = os.path.join(os.getcwd(), "profiles")
    if not os.path.isdir(profiles_dir):
        logger.warning("[profiles] profiles/ directory not found at %s", profiles_dir)
        return []

    result: List[ProfileInfo] = []
    for filepath in sorted(glob.glob(os.path.join(profiles_dir, "*.yaml"))):
        filename = os.path.basename(filepath)
        # Skip template files
        if filename.startswith("template"):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue

            # Only include active profiles
            if not data.get("active", False):
                continue

            # Extract default publication type from source_channels
            default_type = "full_analysis"
            source_channels = data.get("source_channels", [])
            if source_channels and isinstance(source_channels, list):
                first_channel = source_channels[0]
                if isinstance(first_channel, dict):
                    default_type = first_channel.get("default_type", "full_analysis")

            profile = ProfileInfo(
                id=data.get("portal_id", filename.replace(".yaml", "")),
                display_name=data.get("display_name", filename.replace(".yaml", "")),
                active=True,
                publication_types=AVAILABLE_PUBLICATION_TYPES,
                default_type=default_type,
                site_brand=data.get("site_brand"),
            )
            result.append(profile)
            logger.debug("[profiles] Loaded profile: %s (%s)", profile.id, profile.display_name)

        except Exception as exc:
            logger.error("[profiles] Failed to parse %s: %s", filepath, exc)
            continue

    logger.info("[profiles] Loaded %d active profiles", len(result))
    return result


def _generate_profile_yaml(req: CreateProfileRequest) -> str:
    """Generate YAML content for a new profile from request data.

    CO: Buduje dict profilu i serializuje do YAML.
    PO CO: Unikamy ręcznej manipulacji stringami — yaml.safe_dump gwarantuje
           poprawny format.
    JAK: Tworzy strukturę zgodną z template.yaml, zamienia placeholdery.
    """
    profile_data = {
        "portal_id": req.portal_id,
        "display_name": req.display_name,
        "site_brand": req.site_brand,
        "active": True,
        # WordPress — env vars, uzupełniane później
        "wp_base_url": req.wp_base_url,
        "wp_user": f"${{WP_USER_{req.portal_id.upper()}}}",
        "wp_app_password": f"${{WP_APP_PASS_{req.portal_id.upper()}}}",
        # Source channels — puste na start, dodawane później
        "source_channels": [],
        # Gemini AI
        "gemini_api_key": "${GEMINI_API_KEY}",
        "gemini_model": "gemini-2.5-flash",
        # SEO customization
        "seo": {
            "language": req.seo_language,
            "chapter_js_class": f"{req.portal_id}-chapter",
            "seek_fn_name": f"{req.portal_id}Seek",
        },
        # SEO external link
        "seo_external_link": {
            "url": req.seo_external_link_url or "https://www.youtube.com",
            "anchor": req.seo_external_link_anchor or "Źródło wideo",
        },
        # Publish delay
        "publish_delay": {
            "min": 5,
            "max": 37,
        },
        # Paths
        "paths": {
            "subs_dir": f"data/{req.portal_id}/subs",
            "seo_dir": f"data/{req.portal_id}/seo_results",
            "registry_dir": f"data/{req.portal_id}/registry",
            "cookies_file": f"cookies/{req.portal_id}_cookies.txt",
        },
        # Monitor
        "monitor": {
            "interval_seconds": 1800,
            "lookback_days": 14,
            "dry_run": False,
        },
    }

    header = (
        f"# profiles/{req.portal_id}.yaml\n"
        f"# Portal: {req.display_name} — created via VSE Dashboard API\n"
        f"# Default publication type: {req.default_type}\n"
        f"#\n"
        f"# UWAGA: Sekrety (hasła, klucze API) NIE są tu wpisywane bezpośrednio.\n"
        f"# Używaj ${{NAZWA_ZMIENNEJ}} — wartości ładowane z .env lub środowiska.\n\n"
    )

    yaml_content = yaml.safe_dump(
        profile_data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    return header + yaml_content


@router.get("/profiles", response_model=ProfileListResponse)
async def list_profiles() -> ProfileListResponse:
    """List active server-side profiles for dashboard portal selector.

    CO: Zwraca listę aktywnych profili portali.
    PO CO: Frontend wyświetla dropdown z profilami do wyboru przed generowaniem.
    JAK: Wywołuje _load_profiles() → profiles/*.yaml → filtrowane po active=True.
    """
    profiles = _load_profiles()
    return ProfileListResponse(
        profiles=profiles,
        total=len(profiles),
    )


@router.post("/profiles", response_model=ProfileInfo, status_code=201)
async def create_profile(req: CreateProfileRequest) -> ProfileInfo:
    """Create a new YAML profile for a portal.

    CO: Tworzy nowy plik YAML profilu w katalogu profiles/.
    PO CO: User może utworzyć profil z poziomu AddPortalModal bez SSH na serwer.
    JAK: Waliduje dane → generuje YAML z szablonu → zapisuje plik → zwraca ProfileInfo.
    """
    profiles_dir = os.path.join(os.getcwd(), "profiles")

    # Ensure profiles directory exists
    os.makedirs(profiles_dir, exist_ok=True)

    # Check if profile already exists
    target_path = os.path.join(profiles_dir, f"{req.portal_id}.yaml")
    if os.path.exists(target_path):
        raise HTTPException(
            status_code=409,
            detail=f"Profil '{req.portal_id}' już istnieje",
        )

    # Generate and write YAML
    try:
        yaml_content = _generate_profile_yaml(req)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        logger.info(
            "[profiles] Created new profile: %s (%s) at %s",
            req.portal_id, req.display_name, target_path,
        )
    except Exception as exc:
        logger.error("[profiles] Failed to create profile %s: %s", req.portal_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Nie udało się utworzyć profilu: {exc}",
        )

    return ProfileInfo(
        id=req.portal_id,
        display_name=req.display_name,
        active=True,
        publication_types=AVAILABLE_PUBLICATION_TYPES,
        default_type=req.default_type,
        site_brand=req.site_brand,
    )
