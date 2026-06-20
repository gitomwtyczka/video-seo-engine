"""Router: GET /v1/profiles — list active server-side YAML profiles.

CO: Endpoint listujący aktywne profile portali z katalogu profiles/.

PO CO: Dashboard potrzebuje listy profili do dropdown selektora portalu.
       Użytkownik wybiera profil (np. Prawy.pl, Kurier365) PRZED generowaniem
       artykułu, co determinuje konfigurację SEO i domyślny typ publikacji.

JAK: Skanuje profiles/*.yaml, parsuje YAML, filtruje active=true,
     zwraca id + display_name + publication_types + default_type.
     NIE zawiera credentials (bezpieczeństwo).
     Endpoint jest publiczny (lista profili nie jest wrażliwa).

D9 (2026-06-20, vse-dev-23):
  - New endpoint for dashboard portal selector
"""
import glob
import logging
import os
from typing import List, Optional

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1", tags=["profiles"])
logger = logging.getLogger(__name__)

# Publication types available for selection in the dashboard
AVAILABLE_PUBLICATION_TYPES = ["full_analysis", "watching_page", "discover"]


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
