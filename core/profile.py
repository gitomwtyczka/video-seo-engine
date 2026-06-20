"""Portal Profile Loader — multi-tenant configuration system.

Loads per-portal YAML profiles that define:
  - WordPress credentials and URL
  - Source channel mappings (source_channels → channels/*.yaml)
  - SEO customization (JS class names, etc.)
  - Publish delay settings
  - Per-portal data paths (subs, seo_results, registry)

Profile files live in: profiles/<portal_id>.yaml
Channel files live in: channels/<channel_id>.yaml
Secrets are referenced as ${ENV_VAR_NAME} placeholders and resolved
from environment variables at load time.

D6b refactor (2026-06-20, vse-dev-21):
  - Channel data (yt_oauth, channel_ids, yt_api_key) moved to channels/*.yaml
  - Profiles now use source_channels mapping to reference channels
  - _resolve_env_vars moved to core.config_utils (shared with channel.py)
  - Backward compat: profiles with inline yt_oauth still work (deprecation warning)

Usage:
    from core.profile import load_profile, list_profiles
    profile = load_profile("prawy")
    wp_url = profile["wp_base_url"]
"""
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from core.config_utils import resolve_env_vars, load_yaml_file

logger = logging.getLogger(__name__)

# Default profile directory (relative to project root / CWD)
PROFILES_DIR = Path("profiles")


# ============================================================
# BACKWARD COMPAT — keep _resolve_env_vars as a re-export
# ============================================================

_resolve_env_vars = resolve_env_vars  # Legacy callers that import from profile


# ============================================================
# PROFILE LOADING
# ============================================================

def load_profile(name: str, profiles_dir: Optional[Path] = None) -> dict:
    """Load a portal profile from YAML and resolve env var placeholders.

    Profiles are stored as: profiles/<name>.yaml

    Args:
        name: Profile name, e.g. 'prawy', 'kurier365'.
        profiles_dir: Optional override for the profiles directory.

    Returns:
        Dict with all profile settings, env vars resolved.

    Raises:
        FileNotFoundError: If the profile YAML does not exist.
        ValueError: If required fields are missing.
    """
    pdir = profiles_dir or PROFILES_DIR
    profile_path = pdir / f"{name}.yaml"

    if not profile_path.exists():
        raise FileNotFoundError(
            f"Profile '{name}' not found at {profile_path}. "
            f"Available: {list_profiles(pdir)}"
        )

    raw = load_yaml_file(profile_path)
    profile = resolve_env_vars(raw)
    _apply_defaults(profile)
    validate_profile(profile)

    logger.info("Loaded profile: %s (%s)", name, profile.get("wp_base_url", "?"))
    return profile


def _apply_defaults(profile: dict) -> None:
    """Apply default values to optional profile fields in-place.

    Args:
        profile: Loaded profile dict to modify.
    """
    profile.setdefault("seo", {})
    profile["seo"].setdefault("language", "pl")
    profile["seo"].setdefault("chapter_js_class", "vse-chapter")
    profile["seo"].setdefault("seek_fn_name", "vseSeek")

    profile.setdefault("publish_delay", {})
    profile["publish_delay"].setdefault("min", 5)
    profile["publish_delay"].setdefault("max", 37)

    portal_id = profile.get("portal_id", "default")
    profile.setdefault("paths", {})
    profile["paths"].setdefault("subs_dir", f"data/{portal_id}/subs")
    profile["paths"].setdefault("seo_dir", f"data/{portal_id}/seo_results")
    profile["paths"].setdefault("registry_dir", f"data/{portal_id}/registry")

    # Ensure data dirs exist
    for key in ("subs_dir", "seo_dir", "registry_dir"):
        Path(profile["paths"][key]).mkdir(parents=True, exist_ok=True)

    # D6b: default source_channels to empty list
    profile.setdefault("source_channels", [])


def validate_profile(profile: dict) -> None:
    """Validate that required structural fields are present.

    Only checks that portal_id key exists in the profile dict
    (value may be empty string if env var not yet set — that's OK at load time,
    and will fail at runtime when the actual API call is made).

    Args:
        profile: Profile dict to validate.

    Raises:
        ValueError: If a required structural field is completely missing.
    """
    required = ["portal_id"]
    for field in required:
        if field not in profile:
            raise ValueError(f"Profile missing required field: '{field}'")


# ============================================================
# PROFILE DISCOVERY
# ============================================================

def list_profiles(profiles_dir: Optional[Path] = None) -> list:
    """Return a list of available profile names (without .yaml extension).

    Args:
        profiles_dir: Optional override for the profiles directory.

    Returns:
        Sorted list of profile name strings.
    """
    pdir = profiles_dir or PROFILES_DIR
    if not pdir.exists():
        return []
    return sorted(p.stem for p in pdir.glob("*.yaml"))


# ============================================================
# ENV-BASED FALLBACK PROFILE (backward compat)
# ============================================================

def profile_from_env() -> dict:
    """Build a profile dict from environment variables (single-tenant fallback).

    This preserves backward compatibility with the original .env-only approach.
    Used when no --profile flag is specified and no profiles/ directory exists.

    Returns:
        Profile dict populated from environment variables.
    """
    profile = {
        "portal_id": os.environ.get("PORTAL", "prawy"),
        "display_name": os.environ.get("PORTAL", "prawy").capitalize(),
        "wp_base_url": os.environ.get("WP_BASE_URL", ""),
        "wp_user": os.environ.get("WP_USER", ""),
        "wp_app_password": os.environ.get("WP_APP_PASSWORD", ""),
        # D6b: channel data now in channels/*.yaml, but env fallback
        # builds a pseudo source_channels for backward compat
        "source_channels": [],
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "seo": {
            "language": "pl",
            "chapter_js_class": "prawy-chapter",
            "seek_fn_name": "prawySeek",
        },
        "publish_delay": {
            "min": int(os.environ.get("PUBLISH_DELAY_MIN", "5")),
            "max": int(os.environ.get("PUBLISH_DELAY_MAX", "37")),
        },
        "paths": {
            "subs_dir": os.environ.get("SUBS_DIR", "subs"),
            "seo_dir": os.environ.get("SEO_DIR", "seo_results"),
            "registry_dir": "registry",
        },
    }
    # Backward compat: if env has YT OAuth vars, include inline yt_oauth
    # so get_channel_for_profile() can build a pseudo-channel
    yt_client_id = os.environ.get("YT_CLIENT_ID", "")
    if yt_client_id:
        profile["yt_oauth"] = {
            "client_id": yt_client_id,
            "client_secret": os.environ.get("YT_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("YT_REFRESH_TOKEN", ""),
        }
        profile["yt_api_key"] = os.environ.get("YT_API_KEY", "")
        profile["channel_ids"] = [os.environ.get("CHANNEL_ID", "")]
        profile["yt_update_enabled"] = True

    logger.debug("Built profile from env vars (portal=%s)", profile["portal_id"])
    return profile


def resolve_profile(name: Optional[str] = None) -> dict:
    """Smart profile resolver: YAML if available, else env fallback.

    Args:
        name: Profile name to load. If None, uses PORTAL env var or 'prawy'.

    Returns:
        Profile dict, always valid.
    """
    if name is None:
        name = os.environ.get("PORTAL", "prawy")

    yaml_path = PROFILES_DIR / f"{name}.yaml"
    if yaml_path.exists():
        return load_profile(name)

    logger.info("No profiles/%s.yaml found — falling back to env vars", name)
    return profile_from_env()
