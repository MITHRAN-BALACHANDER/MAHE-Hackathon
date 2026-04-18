"""Crowd and traffic persistence tracker.

Maintains in-memory observations of road-segment congestion per ~500 m
geographic grid cell.  Observations are seeded automatically from model
signal scores every time routes are ranked.

An *alert* is raised when:
  - congestion OR crowd level exceeds the HIGH_* thresholds
  - the condition has persisted for >= MIN_PERSIST_MINUTES
  - at least MIN_SAMPLES independent observations have been recorded
  - the event is within ALERT_RADIUS_KM of the user OR directly on the
    upcoming path

Edge-case handling:
  - Short-lived spikes (< MIN_PERSIST_MINUTES) are silently ignored
  - Stale observations (> STALE_EVICT_MINUTES with no update) are evicted
  - on-route alerts with persist > 8 min trigger a reroute suggestion
  - Crowd levels adapt to time-of-day and zone density
"""
import math
import time
from dataclasses import dataclass

from model.config import ZONES
from model.utils import haversine

# -----------------------------------------------------------------------
# Thresholds
# -----------------------------------------------------------------------
MIN_PERSIST_MINUTES: float = 5.0
STALE_EVICT_MINUTES: float = 30.0
ALERT_RADIUS_KM: float = 2.5
ON_PATH_RADIUS_KM: float = 0.40   # 400 m
HIGH_CONGESTION: float = 0.65
HIGH_CROWD: float = 0.65
MIN_SAMPLES: int = 2

_DENSITY_SCORE = {"high": 0.85, "medium": 0.55, "low": 0.25}

# Zones considered commercial / high footfall
_COMMERCIAL_KEYWORDS = frozenset(
    ["mg road", "commercial", "market", "mall", "brigade", "church st", "city"]
)


# -----------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------
@dataclass
class CongestionEvent:
    lat: float
    lng: float
    area_name: str
    congestion_level: float   # 0–1, running average
    crowd_level: float        # 0–1, running average
    first_seen: float         # unix timestamp
    last_updated: float       # unix timestamp
    sample_count: int = 1
    source: str = "model"     # "model" | "reported"


# -----------------------------------------------------------------------
# In-memory store
# -----------------------------------------------------------------------
_store: dict[str, CongestionEvent] = {}


def _grid_key(lat: float, lng: float) -> str:
    """~500 m precision key (round to nearest 0.005°)."""
    return f"{round(lat * 200) / 200:.3f},{round(lng * 200) / 200:.3f}"


def _nearest_zone(lat: float, lng: float) -> tuple[str, dict]:
    """Return (zone_name, zone_info) for the nearest zone centre."""
    best_name, best_info, best_d = "MG Road", ZONES["MG Road"], math.inf
    for name, info in ZONES.items():
        d = haversine(lat, lng, info["center"][0], info["center"][1])
        if d < best_d:
            best_name, best_info, best_d = name, info, d
    return best_name, best_info


# -----------------------------------------------------------------------
# Time-based crowd simulation
# -----------------------------------------------------------------------
def time_based_crowd(lat: float, lng: float, hour: float) -> float:
    """Estimate crowd density (0–1) from time-of-day and zone type.

    This is used when no direct crowd measurement is available.
    """
    zone_name, zone_info = _nearest_zone(lat, lng)
    base = _DENSITY_SCORE.get(zone_info.get("density", "medium"), 0.55)
    terrain = zone_info.get("terrain", "")

    # Multiplier by time-of-day
    if 8.0 <= hour < 10.5 or 17.0 <= hour < 20.5:   # rush hours
        mult = 1.00
    elif 12.0 <= hour < 14.0:                          # lunch
        mult = 0.75
    elif hour >= 22.0 or hour < 6.0:                  # night
        mult = 0.12
    elif 10.5 <= hour < 12.0 or 14.0 <= hour < 17.0: # mid-morning/afternoon
        mult = 0.50
    else:                                               # evening wind-down
        mult = 0.40

    # Commercial zones have higher footfall during business hours
    zone_lower = zone_name.lower()
    if any(kw in zone_lower for kw in _COMMERCIAL_KEYWORDS):
        if 10.0 <= hour < 21.0:
            mult = min(mult * 1.35, 1.0)

    # Highway terrain = vehicles, not pedestrian crowd
    if terrain == "highway":
        mult *= 0.35

    return round(min(base * mult, 1.0), 3)


