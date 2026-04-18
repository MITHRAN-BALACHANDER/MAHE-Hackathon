"""OSRM client for fetching candidate routes.

Supports both real OSRM HTTP API and a built-in mock for local dev.
"""

from dataclasses import dataclass, field

import httpx

from backend.core.config import settings
from backend.core.logging import logger
from backend.routing.polyline import decode_polyline


@dataclass
class CandidateRoute:
    """A single candidate route returned by OSRM."""

    geometry: list[tuple[float, float]]
    eta_seconds: float
    distance_meters: float
    legs: list[dict] = field(default_factory=list)


class OSRMClient:
    """Async OSRM HTTP client with mock fallback."""

    def __init__(self, base_url: str | None = None, use_mock: bool = False) -> None:
        self._base_url = (base_url or settings.OSRM_URL).rstrip("/")
        self._use_mock = use_mock
        self._timeout = settings.OSRM_TIMEOUT_S

    async def get_routes(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        alternatives: int = 3,
    ) -> list[CandidateRoute]:
        if self._use_mock:
            return self._mock_routes(origin_lat, origin_lon, dest_lat, dest_lon)

        return await self._fetch_routes(
            origin_lat, origin_lon, dest_lat, dest_lon, alternatives
        )

    async def _fetch_routes(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        alternatives: int,
    ) -> list[CandidateRoute]:
        # OSRM uses lon,lat ordering
        coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{self._base_url}/route/v1/driving/{coords}"
        params = {
            "overview": "full",
            "geometries": "polyline",
            "alternatives": str(alternatives),
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error(f"OSRM request failed: {exc}")
            return self._mock_routes(origin_lat, origin_lon, dest_lat, dest_lon)

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"OSRM returned no routes: {data.get('code')}")
            return self._mock_routes(origin_lat, origin_lon, dest_lat, dest_lon)

        candidates: list[CandidateRoute] = []
        for route in data["routes"][:alternatives]:
            geometry = decode_polyline(route["geometry"])
            candidates.append(
                CandidateRoute(
                    geometry=geometry,
                    eta_seconds=route["duration"],
                    distance_meters=route["distance"],
                )
            )

        return candidates

    @staticmethod
    def _mock_routes(
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> list[CandidateRoute]:
        """Generate 3 synthetic candidate routes for dev/test."""
        mid_lat = (origin_lat + dest_lat) / 2
        mid_lon = (origin_lon + dest_lon) / 2

        from backend.utils.geo import haversine

        direct_dist = haversine(origin_lat, origin_lon, dest_lat, dest_lon)

        routes = [
            # Direct route
            CandidateRoute(
                geometry=[
                    (origin_lat, origin_lon),
                    (mid_lat, mid_lon),
                    (dest_lat, dest_lon),
                ],
                eta_seconds=direct_dist / 8.33,  # ~30 km/h
                distance_meters=direct_dist,
            ),
            # Northern detour
            CandidateRoute(
                geometry=[
                    (origin_lat, origin_lon),
                    (mid_lat + 0.01, mid_lon - 0.005),
                    (mid_lat + 0.005, mid_lon + 0.005),
                    (dest_lat, dest_lon),
                ],
                eta_seconds=direct_dist * 1.2 / 8.33,
                distance_meters=direct_dist * 1.2,
            ),
            # Southern detour
            CandidateRoute(
                geometry=[
                    (origin_lat, origin_lon),
                    (mid_lat - 0.01, mid_lon + 0.005),
                    (mid_lat - 0.005, mid_lon - 0.005),
                    (dest_lat, dest_lon),
                ],
                eta_seconds=direct_dist * 1.35 / 8.33,
                distance_meters=direct_dist * 1.35,
            ),
        ]

        return routes
