"""SignalRoute Backend -- complete FastAPI server.

Serves three API surfaces:
  /api/*     -- Frontend endpoints (GET/POST for the Next.js UI)
  /model/*   -- ML model endpoints (PUT, direct model access + RL learning)

Run:
  python -m backend.main
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import sys
import random
import asyncio
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Import the existing FastAPI app (has all PUT /model/* endpoints + CORS)
from model.main import (
    app,
    _towers_to_df,
    _build_segments,
    _detect_edge_cases,
)

# Model internals
from model.config import ZONES, DATA_DIR
from model.utils import haversine, extract_features
from model.scoring import rank_routes
from model.bad_zones import detect_bad_zones, assess_task_feasibility
from model.explainability import explain_recommendation, compare_routes_summary
from model.smart_preference import get_smart_preference
from model.inference import predict_single
from model.rl_learning import get_bandit
from model.opencellid import get_towers, refresh_towers, load_real_towers, fetch_towers_for_path
from model.schemas import (
    AutoRouteRequest, AutoRouteResponse,
    RecordTripRequest, RecordTripResponse,
    UserPatternsRequest, UserPatternsResponse,
    RouteResult, BadZone, TaskFeasibility,
    RLInfo, PatternInfo,
)
from backend.routing.tomtom_client import TomTomClient
from backend.routing.geocode import geocode_query, reverse_geocode_query
from backend.db.base import MongoClient

# Mount the auth router so /api/v1/login and /api/v1/register work
from backend.api.routes import router as _auth_router
app.include_router(_auth_router, prefix="/api/v1", tags=["auth"])

# Update app metadata for the full backend
app.title = "SignalRoute Backend"
app.description = "Cellular network-aware routing with reinforcement learning"
app.version = "2.0.0"

# -----------------------------------------------------------------------
# Register new modular routers (enterprise architecture)
# -----------------------------------------------------------------------

try:
    from backend.api.auth import router as auth_router
    app.include_router(auth_router)
except ImportError:
    pass  # Auth module not available

try:
    from backend.api.network import router as network_router
    app.include_router(network_router)
except ImportError:
    pass  # Network detection module not available

# -----------------------------------------------------------------------
# Enterprise middleware stack
# -----------------------------------------------------------------------

try:
    from backend.core.middleware import (
        RequestIdMiddleware,
        RequestLoggingMiddleware,
        ErrorHandlingMiddleware,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
except ImportError:
    pass  # Middleware not available

# -----------------------------------------------------------------------
# Initialize service bus
# -----------------------------------------------------------------------

try:
    from backend.core.grpc_bus import service_bus
    service_bus.register("route_service", "2.0.0")
    service_bus.register("signal_service", "1.0.0")
    service_bus.register("scoring_service", "1.0.0")
    service_bus.register("rl_service", "1.0.0")

    @app.get("/api/services/health")
    async def services_health():
        """Health check for all registered internal services."""
        return {
            "status": "healthy",
            "services": service_bus.health(),
            "architecture": "modular_monolith",
            "communication": "internal_grpc_bus",
        }
except ImportError:
    pass  # Service bus not available

# -----------------------------------------------------------------------
# TomTom routing client (shared instance with connection reuse)
# -----------------------------------------------------------------------

_tomtom = TomTomClient(
    api_key=os.getenv("TOMTOM_API_KEY", ""),
    base_url=os.getenv("TOMTOM_BASE_URL", "https://api.tomtom.com"),
)


@app.on_event("startup")
async def _startup_tomtom():
    await _tomtom.startup()
    try:
        await MongoClient.connect()
    except Exception:
        pass  # MongoDB is optional; auth won't work without it


@app.on_event("shutdown")
async def _shutdown_tomtom():
    await _tomtom.shutdown()
    await MongoClient.disconnect()


# -----------------------------------------------------------------------
# Location lookup for Bangalore
# -----------------------------------------------------------------------

async def _resolve_location(name: str) -> tuple[float, float]:
    """Resolve a place name or @lat,lng string to (lat, lng) coordinates.

    Lookup order:
    1. ``"@lat,lng"`` -- geocoded coordinate pair already supplied by the frontend
    2. Nominatim geocoding via the existing geocode service (dynamic, cached)
    3. ZONES substring match (instant fallback if geocoding fails/times out)
    4. Default: MG Road (Bangalore city centre)
    """
    # Coordinate pair already resolved by the frontend SearchBar
    if name.startswith("@"):
        try:
            lat_s, lng_s = name[1:].split(",", 1)
            return (float(lat_s), float(lng_s))
        except (ValueError, IndexError):
            pass

    # Dynamic geocoding via Nominatim (result is in-memory cached)
    try:
        results = await geocode_query(name.strip(), limit=1)
        if results:
            return (results[0]["lat"], results[0]["lon"])
    except Exception:
        pass  # fall through to static fallbacks

    # Static fallback: ZONES substring match (no network required)
    key = name.lower().strip()
    for zone_name, info in ZONES.items():
        if key in zone_name.lower() or zone_name.lower() in key:
            return info["center"]

    return ZONES["MG Road"]["center"]  # default fallback


# -----------------------------------------------------------------------
# Tower data cache (prefers real OpenCelliD data over synthetic)
# -----------------------------------------------------------------------

_cached_towers: pd.DataFrame | None = None


def _get_towers() -> pd.DataFrame:
    """Load tower data (cached). Prefers real OpenCelliD data."""
    global _cached_towers
    if _cached_towers is not None:
        return _cached_towers
    _cached_towers = get_towers(prefer_real=True)
    return _cached_towers


def _invalidate_tower_cache():
    """Clear the tower cache so next request reloads from disk."""
    global _cached_towers
    _cached_towers = None


def _merge_route_towers(route_dicts: list[dict]) -> pd.DataFrame:
    """Merge per-route live tower DataFrames into one de-duplicated DataFrame.

    Always blends in the synthetic/global tower base so the model sees the
    dense calibrated distribution it was trained on. Real per-route towers
    are appended for additional real-world radio/tech feature diversity.
    """
    base = _get_towers()  # always include synthetic base

    live_frames = [
        r["towers"] for r in route_dicts
        if "towers" in r and r["towers"] is not None and not r["towers"].empty
    ]

    if not live_frames:
        return base

    # Only append live towers with precise coordinates (>2 decimal places)
    # to avoid replacing calibrated synthetic with coarse OpenCelliD grid data
    precise_frames = []
    for df in live_frames:
        if df.empty:
            continue
        precise = df[(df["lat"].round(2) != df["lat"]) | (df["lng"].round(2) != df["lng"])]
        if not precise.empty:
            precise_frames.append(precise)

    if not precise_frames:
        return base

    combined = pd.concat([base] + precise_frames, ignore_index=True)
    if "tower_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["tower_id"])
    return combined


# -----------------------------------------------------------------------
# Route generation between two locations
# -----------------------------------------------------------------------

def _build_path(
    src: tuple, dst: tuple, via: list[tuple], n_interp: int = 4,
) -> list[dict]:
    """Build a path from source through waypoints to destination."""
    waypoints = [src] + via + [dst]
    path = []
    for i in range(len(waypoints) - 1):
        lat1, lng1 = waypoints[i]
        lat2, lng2 = waypoints[i + 1]
        for j in range(n_interp):
            t = j / n_interp
            path.append({
                "lat": round(lat1 + t * (lat2 - lat1) + random.gauss(0, 0.0008), 6),
                "lng": round(lng1 + t * (lng2 - lng1) + random.gauss(0, 0.0008), 6),
            })
    path.append({"lat": round(dst[0], 6), "lng": round(dst[1], 6)})
    return path


def _zones_along_path(path: list[dict]) -> list[str]:
    """Identify ZONES that the path passes through."""
    zone_names = []
    seen = set()
    for pt in path[::max(1, len(path) // 10)]:  # sample ~10 points
        for name, info in ZONES.items():
            if name in seen:
                continue
            c = info["center"]
            if haversine(pt["lat"], pt["lng"], c[0], c[1]) < 3.0:  # within 3 km
                zone_names.append(name)
                seen.add(name)
    return zone_names


def _generate_routes_sync(
    src: tuple[float, float], dst: tuple[float, float],
) -> list[dict]:
    """Synthetic fallback routes (straight-line interpolation) -- up to 7 routes."""
    total_dist = haversine(src[0], src[1], dst[0], dst[1])

    candidates = []
    for name, info in ZONES.items():
        c = info["center"]
        d_src = haversine(src[0], src[1], c[0], c[1])
        d_dst = haversine(dst[0], dst[1], c[0], c[1])
        if d_src + d_dst < total_dist * 2.5 and d_src > 0.3 and d_dst > 0.3:
            candidates.append((name, c, d_src, info["density"]))
    candidates.sort(key=lambda x: x[2])

    routes = []

    # 1. Fastest Route -- nearest 2 waypoints, high speed
    fast_via = [c[1] for c in candidates[:2]]
    fast_dist = total_dist * 1.1
    routes.append({
        "name": "Fastest Route",
        "eta": round(fast_dist / 40 * 60, 1),
        "distance": round(fast_dist, 1),
        "path": _build_path(src, dst, fast_via, 3),
        "zones": [c[0] for c in candidates[:2]],
    })

    # 2. Balanced Route -- nearest 4 waypoints
    bal_via = [c[1] for c in candidates[:4]]
    bal_dist = total_dist * 1.25
    routes.append({
        "name": "Balanced Route",
        "eta": round(bal_dist / 35 * 60, 1),
        "distance": round(bal_dist, 1),
        "path": _build_path(src, dst, bal_via, 4),
        "zones": [c[0] for c in candidates[:4]],
    })

    # 3. Best Signal Route -- prefer high-density zones
    sig_cands = sorted(candidates, key=lambda x: 0 if x[3] == "high" else 1)
    sig_sorted = sorted(sig_cands[:5], key=lambda x: x[2])
    sig_via = [c[1] for c in sig_sorted]
    sig_dist = total_dist * 1.4
    routes.append({
        "name": "Best Signal Route",
        "eta": round(sig_dist / 30 * 60, 1),
        "distance": round(sig_dist, 1),
        "path": _build_path(src, dst, sig_via, 5),
        "zones": [c[0] for c in sig_sorted],
    })

    # 4. Eco Route -- moderate distance, steady speed
    eco_via = [c[1] for c in candidates[1:4]] if len(candidates) >= 4 else fast_via
    eco_dist = total_dist * 1.35
    routes.append({
        "name": "Eco Route",
        "eta": round(eco_dist / 33 * 60, 1),
        "distance": round(eco_dist, 1),
        "path": _build_path(src, dst, eco_via, 4),
        "zones": [c[0] for c in candidates[1:4]] if len(candidates) >= 4 else [c[0] for c in candidates[:2]],
    })

    # 5. Low Traffic Route -- prefer medium/low density zones (less congested)
    low_cands = sorted(candidates, key=lambda x: 0 if x[3] == "low" else (1 if x[3] == "medium" else 2))
    low_sorted = sorted(low_cands[:4], key=lambda x: x[2])
    low_via = [c[1] for c in low_sorted]
    low_dist = total_dist * 1.30
    routes.append({
        "name": "Low Traffic Route",
        "eta": round(low_dist / 36 * 60, 1),
        "distance": round(low_dist, 1),
        "path": _build_path(src, dst, low_via, 4),
        "zones": [c[0] for c in low_sorted],
    })

    # 6. Highway Route -- medium waypoints, higher speed
    hw_via = [c[1] for c in candidates[:3]]
    hw_dist = total_dist * 1.20
    routes.append({
        "name": "Highway Route",
        "eta": round(hw_dist / 45 * 60, 1),
        "distance": round(hw_dist, 1),
        "path": _build_path(src, dst, hw_via, 3),
        "zones": [c[0] for c in candidates[:3]],
    })

    # 7. Scenic Route -- many waypoints, relaxed speed
    sc_via = [c[1] for c in candidates[:6]]
    sc_dist = total_dist * 1.50
    routes.append({
        "name": "Scenic Route",
        "eta": round(sc_dist / 28 * 60, 1),
        "distance": round(sc_dist, 1),
        "path": _build_path(src, dst, sc_via, 5),
        "zones": [c[0] for c in candidates[:6]],
    })

    return routes


_ROUTE_NAMES = [
    "Fastest Route",
    "Balanced Route",
    "Best Signal Route",
    "Eco Route",
    "Low Traffic Route",
    "Highway Route",
    "Scenic Route",
]
_MAX_ROUTES = 7  # hard cap on routes returned to the frontend


async def _generate_routes(
    src: tuple[float, float], dst: tuple[float, float],
) -> list[dict]:
    """Fetch road-snapped routes from TomTom, fall back to synthetic.

    After building geometry, fetches real cell towers from OpenCelliD along
    each route and attaches them as ``route["towers"]`` for the scoring model.
    """
    if not _tomtom._api_key:
        routes = _generate_routes_sync(src, dst)
    else:
        try:
            tt_routes = await _tomtom.get_routes(src, dst)
        except Exception:
            routes = _generate_routes_sync(src, dst)
        else:
            if not tt_routes or not tt_routes[0].get("geometry"):
                routes = _generate_routes_sync(src, dst)
            else:
                total_dist = haversine(src[0], src[1], dst[0], dst[1])
                routes = []
                for i, tt in enumerate(tt_routes):
                    path = tt["geometry"]
                    dist_km = 0.0
                    for j in range(len(path) - 1):
                        dist_km += haversine(
                            path[j]["lat"], path[j]["lng"],
                            path[j + 1]["lat"], path[j + 1]["lng"],
                        )
                    dist_km = dist_km if dist_km > 0 else total_dist
                    name = _ROUTE_NAMES[i] if i < len(_ROUTE_NAMES) else f"Route {i + 1}"
                    zones = _zones_along_path(path)
                    routes.append({
                        "name": name,
                        "eta": tt["eta"],
                        "distance": round(dist_km, 1),
                        "path": path,
                        "zones": zones,
                        "traffic_delay": tt.get("traffic_delay", 0),
                    })
                # Cap at _MAX_ROUTES
                routes = routes[:_MAX_ROUTES]

                # If TomTom returned fewer than 5 routes, pad with synthetic
                # alternatives so the map always shows visually distinct paths.
                if len(routes) < 5:
                    synthetic = _generate_routes_sync(src, dst)
                    existing_names = {r["name"] for r in routes}
                    for syn in synthetic:
                        if len(routes) >= 5:
                            break
                        if syn["name"] not in existing_names:
                            routes.append(syn)

    # Fetch real cell towers along each route from OpenCelliD (parallel via executor)
    loop = asyncio.get_event_loop()

    async def _fetch_for_route(path: list[dict]) -> pd.DataFrame:
        return await loop.run_in_executor(
            None,
            lambda: fetch_towers_for_path(path, sample_every_n=30, max_towers=150, radius_km=0.8),
        )

    tower_tasks = [_fetch_for_route(r["path"]) for r in routes]
    per_route_towers = await asyncio.gather(*tower_tasks)

    # Attach real towers; fall back to global cached data if API returned nothing
    fallback_towers = _get_towers()
    for route, rt in zip(routes, per_route_towers):
        if rt is not None and not rt.empty:
            route["towers"] = rt
        else:
            route["towers"] = fallback_towers

    return routes


# =======================================================================
# FRONTEND ENDPOINTS  (GET / POST  --  /api/*)
# =======================================================================

# -----------------------------------------------------------------------
# GET /api/routes
# -----------------------------------------------------------------------

@app.get("/api/routes")
async def api_routes(
    source: str = Query("MIT", max_length=200),
    destination: str = Query("Airport", max_length=200),
    preference: float = Query(50, ge=0, le=100),
    telecom: str = Query("all", max_length=20),
    max_eta_factor: float = Query(1.5, ge=0, le=10),
):
    """Score routes between two named locations.

    Parameters
    ----------
    max_eta_factor : hard constraint -- reject routes with ETA > fastest * ratio.
                     Default 1.5 (50% slower than fastest). Set 0 to disable.
    telecom : "all", "jio", "airtel", "vi", or "multi" for multi-SIM optimization.
    """
    src, dst = await asyncio.gather(_resolve_location(source), _resolve_location(destination))
    route_dicts = await _generate_routes(src, dst)

    # Merge per-route live towers into one de-duplicated DataFrame for scoring
    towers_df = _merge_route_towers(route_dicts)

    # If max_eta_factor is 0 or negative, disable hard constraint
    effective_max = max_eta_factor if max_eta_factor > 0 else 999.0

    include_multi_sim = telecom.lower() == "multi"
    score_telecom = "all" if include_multi_sim else telecom

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=preference, telecom=score_telecom,
        time_hour=12.0, weather_factor=1.0, speed_kmh=40.0,
        max_eta_ratio=effective_max,
        include_multi_sim=include_multi_sim,
    )

    results = []
    for r in ranked:
        conn = r.get("connectivity", {})

        # Detect bad zones along this route
        bad_zones = detect_bad_zones(
            r["path"],
            conn.get("segment_signals", []),
            avg_speed_kmh=40.0,
        )

        entry = {
            "name": r["name"],
            "eta": r["eta"],
            "distance": r["distance"],
            "signal_score": r.get("signal_score", 0),
            "weighted_score": r.get("weighted_score", 0),
            "zones": r.get("zones", []),
            "path": r["path"],
            "rejected": r.get("rejected", False),
            # Stability metrics
            "stability_score": r.get("stability_score", 50),
            "continuity_score": r.get("continuity_score", 50),
            "signal_variance": r.get("signal_variance", 0),
            "longest_stable_window": r.get("longest_stable_window", 0),
            # Bad zone predictions
            "bad_zones": [
                {
                    "start_coord": bz["start_coord"],
                    "end_coord": bz["end_coord"],
                    "length_km": bz["length_km"],
                    "min_signal": bz["min_signal"],
                    "time_to_zone_min": bz["time_to_zone_min"],
                    "zone_duration_min": bz["zone_duration_min"],
                    "edge_zone_name": bz.get("edge_zone_name"),
                    "warning": bz["warning"],
                }
                for bz in bad_zones
            ],
        }

        # Multi-SIM data
        if r.get("multi_sim"):
            entry["multi_sim"] = r["multi_sim"]

        results.append(entry)

    rec = results[0]["name"] if results else "None"
    return {
        "source": source,
        "destination": destination,
        "preference": preference,
        "max_eta_factor": effective_max,
        "routes": results,
        "recommended_route": rec,
    }


# -----------------------------------------------------------------------
# GET /api/heatmap
# -----------------------------------------------------------------------

@app.get("/api/heatmap")
def api_heatmap():
    """Signal-strength heatmap for all Bangalore zones."""
    towers_df = _get_towers()
    zones = []
    for name, info in ZONES.items():
        lat, lng = info["center"]
        try:
            feats = extract_features(lat, lng, towers_df, 12.0, 1.0, 40.0)
            result = predict_single(feats)
            score = result["signal_strength"]
        except Exception:
            score = 50.0

        if score >= 70:
            strength, color = "strong", "#22c55e"
        elif score >= 40:
            strength, color = "medium", "#eab308"
        else:
            strength, color = "weak", "#ef4444"

        zones.append({
            "name": name,
            "lat": lat,
            "lng": lng,
            "score": round(score, 1),
            "signal_strength": strength,
            "color": color,
        })

    return {"zones": zones}


# -----------------------------------------------------------------------
# GET /api/predict
# -----------------------------------------------------------------------

@app.get("/api/predict")
def api_predict(
    zone: str = Query(..., max_length=100, description="Zone name to predict signal for"),
    minutes: int = Query(15, ge=1, le=120),
):
    """Short-horizon signal prediction for a zone."""
    zone_info = None
    zone_name = zone
    for name, info in ZONES.items():
        if zone.lower() in name.lower():
            zone_info = info
            zone_name = name
            break

    if zone_info is None:
        return {
            "zone": zone,
            "horizon_minutes": minutes,
            "expected_signal_score": 50,
            "message": f"Zone '{zone}' not found. Using default prediction.",
        }

    lat, lng = zone_info["center"]
    towers_df = _get_towers()
    try:
        feats = extract_features(lat, lng, towers_df, 12.0, 1.0, 40.0)
        result = predict_single(feats)
        score = result["signal_strength"]
    except Exception:
        score = 50.0

    if score >= 70:
        msg = f"Signal expected to remain strong in {zone_name} for the next {minutes} minutes."
    elif score >= 40:
        msg = f"Moderate signal expected in {zone_name}. Consider pre-loading content before entering."
    else:
        msg = f"Weak signal expected in {zone_name} for the next {minutes} minutes. Download offline maps recommended."

    return {
        "zone": zone_name,
        "horizon_minutes": minutes,
        "expected_signal_score": round(score, 1),
        "message": msg,
    }


# -----------------------------------------------------------------------
# POST /api/reroute
# -----------------------------------------------------------------------

class _RerouteBody(BaseModel):
    source: str
    destination: str
    current_zone: str = ""
    preference: float = 50
    telecom: str = "all"


@app.post("/api/reroute")
async def api_reroute(body: _RerouteBody):
    """Reroute with bias toward better signal."""
    src, dst = await asyncio.gather(_resolve_location(body.source), _resolve_location(body.destination))
    route_dicts = await _generate_routes(src, dst)
    towers_df = _merge_route_towers(route_dicts)
    pref = max(body.preference, 70)  # bias toward signal on reroute
    ranked = rank_routes(
        route_dicts, towers_df,
        preference=pref, telecom=body.telecom,
        time_hour=12.0, weather_factor=1.0, speed_kmh=40.0,
    )

    best = ranked[0] if ranked else route_dicts[0]
    selected = {
        "name": best["name"],
        "eta": best["eta"],
        "distance": best["distance"],
        "signal_score": best.get("signal_score", 0),
        "weighted_score": best.get("weighted_score", 0),
        "zones": best.get("zones", []),
        "path": best["path"],
    }

    zone_str = body.current_zone or "your current area"
    return {
        "message": f"Rerouting to avoid weak signal in {zone_str}.",
        "selected_route": selected,
        "advisory": (
            f"Signal drop detected ahead. "
            f"Switching to {best['name']} for better connectivity."
        ),
    }


# =======================================================================
# TOWER DATA ENDPOINTS  (GET/PUT  --  /api/towers, /model/refresh-towers)
# =======================================================================

# -----------------------------------------------------------------------
# GET /api/geocode  (location name -> lat/lon via Nominatim)
# -----------------------------------------------------------------------

@app.get("/api/geocode")
async def api_geocode(
    q: str = Query("", description="Free-form location query, e.g. 'MIT Bangalore'"),
    limit: int = Query(5, ge=1, le=10, description="Max results to return"),
):
    """Convert a location name to lat/lon using OpenStreetMap Nominatim.

    Supports any free-form query such as ``"MIT Bangalore"``, ``"Koramangala"``,
    or ``"Electronic City, Bengaluru"``. Results are cached in-memory.

    Returns a list of matching locations, each with:
    - ``city``: full display name from Nominatim
    - ``lat``: latitude
    - ``lon``: longitude
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    results = await geocode_query(q.strip(), limit=limit)

    # Return empty list (200) when Nominatim finds nothing — avoids red 404 in browser
    return results


