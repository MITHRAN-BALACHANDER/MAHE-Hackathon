"""Geocoding service using OpenStreetMap Nominatim API.

Provides free-form location search (e.g. "MIT Bangalore", "Electronic City")
and returns lat/lon coordinates. Results are cached in-memory to avoid
repeated calls to the Nominatim rate-limited API.
"""
from __future__ import annotations

import asyncio
import os
from collections import OrderedDict
from typing import TypedDict

import httpx

from backend.core.logging import logger

# ---------------------------------------------------------------------------
# LRU cache with max size + Nominatim rate limiter (1 req/sec)
# ---------------------------------------------------------------------------
_MAX_CACHE_SIZE = 1000
_CACHE: OrderedDict[str, list["GeoResult"]] = OrderedDict()
_NOMINATIM_SEMAPHORE = asyncio.Semaphore(1)  # serialize Nominatim calls

_NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
_NOMINATIM_REVERSE_URL = os.environ.get(
    "NOMINATIM_REVERSE_URL", "https://nominatim.openstreetmap.org/reverse"
)
_USER_AGENT = "SignalRoute/1.0 (hackathon; github.com/MAHE-Hackathon)"
_TIMEOUT_S = 5.0

# Bounding box that biases forward-geocode results toward Bengaluru
_BANGALORE_VIEWBOX = os.environ.get("NOMINATIM_VIEWBOX", "77.35,12.70,77.82,13.20")


def _cache_put(key: str, value: list["GeoResult"]) -> None:
    """Insert into bounded LRU cache, evicting oldest if full."""
    if key in _CACHE:
        _CACHE.move_to_end(key)
    _CACHE[key] = value
    while len(_CACHE) > _MAX_CACHE_SIZE:
        _CACHE.popitem(last=False)


class GeoResult(TypedDict):
    city: str   # full display_name from Nominatim
    lat: float
    lon: float


async def geocode_query(
    query: str,
    limit: int = 5,
    *,
    countrycodes: str = "in",
    viewbox: str = _BANGALORE_VIEWBOX,
    bounded: int = 0,
) -> list[GeoResult]:
    """Geocode a free-form location string using Nominatim.

    Parameters
    ----------
    query : free-form text, e.g. ``"MIT Bangalore"`` or ``"MG Road"``
    limit : maximum number of candidate results (1-10)
    countrycodes : ISO 3166-1 alpha-2 filter. Default ``"in"`` (India).
    viewbox : bias results toward this bounding box (minlon,minlat,maxlon,maxlat).
    bounded : 0 = prefer viewbox, 1 = restrict to viewbox only.

    Returns
    -------
    List of :class:`GeoResult` dicts. Empty on failure or no results.
    """
    cache_key = f"{query.lower().strip()}:{limit}:{countrycodes}:{viewbox}:{bounded}"
    if cache_key in _CACHE:
        _CACHE.move_to_end(cache_key)  # refresh LRU position
        return _CACHE[cache_key]

    # Serialize Nominatim calls to respect 1 req/sec rate limit
    async with _NOMINATIM_SEMAPHORE:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                params: dict = {
                    "q": query,
                    "format": "json",
                    "limit": limit,
                    "addressdetails": 0,
                    "countrycodes": countrycodes,
                }
                if viewbox:
                    params["viewbox"] = viewbox
                    params["bounded"] = bounded
                resp = await client.get(
                    _NOMINATIM_URL,
                    params=params,
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
    _cache_put(cache_key, results)
    return results


async def reverse_geocode_query(lat: float, lon: float) -> GeoResult | None:
    """Reverse geocode a lat/lon pair to a human-readable place name.

    Uses Nominatim's ``/reverse`` endpoint which is designed for coordinate
    lookup (unlike ``/search`` which expects text queries).

    Parameters
    ----------
    lat : latitude in decimal degrees
    lon : longitude in decimal degrees

    Returns
    -------
    A :class:`GeoResult` dict, or ``None`` on failure.
    """
    cache_key = f"rev:{round(lat, 5)}:{round(lon, 5)}"
    if cache_key in _CACHE:
        _CACHE.move_to_end(cache_key)
        cached = _CACHE[cache_key]
        return cached[0] if cached else None

    async with _NOMINATIM_SEMAPHORE:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                resp = await client.get(
                    _NOMINATIM_REVERSE_URL,
                    params={
                        "lat": lat,
                        "lon": lon,
                        "format": "json",
                        "zoom": 14,
                        "addressdetails": 1,
                    },
                    headers={"User-Agent": _USER_AGENT},
                )
                resp.raise_for_status()
                data: dict = resp.json()
        except httpx.TimeoutException:
            logger.warning("Nominatim reverse timeout for (%s, %s)", lat, lon)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Nominatim reverse HTTP %s for (%s, %s)",
                exc.response.status_code, lat, lon,
            )
            return None
        except Exception:
            logger.exception("Unexpected reverse geocode error for (%s, %s)", lat, lon)
            return None

    if "error" in data or "display_name" not in data:
        _cache_put(cache_key, [])
        return None

    # Build a readable name from structured address components
    addr = data.get("address", {})
    area = (
        addr.get("neighbourhood")
        or addr.get("village")
        or addr.get("town")
        or ""
    )
    if not area:
        suburb = addr.get("suburb", "")
        if suburb and "Ward" not in suburb and "Corporation" not in suburb:
            area = suburb
    if not area:
        area = (
            addr.get("county", "")
            .replace(" taluku", "")
            .replace(" taluk", "")
            .strip()
        )
    city = (
        addr.get("city")
        or addr.get("state_district", "")
            .replace(" Urban District", "")
            .replace(" Rural District", "")
            .strip()
        or ""
    )
    if city == area:
        city = ""
    if area or city:
        display_name = f"{area}, {city}".strip(", ") if area and city else (area or city)
    else:
        display_name = data["display_name"]

    result = GeoResult(
        city=display_name,
        lat=float(data["lat"]),
        lon=float(data["lon"]),
    )
    _cache_put(cache_key, [result])
    return result
