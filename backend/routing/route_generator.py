"""Convenience wrapper: builds CandidateRoute objects for the route service."""

from backend.routing.osrm_client import OSRMClient, CandidateRoute


async def generate_candidate_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    use_mock: bool = False,
) -> list[CandidateRoute]:
    """Fetch candidate routes from OSRM (or mock)."""
    client = OSRMClient(use_mock=use_mock)
    return await client.get_routes(origin_lat, origin_lon, dest_lat, dest_lon)
