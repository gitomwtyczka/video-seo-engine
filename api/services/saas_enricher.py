"""SAAS SEO Data Enricher — fetches keywords & top pages from PressAI SAAS.

CO: Moduł pobierający dane SEO (frazy kluczowe z GSC, top pages) z SAAS
PressAI (crimson-void) poprzez dedykowany endpoint zewnętrzny.

PO CO: Integracja SAAS↔VSE — generator artykułów SEO dostaje kontekst
z Google Search Console portalu docelowego. Dzięki temu generowane
artykuły zawierają frazy, które portal już rankuje + propozycje
linków wewnętrznych do istniejących artykułów.

JAK:
- Async HTTP GET do SAAS /api/external/seo-data?site_url=<portal_url>
- Auth: Bearer token (SAAS_API_TOKEN z .env)
- Cache w pamięci 30 min (dict + timestamp) — SAAS odpytuje GSC
  z quotą, nie chcemy bombardować
- Fallback: jeśli SAAS niedostępny → puste dane (VSE działa jak dotąd)

Zmienne .env:
  SAAS_API_URL  — bazowy URL SAAS (np. http://localhost:8001)
  SAAS_API_TOKEN — token autoryzacyjny (Bearer)
"""
import asyncio
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# In-memory cache: key = site_url, value = (timestamp, data)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes


def _get_saas_config() -> tuple[Optional[str], Optional[str]]:
    """Read SAAS connection config from environment.

    Returns:
        Tuple of (saas_api_url, saas_api_token). Both None if not configured.
    """
    url = os.environ.get("SAAS_API_URL", "").strip().rstrip("/")
    token = os.environ.get("SAAS_API_TOKEN", "").strip()
    if not url or not token:
        return None, None
    return url, token


def _is_cache_valid(site_url: str) -> bool:
    """Check if cached data for site_url is still fresh."""
    if site_url not in _cache:
        return False
    cached_time, _ = _cache[site_url]
    return (time.time() - cached_time) < CACHE_TTL_SECONDS


def _get_cached(site_url: str) -> Optional[dict]:
    """Return cached SAAS data if valid, else None."""
    if _is_cache_valid(site_url):
        _, data = _cache[site_url]
        logger.debug("[saas_enricher] Cache hit for %s", site_url)
        return data
    return None


def _set_cache(site_url: str, data: dict) -> None:
    """Store SAAS data in cache with current timestamp."""
    _cache[site_url] = (time.time(), data)
    logger.debug("[saas_enricher] Cached data for %s (%d keys)", site_url, len(data))


