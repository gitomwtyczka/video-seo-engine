"""YouTube Channel Loader — load channel configs from channels/*.yaml.

CO: Ładuje konfigurację kanałów YouTube z plików YAML w katalogu channels/.

PO CO: Model 1:N — jeden kanał YT może być źródłem dla wielu witryn.
       Dane kanału (OAuth, hashtags, footer, kategoria) żyją oddzielnie
       od danych witryny (WordPress credentials, SEO customization).
       Profile witryn referencują kanały przez source_channels.

JAK: load_channel("prawy-tv") → parsuje channels/prawy-tv.yaml,
     rozwiązuje ${ENV_VAR} placeholdery, waliduje wymagane pola.
     get_channel_for_profile() → szuka kanału dla danego profilu witryny.

Utworzono: 2026-06-20 | vse-dev-21 | D6b.3
"""
import logging
from pathlib import Path
from typing import Optional

from core.config_utils import load_yaml_file, resolve_env_vars

logger = logging.getLogger(__name__)

# Default channel directory (relative to project root / CWD)
CHANNELS_DIR = Path("channels")


def load_channel(
    channel_id: str,
    channels_dir: Optional[Path] = None,
) -> dict:
    """Load a channel config from YAML and resolve env var placeholders.

    Channels are stored as: channels/<channel_id>.yaml

    Args:
        channel_id: Channel identifier, e.g. 'prawy-tv'.
        channels_dir: Optional override for the channels directory.

    Returns:
        Dict with all channel settings, env vars resolved.

    Raises:
        FileNotFoundError: If the channel YAML does not exist.
        ValueError: If required fields are missing.
    """
    cdir = channels_dir or CHANNELS_DIR
    channel_path = cdir / f"{channel_id}.yaml"

    if not channel_path.exists():
        raise FileNotFoundError(
            f"Channel '{channel_id}' not found at {channel_path}. "
            f"Available: {list_channels(cdir)}"
        )

    raw = load_yaml_file(channel_path)
    channel = resolve_env_vars(raw)
    _validate_channel(channel, channel_id)

    logger.info("Loaded channel: %s (%s)", channel_id, channel.get("display_name", "?"))
    return channel


def _validate_channel(channel: dict, channel_id: str) -> None:
    """Validate that required structural fields are present.

    Args:
        channel: Channel dict to validate.
        channel_id: Channel ID for error messages.

    Raises:
        ValueError: If a required field is missing.
    """
    required = ["channel_id"]
    for field in required:
        if field not in channel:
            raise ValueError(
                f"Channel '{channel_id}' missing required field: '{field}'"
            )


def list_channels(channels_dir: Optional[Path] = None) -> list[str]:
    """Return a list of available channel IDs (without .yaml extension).

    Args:
        channels_dir: Optional override for the channels directory.

    Returns:
        Sorted list of channel ID strings.
    """
    cdir = channels_dir or CHANNELS_DIR
    if not cdir.exists():
        return []
    return sorted(p.stem for p in cdir.glob("*.yaml"))


def get_channel_for_profile(
    profile: dict,
    channel_id: Optional[str] = None,
) -> Optional[dict]:
    """Resolve a channel config for a given portal profile.

    CO: Zwraca dict kanału YT powiązanego z profilem witryny.

    PO CO: Pipeline potrzebuje danych kanału (OAuth, footer, hashtags)
           żeby zaktualizować opis na YouTube. Profile referencują kanały
           przez source_channels.

    JAK:
    1. Jeśli podano channel_id — ładuj bezpośrednio
    2. Jeśli profil ma source_channels — użyj pierwszego
    3. Backward compat: jeśli profil ma inline yt_oauth — zbuduj pseudo-channel
    4. Zwróć None jeśli brak kanału

    Args:
        profile: Portal profile dict loaded from YAML.
        channel_id: Optional explicit channel ID to load.

    Returns:
        Channel config dict, or None if no channel is associated.
    """
    # 1. Explicit channel_id
    if channel_id:
        try:
            return load_channel(channel_id)
        except FileNotFoundError:
            logger.warning(
                "Explicit channel '%s' not found — falling back", channel_id
            )

    # 2. source_channels mapping in profile
    source_channels = profile.get("source_channels", [])
    if source_channels:
        first_channel_id = source_channels[0].get("channel", "")
        if first_channel_id:
            try:
                return load_channel(first_channel_id)
            except FileNotFoundError:
                logger.warning(
                    "source_channel '%s' not found for profile '%s'",
                    first_channel_id, profile.get("portal_id", "?"),
                )

    # 3. Backward compat: inline yt_oauth in profile (pre-D6b format)
    yt_oauth = profile.get("yt_oauth", {})
    if yt_oauth and yt_oauth.get("client_id"):
        logger.warning(
            "DEPRECATED: Profile '%s' has inline yt_oauth — migrate to channels/*.yaml",
            profile.get("portal_id", "?"),
        )
        return {
            "channel_id": profile.get("portal_id", "unknown"),
            "display_name": profile.get("display_name", ""),
            "yt_channel_id": (profile.get("channel_ids", [""]))[0] if profile.get("channel_ids") else "",
            "yt_oauth": yt_oauth,
            "yt_api_key": profile.get("yt_api_key", ""),
            "yt_update_enabled": profile.get("yt_update_enabled", False),
            "yt_category_id": "25",
            "yt_hashtags": ["#PrawyTV", "#Polska"],
            "yt_footer": "",  # No footer in legacy format
        }

    # 4. No channel
    return None


def get_default_publication_type(
    profile: dict,
    channel_id: Optional[str] = None,
) -> str:
    """Get the default publication type for a profile+channel combination.

    CO: Zwraca domyślny typ publikacji dla danego profilu i kanału.

    PO CO: Każda witryna może mieć inny domyślny typ artykułu dla danego kanału.
           np. prawy.pl → full_analysis, kurier365 → watching_page.

    JAK: Szuka w source_channels mapowaniu matching channel_id.
         Fallback: 'full_analysis'.

    Args:
        profile: Portal profile dict.
        channel_id: Optional channel ID to match against source_channels.

    Returns:
        Publication type string: 'full_analysis', 'watching_page', or 'discover'.
    """
    source_channels = profile.get("source_channels", [])

    if channel_id:
        for sc in source_channels:
            if sc.get("channel") == channel_id:
                return sc.get("default_type", "full_analysis")

    # Fallback: first source_channel's default_type, or "full_analysis"
    if source_channels:
        return source_channels[0].get("default_type", "full_analysis")

    return "full_analysis"