# -----------------------------------------------------------------------
# Recording observations
# -----------------------------------------------------------------------
def record_congestion(
    lat: float,
    lng: float,
    congestion: float,
    crowd: float,
    area_name: str = "",
    source: str = "model",
) -> None:
    """Record or update a congestion observation at a geographic point.

    Uses a running average to smooth out single-sample spikes.
    """
    key = _grid_key(lat, lng)
    now = time.time()
    if key in _store:
        ev = _store[key]
        n = ev.sample_count
        ev.congestion_level = (ev.congestion_level * n + congestion) / (n + 1)
        ev.crowd_level = (ev.crowd_level * n + crowd) / (n + 1)
        ev.sample_count = n + 1
        ev.last_updated = now
    else:
        _store[key] = CongestionEvent(
            lat=lat,
            lng=lng,
            area_name=area_name or _grid_key(lat, lng),
            congestion_level=congestion,
            crowd_level=crowd,
            first_seen=now,
            last_updated=now,
            source=source,
        )


def seed_from_routes(route_dicts: list[dict], hour: float) -> None:
    """Seed the tracker from ranked route scoring results.

    Called after rank_routes().  For each route, samples path points
    and estimates congestion from model segment signals + time-based
    crowd simulation.
    """
    for route in route_dicts:
        path = route.get("path", [])
        if not path:
            continue
        conn = route.get("connectivity", {})
        segs = conn.get("segment_signals", [])
        total = len(path)
        step = max(1, total // 20)   # at most 20 samples per route

        for i in range(0, total, step):
            pt = path[i]
            crowd = time_based_crowd(pt["lat"], pt["lng"], hour)
            if segs:
                sig = segs[min(i, len(segs) - 1)] / 100.0
                # Low signal in a dense area ≈ congestion
                congestion = max(0.0, (1.0 - sig) * crowd)
            else:
                congestion = crowd * 0.30

            if crowd > 0.40 or congestion > 0.35:
                zone_name, _ = _nearest_zone(pt["lat"], pt["lng"])
                record_congestion(
                    pt["lat"], pt["lng"], congestion, crowd, zone_name, "model"
                )


# -----------------------------------------------------------------------
# Alert generation
# -----------------------------------------------------------------------
def get_active_alerts(
    user_lat: float,
    user_lng: float,
    path: list[dict],
) -> list[dict]:
    """Return current congestion/crowd alerts relevant to the user.

    Evicts stale entries, then filters events by:
      1. Above HIGH_* thresholds
      2. Persisted >= MIN_PERSIST_MINUTES
      3. MIN_SAMPLES observations
      4. Within ALERT_RADIUS_KM of user OR on the upcoming path
    """
    now = time.time()

    # Lazy eviction of stale events
    stale = [
        k for k, ev in _store.items()
        if now - ev.last_updated > STALE_EVICT_MINUTES * 60
    ]
    for k in stale:
        del _store[k]

    alerts: list[dict] = []

    for ev in _store.values():
        persist_min = (now - ev.first_seen) / 60.0

        if persist_min < MIN_PERSIST_MINUTES:
            continue
        if ev.sample_count < MIN_SAMPLES:
            continue
        if ev.congestion_level < HIGH_CONGESTION and ev.crowd_level < HIGH_CROWD:
            continue

        dist_user = haversine(user_lat, user_lng, ev.lat, ev.lng)

        on_path = any(
            haversine(ev.lat, ev.lng, pt["lat"], pt["lng"]) < ON_PATH_RADIUS_KM
            for pt in path
        )

        if dist_user > ALERT_RADIUS_KM and not on_path:
            continue

        # Build alert payload
        types: list[str] = []
        if ev.congestion_level >= HIGH_CONGESTION:
            types.append("heavy traffic")
        if ev.crowd_level >= HIGH_CROWD:
            types.append("large crowd")

        severity = (
            "high"
            if ev.congestion_level > 0.82 or ev.crowd_level > 0.82
            else "medium"
        )
        persist_str = (
            f"{int(persist_min)} min" if persist_min < 60
            else f"{persist_min / 60:.1f} hr"
        )
        condition = " & ".join(types) or "congestion"
        suggest_reroute = on_path and persist_min >= 8.0

        if on_path:
            message = (
                f"Your route has {condition} ahead near {ev.area_name}, "
                f"persisting for {persist_str}."
                + (" Consider an alternate route." if suggest_reroute else "")
            )
        else:
            message = (
                f"{condition.capitalize()} detected {dist_user:.1f} km away "
                f"near {ev.area_name}, active for {persist_str}."
            )

        alerts.append(
            {
                "lat": ev.lat,
                "lng": ev.lng,
                "area": ev.area_name,
                "type": condition,
                "congestion_level": round(ev.congestion_level, 2),
                "crowd_level": round(ev.crowd_level, 2),
                "persist_minutes": round(persist_min, 1),
                "distance_km": round(dist_user, 2),
                "on_route": on_path,
                "severity": severity,
                "message": message,
                "suggest_reroute": suggest_reroute,
            }
        )

    # On-route alerts first, then by proximity
    alerts.sort(key=lambda a: (not a["on_route"], a["distance_km"]))
    return alerts
