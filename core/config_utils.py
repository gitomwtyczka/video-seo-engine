"""Shared configuration utilities — env var resolution + YAML loading.

CO: Wspólne narzędzia do ładowania i parsowania konfiguracji YAML z ${ENV_VAR}.

PO CO: Zarówno profile.py (witryny) jak i channel.py (kanały YT) potrzebują
       rozwiązywania ${ENV_VAR} placeholderów i parsowania YAML. Wydzielenie
       do wspólnego modułu eliminuje duplikację kodu.

JAK: Dwie funkcje — resolve_env_vars() (rekurencyjne rozwiązywanie placeholderów)
     i load_yaml_file() (ładowanie YAML z fallback parsingiem).

Utworzono: 2026-06-20 | vse-dev-21 | D6b.3
"""
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in strings/dicts/lists.

    Args:
        value: A string, dict, list, or any other type to resolve.

    Returns:
        The same structure with all ${VAR} placeholders replaced by
        their environment variable values. Missing vars resolve to "".
    """
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            var_name = m.group(1)
            val = os.environ.get(var_name)
            if val is None:
                logger.warning("Config references unset env var: %s", var_name)
                return ""
            return val
        return re.sub(r"\$\{([^}]+)\}", _replace, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    return value


def load_yaml_file(path: Path) -> dict:
    """Load a YAML file and return raw dict (no env var resolution).

    Falls back to a simple key: value parser if PyYAML is not installed.

    Args:
        path: Path to the YAML file.

    Returns:
        Raw dict from YAML parsing.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If parsed content is not a dict.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        import yaml  # type: ignore
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except ImportError:
        raw = _parse_simple_yaml(path)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw)}: {path}")

    return raw


def _parse_simple_yaml(path: Path) -> dict:
    """Minimal YAML parser for flat key: value files (no yaml package required).

    Only handles top-level string values. For nested config, install PyYAML.
    """
    result: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()
    return result