# -----------------------------------------------------------------------
# GET /api/reverse-geocode  (lat,lon -> place name via Nominatim /reverse)
# -----------------------------------------------------------------------

@app.get("/api/reverse-geocode")
async def api_reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Convert GPS coordinates to a human-readable place name.

    Uses Nominatim ``/reverse`` which is designed for coordinate lookup.
    Returns a single result with ``city``, ``lat``, and ``lon`` fields.
    """
    result = await reverse_geocode_query(lat, lon)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No place found for coordinates ({lat}, {lon})",
        )
    return result


# -----------------------------------------------------------------------
# GET /api/towers  (current tower data summary)
# -----------------------------------------------------------------------

@app.get("/api/towers")
def api_towers():
    """Return summary of loaded tower data."""
    towers_df = _get_towers()
    if towers_df.empty:
        return {"source": "none", "count": 0, "operators": {}, "zones": {}}

    real = load_real_towers()
    source = "opencellid" if real is not None and len(real) > 0 else "synthetic"

    ops = towers_df["operator"].value_counts().to_dict() if "operator" in towers_df.columns else {}
    zones = towers_df["zone"].value_counts().to_dict() if "zone" in towers_df.columns else {}

    result = {
        "source": source,
        "count": len(towers_df),
        "operators": ops,
        "zones": zones,
    }

    # Extra stats if real data
    if source == "opencellid" and real is not None:
        result["radio_types"] = real["radio"].value_counts().to_dict() if "radio" in real.columns else {}
        result["towers_with_signal"] = int((real["avg_signal_dbm"] != 0).sum()) if "avg_signal_dbm" in real.columns else 0

    return result


# -----------------------------------------------------------------------
# GET /api/towers/geo  (individual tower lat/lng for map rendering)
# -----------------------------------------------------------------------

@app.get("/api/towers/geo")
def api_towers_geo(
    max_towers: int = Query(300, ge=1, le=1000, description="Max individual towers to return"),
    operator: str = Query("all", max_length=20, description="Filter by operator (jio/airtel/vi/all)"),
):
    """Return individual tower positions for map rendering.

    Returns real lat/lng from OpenCelliD (or synthetic) data so the
    frontend can place tower icons at their actual geographic positions.
    """
    towers_df = _get_towers()
    if towers_df.empty:
        return {"towers": [], "count": 0}

    df = towers_df.copy()

    # Optional operator filter
    if operator.lower() != "all" and "operator" in df.columns:
        df = df[df["operator"].str.lower() == operator.lower()]

    # Sample down to max_towers keeping geographic spread (random with fixed seed)
    if len(df) > max_towers:
        df = df.sample(n=max_towers, random_state=42)

    # Return only the columns the map needs
    needed = ["tower_id", "lat", "lng", "operator", "signal_score", "zone"]
    available = [c for c in needed if c in df.columns]
    records = df[available].to_dict("records")

    # Ensure numeric types are plain Python floats/ints for JSON serialisation
    for r in records:
        r["lat"] = float(r["lat"])
        r["lng"] = float(r["lng"])
        r["signal_score"] = float(r.get("signal_score", 50))

    return {"towers": records, "count": len(records)}


# -----------------------------------------------------------------------
# PUT /model/refresh-towers  (fetch fresh data from OpenCelliD)
# -----------------------------------------------------------------------

class _RefreshRequest(BaseModel):
    max_per_zone: int = 50


@app.put("/model/refresh-towers")
def refresh_towers_endpoint(req: _RefreshRequest):
    """Fetch fresh real tower data from OpenCelliD API.

    This calls the OpenCelliD API for all 20 Bangalore zones and saves
    the result to towers_real.csv. Subsequent requests will use real data.
    Takes ~30-60 seconds depending on API response times.
    """
    df = refresh_towers(max_per_zone=req.max_per_zone)
    _invalidate_tower_cache()

    if len(df) == 0:
        return {"status": "error", "message": "No towers fetched", "count": 0}

    ops = df["operator"].value_counts().to_dict()
    radios = df["radio"].value_counts().to_dict()
    zones_count = df["zone"].nunique()
    with_signal = int((df["avg_signal_dbm"] != 0).sum())

    return {
        "status": "ok",
        "count": len(df),
        "zones_covered": zones_count,
        "operators": ops,
        "radio_types": radios,
        "towers_with_signal_data": with_signal,
        "message": f"Fetched {len(df)} real towers across {zones_count} zones",
    }


# =======================================================================
# RL ENDPOINTS  (PUT  --  /model/*)
# =======================================================================

# -----------------------------------------------------------------------
# PUT /model/auto-route  (RL-powered routing)
# -----------------------------------------------------------------------

@app.put("/model/auto-route", response_model=AutoRouteResponse)
def auto_route_endpoint(req: AutoRouteRequest):
    """RL-powered routing: auto-detect user intent from time + location patterns.

    Flow:
    1. Bandit checks if it has a learned pattern for this (user, time, origin, dest)
    2. If confident, auto-assigns the learned intent
    3. If not, falls back to manual intent or default "balanced"
    4. Routes are scored using the resolved preference
    """
    bandit = get_bandit(req.user_id)

    # Ask the bandit for an intent prediction
    rl_result = bandit.select(
        req.time_hour, req.day_of_week,
        req.origin.lat, req.origin.lng,
        req.destination.lat, req.destination.lng,
    )

    # Priority: user override > RL prediction > fallback
    if req.intent:
        intent = req.intent
        source = "user_override"
    elif rl_result["intent"]:
        intent = rl_result["intent"]
        source = "rl_learned"
    else:
        intent = "balanced"
        source = "default"

    # Resolve preference from intent
    pref_info = get_smart_preference(req.user_id, intent, req.time_hour)
    preference = pref_info["preference"]
    task_type = pref_info["task_type"]
    task_dur = pref_info["task_duration_min"]

    towers_df = _towers_to_df(req.towers)

    route_dicts = []
    for r in req.routes:
        route_dicts.append({
            "name": r.name,
            "eta": r.eta,
            "distance": r.distance,
            "path": [{"lat": c.lat, "lng": c.lng} for c in r.path],
            "zones": r.zones,
        })

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=preference, telecom=req.telecom,
        time_hour=req.time_hour, weather_factor=req.weather_factor,
        speed_kmh=req.speed_kmh,
    )

    route_results = []
    all_edge_cases: list[str] = []
    best_tf = None

    for r in ranked:
        conn = r.get("connectivity", {})
        bz_raw = detect_bad_zones(
            r["path"], conn.get("segment_signals", []),
            avg_speed_kmh=req.speed_kmh,
        )
        bz_models = [BadZone(**bz) for bz in bz_raw]
        segments = _build_segments(conn)
        edge_cases = _detect_edge_cases(conn, bz_models)
        all_edge_cases.extend(edge_cases)

        tf_raw = assess_task_feasibility(
            conn.get("segment_signals", []),
            task_type=task_type,
            task_duration_min=task_dur,
            avg_speed_kmh=req.speed_kmh,
            total_distance_km=r.get("distance", 10),
        )
        tf = TaskFeasibility(**tf_raw)
        if best_tf is None:
            best_tf = tf

        route_results.append(RouteResult(
            name=r["name"],
            eta=r["eta"],
            distance=r["distance"],
            signal_score=r.get("signal_score", 0),
            weighted_score=r.get("weighted_score", 0),
            zones=r.get("zones", []),
            path=[{"lat": p["lat"], "lng": p["lng"]} for p in r["path"]],
            rejected=r.get("rejected", False),
            connectivity=conn,
            bad_zones=bz_models,
            segments=segments,
            task_feasibility=tf,
        ))

    valid = [r for r in route_results if not r.rejected]
    rec_name = valid[0].name if valid else (
        route_results[0].name if route_results else "None"
    )
    rec_idx = next(
        (i for i, r in enumerate(route_results) if r.name == rec_name), 0
    )
    explanation = explain_recommendation(
        [r.model_dump() for r in route_results], rec_idx, preference,
    )
    for rr in route_results:
        if rr.name == rec_name:
            rr.explanation = explanation

    comparison = compare_routes_summary(
        [r.model_dump() for r in route_results]
    )

    rl_info = RLInfo(
        pattern_key=rl_result["pattern_key"],
        context=rl_result["context"],
        confidence=rl_result["confidence"],
        exploration_needed=rl_result["exploration_needed"],
        rl_selected_intent=rl_result["intent"],
        all_scores=rl_result.get("all_scores", {}),
    )

    return AutoRouteResponse(
        user_id=req.user_id,
        intent=intent,
        resolved_preference=preference,
        preference_source=source,
        task_type=task_type,
        task_duration_min=task_dur,
        intent_description=pref_info["description"],
        recommended_route=rec_name,
        explanation=explanation,
        routes=route_results,
        comparison=comparison,
        edge_cases_detected=list(set(all_edge_cases)),
        task_feasibility=best_tf,
        rl_info=rl_info,
    )


# -----------------------------------------------------------------------
# PUT /model/record-trip  (RL learning from completed trip)
# -----------------------------------------------------------------------

@app.put("/model/record-trip", response_model=RecordTripResponse)
def record_trip_endpoint(req: RecordTripRequest):
    """Record a completed trip for RL learning.

    Call this after the user completes a trip to update the bandit's
    distributions. Over time, the bandit learns each user's preferred
    intent for recurring (time, origin, destination) patterns.
    """
    bandit = get_bandit(req.user_id)
    result = bandit.update(
        req.time_hour, req.day_of_week,
        req.origin.lat, req.origin.lng,
        req.destination.lat, req.destination.lng,
        req.chosen_intent,
        req.recommended_intent or None,
    )
    return RecordTripResponse(
        recorded=True,
        user_id=req.user_id,
        pattern_key=result["pattern_key"],
        trip_count=result["trip_count"],
        context=result["context"],
    )


# -----------------------------------------------------------------------
# PUT /model/user-patterns  (view learned RL patterns)
# -----------------------------------------------------------------------

@app.put("/model/user-patterns", response_model=UserPatternsResponse)
def user_patterns_endpoint(req: UserPatternsRequest):
    """View all learned RL patterns for a user."""
    bandit = get_bandit(req.user_id)
    patterns = bandit.get_patterns()
    return UserPatternsResponse(
        user_id=req.user_id,
        trip_count=bandit.trip_count,
        patterns=[PatternInfo(**p) for p in patterns],
    )


# =======================================================================
# OFFLINE BUNDLE  (GET  --  /api/offline-bundle)
# =======================================================================

@app.get("/api/offline-bundle")
async def api_offline_bundle(
    source: str = Query("MIT"),
    destination: str = Query("Airport"),
    preference: float = Query(50),
    telecom: str = Query("all"),
):
    """Pre-computed bundle for offline navigation.

    Returns full route data, bad zone predictions, heatmap, and signal
    predictions that can be cached client-side for use without connectivity.
    """
    src, dst = await asyncio.gather(_resolve_location(source), _resolve_location(destination))
    route_dicts = await _generate_routes(src, dst)
    towers_df = _merge_route_towers(route_dicts)

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=preference, telecom=telecom if telecom != "multi" else "all",
        time_hour=12.0, weather_factor=1.0, speed_kmh=40.0,
        include_multi_sim=telecom.lower() == "multi",
    )

    routes_bundle = []
    for r in ranked:
        conn = r.get("connectivity", {})
        bad_zones = detect_bad_zones(
            r["path"],
            conn.get("segment_signals", []),
            avg_speed_kmh=40.0,
        )
        routes_bundle.append({
            "name": r["name"],
            "eta": r["eta"],
            "distance": r["distance"],
            "signal_score": r.get("signal_score", 0),
            "weighted_score": r.get("weighted_score", 0),
            "zones": r.get("zones", []),
            "path": r["path"],
            "rejected": r.get("rejected", False),
            "stability_score": r.get("stability_score", 50),
            "continuity_score": r.get("continuity_score", 50),
            "signal_variance": r.get("signal_variance", 0),
            "segment_signals": conn.get("segment_signals", []),
            "segment_colors": conn.get("segment_colors", []),
            "bad_zones": [
                {
                    "start_coord": bz["start_coord"],
                    "end_coord": bz["end_coord"],
                    "length_km": bz["length_km"],
                    "min_signal": bz["min_signal"],
                    "time_to_zone_min": bz["time_to_zone_min"],
                    "zone_duration_min": bz["zone_duration_min"],
                    "warning": bz["warning"],
                }
                for bz in bad_zones
            ],
        })

    # Heatmap snapshot
    heatmap = []
    for name, info in ZONES.items():
        lat, lng = info["center"]
        try:
            feats = extract_features(lat, lng, towers_df, 12.0, 1.0, 40.0)
            result = predict_single(feats)
            score = result["signal_strength"]
        except Exception:
            score = 50.0

        if score >= 70:
            strength, color = "strong", "#22c55e"
        elif score >= 40:
            strength, color = "moderate", "#eab308"
        else:
            strength, color = "weak", "#ef4444"

        heatmap.append({
            "name": name, "lat": lat, "lng": lng,
            "score": round(score, 1),
            "signal_strength": strength,
            "color": color,
        })

    import time as _time
    return {
        "source": source,
        "destination": destination,
        "generated_at": int(_time.time()),
        "routes": routes_bundle,
        "heatmap": heatmap,
        "offline": True,
    }


# =======================================================================
# Entry point
# =======================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
