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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from fastapi import FastAPI, Query
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
from model.schemas import (
    AutoRouteRequest, AutoRouteResponse,
    RecordTripRequest, RecordTripResponse,
    UserPatternsRequest, UserPatternsResponse,
    RouteResult, BadZone, TaskFeasibility,
    RLInfo, PatternInfo,
)

# Update app metadata for the full backend
app.title = "SignalRoute Backend"
app.description = "Cellular network-aware routing with reinforcement learning"
app.version = "2.0.0"


# -----------------------------------------------------------------------
# Location lookup for Bangalore
# -----------------------------------------------------------------------

LOCATIONS: dict[str, tuple[float, float]] = {
    "mit":               (12.9172, 77.6225),
    "mit mahe":          (12.9172, 77.6225),
    "silk board":        (12.9172, 77.6225),
    "airport":           (13.1986, 77.7066),
    "kempegowda airport":(13.1986, 77.7066),
    "mg road":           (12.9716, 77.5946),
    "majestic":          (12.9766, 77.5713),
    "koramangala":       (12.9279, 77.6271),
    "indiranagar":       (12.9784, 77.6408),
    "jayanagar":         (12.9250, 77.5840),
    "whitefield":        (12.9698, 77.7499),
    "electronic city":   (12.8399, 77.6670),
    "hsr layout":        (12.9116, 77.6389),
    "btm layout":        (12.9166, 77.6101),
    "marathahalli":      (12.9591, 77.6974),
    "hebbal":            (13.0358, 77.5970),
    "kr puram":          (12.9956, 77.6969),
    "yelahanka":         (13.1007, 77.5963),
    "bannerghatta":      (12.8010, 77.5775),
    "sarjapur road":     (12.9100, 77.6800),
    "rajajinagar":       (12.9910, 77.5550),
    "peenya":            (13.0290, 77.5180),
    "hosur road":        (12.8700, 77.6400),
}


def _resolve_location(name: str) -> tuple[float, float]:
    """Resolve a place name to (lat, lng). Falls back to zone lookup."""
    key = name.lower().strip()
    if key in LOCATIONS:
        return LOCATIONS[key]
    for zone_name, info in ZONES.items():
        if key in zone_name.lower():
            return info["center"]
    return (12.9172, 77.6225)  # default: Silk Board


# -----------------------------------------------------------------------
# Tower data cache
# -----------------------------------------------------------------------

_cached_towers: pd.DataFrame | None = None


def _get_towers() -> pd.DataFrame:
    """Load trained tower data (cached)."""
    global _cached_towers
    if _cached_towers is not None:
        return _cached_towers
    towers_path = DATA_DIR / "towers.csv"
    if towers_path.exists():
        _cached_towers = pd.read_csv(towers_path)
    else:
        _cached_towers = pd.DataFrame()
    return _cached_towers


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


def _generate_routes(
    src: tuple[float, float], dst: tuple[float, float],
) -> list[dict]:
    """Generate 3 route variants (fastest, balanced, best-signal)."""
    total_dist = haversine(src[0], src[1], dst[0], dst[1])

    # Find zones roughly between source and destination
    candidates = []
    for name, info in ZONES.items():
        c = info["center"]
        d_src = haversine(src[0], src[1], c[0], c[1])
        d_dst = haversine(dst[0], dst[1], c[0], c[1])
        if d_src + d_dst < total_dist * 2.5 and d_src > 0.3 and d_dst > 0.3:
            candidates.append((name, c, d_src, info["density"]))
    candidates.sort(key=lambda x: x[2])

    routes = []

    # Fastest Route: most direct (1-2 waypoints)
    fast_via = [c[1] for c in candidates[:2]]
    fast_dist = total_dist * 1.1
    routes.append({
        "name": "Fastest Route",
        "eta": round(fast_dist / 40 * 60, 1),
        "distance": round(fast_dist, 1),
        "path": _build_path(src, dst, fast_via, 3),
        "zones": [c[0] for c in candidates[:2]],
    })

    # Balanced Route: moderate path (2-4 waypoints)
    bal_via = [c[1] for c in candidates[:4]]
    bal_dist = total_dist * 1.25
    routes.append({
        "name": "Balanced Route",
        "eta": round(bal_dist / 35 * 60, 1),
        "distance": round(bal_dist, 1),
        "path": _build_path(src, dst, bal_via, 4),
        "zones": [c[0] for c in candidates[:4]],
    })

    # Best Signal Route: prefer high-density zones
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

    return routes


# =======================================================================
# FRONTEND ENDPOINTS  (GET / POST  --  /api/*)
# =======================================================================

# -----------------------------------------------------------------------
# GET /api/routes
# -----------------------------------------------------------------------

@app.get("/api/routes")
def api_routes(
    source: str = Query("MIT"),
    destination: str = Query("Airport"),
    preference: float = Query(50),
    telecom: str = Query("all"),
):
    """Score routes between two named locations."""
    src = _resolve_location(source)
    dst = _resolve_location(destination)
    towers_df = _get_towers()
    route_dicts = _generate_routes(src, dst)

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=preference, telecom=telecom,
        time_hour=12.0, weather_factor=1.0, speed_kmh=40.0,
    )

    results = []
    for r in ranked:
        results.append({
            "name": r["name"],
            "eta": r["eta"],
            "distance": r["distance"],
            "signal_score": r.get("signal_score", 0),
            "weighted_score": r.get("weighted_score", 0),
            "zones": r.get("zones", []),
            "path": r["path"],
        })

    rec = results[0]["name"] if results else "None"
    return {
        "source": source,
        "destination": destination,
        "preference": preference,
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
    zone: str = Query("Electronic City"),
    minutes: int = Query(15),
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
def api_reroute(body: _RerouteBody):
    """Reroute with bias toward better signal."""
    src = _resolve_location(body.source)
    dst = _resolve_location(body.destination)
    towers_df = _get_towers()

    route_dicts = _generate_routes(src, dst)
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
# Entry point
# =======================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
