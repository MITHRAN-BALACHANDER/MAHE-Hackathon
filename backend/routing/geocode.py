"""Geocoding service using OpenStreetMap Nominatim API.

Provides free-form location search (e.g. "MIT Bangalore", "Electronic City")
and returns lat/lon coordinates. Results are cached in-memory to avoid
repeated calls to the Nominatim rate-limited API.
"""
from __future__ import annotations

from typing import TypedDict

import httpx

from backend.core.logging import logger

# ---------------------------------------------------------------------------
# In-memory cache: cache_key -> list of results
# ---------------------------------------------------------------------------
_CACHE: dict[str, list["GeoResult"]] = {}

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "SignalRoute/1.0 (hackathon; github.com/MAHE-Hackathon)"
_TIMEOUT_S = 5.0


class GeoResult(TypedDict):
    city: str   # full display_name from Nominatim
    lat: float
    lon: float


async def geocode_query(
    query: str,
    limit: int = 5,
    *,
    countrycodes: str = "in",
) -> list[GeoResult]:
    """Geocode a free-form location string using Nominatim.

    Parameters
    ----------
    query : free-form text, e.g. ``"MIT Bangalore"`` or ``"MG Road"``
    limit : maximum number of candidate results (1-10)
    countrycodes : ISO 3166-1 alpha-2 filter. Default ``"in"`` (India).

    Returns
    -------
    List of :class:`GeoResult` dicts. Empty on failure or no results.
    """
    cache_key = f"{query.lower().strip()}:{limit}:{countrycodes}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": limit,
                    "addressdetails": 0,
                    "countrycodes": countrycodes,
                },
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            data: list[dict] = resp.json()
    except httpx.TimeoutException:
        logger.warning("Nominatim geocode timeout for query: %r", query)
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Nominatim HTTP %s for query: %r", exc.response.status_code, query
        )
        return []
    except Exception:
        logger.exception("Unexpected geocode error for query: %r", query)
        return []

    results: list[GeoResult] = [
        GeoResult(
            city=item["display_name"],
            lat=float(item["lat"]),
            lon=float(item["lon"]),
        )
        for item in data
    ]
    _CACHE[cache_key] = results
    return results