async def get_saas_seo_data(
    site_url: str,
    saas_api_url: Optional[str] = None,
    saas_api_token: Optional[str] = None,
) -> dict:
    """Fetch SEO enrichment data from SAAS for a given portal.

    CO: Główna funkcja modułu — pobiera frazy kluczowe i top pages z SAAS.

    PO CO: Pipeline wywołuje ją przed generowaniem artykułu. Jeśli SAAS
    zwraca dane, generator dostaje priorytetowe frazy i propozycje linków.
    Jeśli SAAS jest niedostępny — zwraca puste dane (graceful degradation).

    JAK:
    1. Sprawdź cache → jeśli fresh → zwróć bez HTTP
    2. GET /api/external/seo-data?site_url=<url>
    3. Parse response → cache → zwróć
    4. Exception → log + zwróć puste dane

    Args:
        site_url: URL portalu docelowego (np. https://prawy.pl).
        saas_api_url: Override bazowego URL SAAS (domyślnie z .env).
        saas_api_token: Override tokena (domyślnie z .env).

    Returns:
        Dict z kluczami:
          - keywords: list[dict] — frazy z GSC (query, clicks, impressions, position)
          - top_pages: list[dict] — top strony portalu (page, clicks, impressions)
        Puste listy jeśli SAAS niedostępny lub błąd.
    """
    empty_result = {"keywords": [], "top_pages": []}

    # Resolve config
    if not saas_api_url or not saas_api_token:
        env_url, env_token = _get_saas_config()
        saas_api_url = saas_api_url or env_url
        saas_api_token = saas_api_token or env_token

    if not saas_api_url or not saas_api_token:
        logger.debug(
            "[saas_enricher] SAAS_API_URL or SAAS_API_TOKEN not configured — "
            "skipping enrichment (VSE works standalone)"
        )
        return empty_result

    # Check cache first
    cache_key = site_url.rstrip("/").lower()
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Fetch from SAAS
    endpoint = f"{saas_api_url}/api/external/seo-data"
    headers = {
        "Authorization": f"Bearer {saas_api_token}",
        "Accept": "application/json",
    }
    params = {"site_url": site_url}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.info(
                "[saas_enricher] Fetching SEO data from SAAS for %s",
                site_url,
            )
            response = await client.get(endpoint, headers=headers, params=params)

        if response.status_code != 200:
            logger.warning(
                "[saas_enricher] SAAS returned HTTP %d for %s: %s",
                response.status_code, site_url, response.text[:200],
            )
            return empty_result

        data = response.json()

        # Normalize response structure
        result = {
            "keywords": data.get("keywords", []),
            "top_pages": data.get("top_pages", []),
        }

        kw_count = len(result["keywords"])
        tp_count = len(result["top_pages"])
        logger.info(
            "[saas_enricher] SAAS data received: %d keywords, %d top_pages for %s",
            kw_count, tp_count, site_url,
        )

        # Cache the result
        _set_cache(cache_key, result)
        return result

    except httpx.TimeoutException:
        logger.warning(
            "[saas_enricher] SAAS timeout for %s — continuing without enrichment",
            site_url,
        )
        return empty_result
    except httpx.ConnectError:
        logger.warning(
            "[saas_enricher] SAAS connection refused for %s — is SAAS running?",
            site_url,
        )
        return empty_result
    except Exception as exc:
        logger.error(
            "[saas_enricher] Unexpected error fetching SAAS data for %s: %s",
            site_url, exc,
        )
        return empty_result


def extract_priority_keywords(saas_data: dict, max_keywords: int = 15) -> list[str]:
    """Extract top keyword phrases from SAAS data.

    CO: Konwerter — z pełnych danych GSC wyciąga same frazy tekstowe.

    PO CO: Generator LLM potrzebuje prostej listy fraz, nie pełnych obiektów
    z clicks/impressions. Ta funkcja rankuje frazy wg clicks i zwraca top N.

    Args:
        saas_data: Dict z get_saas_seo_data().
        max_keywords: Maks. liczba fraz do zwrócenia.

    Returns:
        Lista stringów z frazami kluczowymi posortowanymi wg clicks desc.
    """
    keywords = saas_data.get("keywords", [])
    if not keywords:
        return []

    # Sort by clicks descending, then by impressions
    sorted_kw = sorted(
        keywords,
        key=lambda k: (k.get("clicks", 0), k.get("impressions", 0)),
        reverse=True,
    )

    return [kw.get("query", kw.get("keyword", "")) for kw in sorted_kw[:max_keywords] if kw.get("query") or kw.get("keyword")]


def extract_internal_links(saas_data: dict, max_links: int = 10) -> list[dict]:
    """Extract top pages as internal link suggestions.

    CO: Konwerter — z top_pages tworzy listę propozycji linków wewnętrznych.

    PO CO: Generator LLM może wpleść linki do istniejących artykułów portalu
    w generowany tekst — wzmacnia internal linking (SEO factor).

    Args:
        saas_data: Dict z get_saas_seo_data().
        max_links: Maks. liczba linków do zwrócenia.

    Returns:
        Lista dict z kluczami 'url' i 'title' (title = URL path jako fallback).
    """
    pages = saas_data.get("top_pages", [])
    if not pages:
        return []

    # Sort by clicks descending
    sorted_pages = sorted(
        pages,
        key=lambda p: p.get("clicks", 0),
        reverse=True,
    )

    result = []
    for page in sorted_pages[:max_links]:
        url = page.get("page", page.get("url", ""))
        if not url:
            continue
        # Extract a readable title from URL path
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        title = path.split("/")[-1].replace("-", " ").title() if path else url
        result.append({"url": url, "title": title})

    return result
