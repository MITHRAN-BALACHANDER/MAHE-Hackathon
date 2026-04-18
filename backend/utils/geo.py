import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two geographic points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def sample_points_along_route(
    geometry: list[tuple[float, float]],
    interval_m: float = 500.0,
) -> list[tuple[float, float]]:
    """Sample points along a polyline at regular intervals.

    Returns a list of (lat, lon) tuples roughly *interval_m* meters apart.
    Always includes the first and last points.
    """
    if len(geometry) < 2:
        return list(geometry)

    sampled: list[tuple[float, float]] = [geometry[0]]
    accumulated = 0.0

    for i in range(1, len(geometry)):
        prev = geometry[i - 1]
        curr = geometry[i]
        seg_dist = haversine(prev[0], prev[1], curr[0], curr[1])
        accumulated += seg_dist

        if accumulated >= interval_m:
            sampled.append(curr)
            accumulated = 0.0

    # Always include the last point
    if sampled[-1] != geometry[-1]:
        sampled.append(geometry[-1])

    return sampled


def interpolate_point(
    lat1: float, lon1: float, lat2: float, lon2: float, fraction: float
) -> tuple[float, float]:
    """Linearly interpolate between two points."""
    return (
        lat1 + (lat2 - lat1) * fraction,
        lon1 + (lon2 - lon1) * fraction,
    )
