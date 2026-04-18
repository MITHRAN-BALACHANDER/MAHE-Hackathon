"""FastAPI application -- all PUT endpoints for ngrok compatibility."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from model.schemas import (
    ScoreRoutesRequest, ScoreRoutesResponse,
    PredictSignalRequest, PredictSignalResponse,
    AnalyzeRouteRequest, AnalyzeRouteResponse,
    DetectZonesRequest, DetectZonesResponse,
    HealthResponse, RouteResult, SegmentDetail, BadZone, TaskFeasibility,
    SmartRouteRequest, SmartRouteResponse,
    RecordChoiceRequest, RecordChoiceResponse,
    ResolveIntentRequest, ResolveIntentResponse,
)
from model.scoring import score_route, rank_routes
from model.bad_zones import detect_bad_zones, assess_task_feasibility
from model.explainability import (
    explain_recommendation, explain_bad_zones, compare_routes_summary,
)
from model.smart_preference import (
    resolve_intent, get_smart_preference, record_choice, _load_profiles,
)
from model.utils import extract_features, detect_edge_zone
from model.inference import predict_single
from model.config import WEIGHTS_PATH, DATA_DIR, EDGE_ZONES

app = FastAPI(
    title="SignalRoute Model API",
    description="Connectivity-aware routing model for L4 vehicles -- all PUT endpoints",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        os.environ.get("CORS_ORIGIN", ""),
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _towers_to_df(towers) -> pd.DataFrame:
    """Convert list of TowerInput pydantic models to DataFrame."""
    records = [t.model_dump() for t in towers]
    return pd.DataFrame(records)


def _route_to_path(route) -> list[dict]:
    return [{"lat": c.lat, "lng": c.lng} for c in route.path]


def _build_segments(conn: dict) -> list[SegmentDetail]:
    sigs = conn.get("segment_signals", [])
    drops = conn.get("segment_drop_probs", [])
    hos = conn.get("segment_handoff_risks", [])
    colors = conn.get("segment_colors", [])
    return [
        SegmentDetail(
            signal_strength=round(sigs[i], 2),
            drop_probability=round(drops[i], 4),
            handoff_risk=round(hos[i], 4),
            color=colors[i] if i < len(colors) else "medium",
        )
        for i in range(len(sigs))
    ]


def _detect_edge_cases(conn: dict, bad_zones_list: list) -> list[str]:
    """Identify edge cases present in the route analysis."""
    cases = []
    if conn.get("single_tower_dependency_segments", 0) > 0:
        cases.append(
            f"Single-tower dependency on {conn['single_tower_dependency_segments']} segment(s) "
            "-- if that tower fails, signal is lost"
        )
    if conn.get("avg_handoff_risk", 0) > 0.4:
        cases.append("High handoff risk -- frequent tower switching expected at this speed")
    if conn.get("continuity_score", 100) < 50:
        cases.append("Low continuity -- signal fluctuates significantly along the route")
    for bz in bad_zones_list:
        if bz.edge_zone_name:
            cases.append(f"Edge zone: {bz.edge_zone_name} ({bz.reason})")
    return cases


# -----------------------------------------------------------------------
# PUT /model/score-routes
# -----------------------------------------------------------------------

@app.put("/model/score-routes", response_model=ScoreRoutesResponse)
def score_routes_endpoint(req: ScoreRoutesRequest):
    towers_df = _towers_to_df(req.towers)

    # Build route dicts for scoring engine
    route_dicts = []
    for r in req.routes:
        route_dicts.append({
            "name": r.name,
            "eta": r.eta,
            "distance": r.distance,
            "path": _route_to_path(r),
            "zones": r.zones,
        })

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=req.preference,
        telecom=req.telecom,
        time_hour=req.time_hour,
        weather_factor=req.weather_factor,
        speed_kmh=req.speed_kmh,
    )

    # Build response for each route
    route_results = []
    all_edge_cases = []
    for r in ranked:
        conn = r.get("connectivity", {})

        # Bad zones
        bz_raw = detect_bad_zones(
            r["path"], conn.get("segment_signals", []),
            avg_speed_kmh=req.speed_kmh,
        )
        bz_models = [BadZone(**bz) for bz in bz_raw]

        segments = _build_segments(conn)
        edge_cases = _detect_edge_cases(conn, bz_models)
        all_edge_cases.extend(edge_cases)

        # Task feasibility (default: call)
        tf_raw = assess_task_feasibility(
            conn.get("segment_signals", []),
            task_type="call",
            task_duration_min=10.0,
            avg_speed_kmh=req.speed_kmh,
            total_distance_km=r.get("distance", 10),
        )
        tf = TaskFeasibility(**tf_raw)

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

    # Recommendation
    valid = [r for r in route_results if not r.rejected]
    rec_name = valid[0].name if valid else (route_results[0].name if route_results else "None")
    rec_idx = next((i for i, r in enumerate(route_results) if r.name == rec_name), 0)
    explanation = explain_recommendation(
        [r.model_dump() for r in route_results], rec_idx, req.preference,
    )

    for i, rr in enumerate(route_results):
        if rr.name == rec_name:
            rr.explanation = explanation

    comparison = compare_routes_summary([r.model_dump() for r in route_results])

    return ScoreRoutesResponse(
        preference=req.preference,
        telecom=req.telecom,
        recommended_route=rec_name,
        explanation=explanation,
        routes=route_results,
        comparison=comparison,
        edge_cases_detected=list(set(all_edge_cases)),
    )


# -----------------------------------------------------------------------
# PUT /model/predict-signal
# -----------------------------------------------------------------------

@app.put("/model/predict-signal", response_model=PredictSignalResponse)
def predict_signal_endpoint(req: PredictSignalRequest):
    towers_df = _towers_to_df(req.towers)
    if req.telecom.lower() != "all" and "operator" in towers_df.columns:
        filtered = towers_df[towers_df["operator"].str.lower() == req.telecom.lower()]
        if not filtered.empty:
            towers_df = filtered

    feats = extract_features(
        req.lat, req.lng, towers_df,
        req.time_hour, req.weather_factor, req.speed_kmh,
    )
    result = predict_single(feats)

    _, _, edge_name, _ = detect_edge_zone(req.lat, req.lng)
    nearby = int(feats[5])  # towers_within_2km

    sig = result["signal_strength"]
    if sig >= 70:
        conf = "high"
    elif sig >= 40:
        conf = "medium"
    else:
        conf = "low"

    return PredictSignalResponse(
        lat=req.lat,
        lng=req.lng,
        signal_strength=round(sig, 2),
        drop_probability=round(result["drop_probability"], 4),
        handoff_risk=round(result["handoff_risk"], 4),
        edge_zone=edge_name,
        nearby_towers=nearby,
        confidence=conf,
    )


# -----------------------------------------------------------------------
# PUT /model/analyze-route
# -----------------------------------------------------------------------

@app.put("/model/analyze-route", response_model=AnalyzeRouteResponse)
def analyze_route_endpoint(req: AnalyzeRouteRequest):
    towers_df = _towers_to_df(req.towers)
    path = _route_to_path(req.route)

    conn = score_route(
        path, towers_df, req.telecom,
        req.time_hour, req.weather_factor, req.speed_kmh,
    )

    bz_raw = detect_bad_zones(
        path, conn.get("segment_signals", []),
        avg_speed_kmh=req.speed_kmh,
    )
    bz_models = [BadZone(**bz) for bz in bz_raw]
    segments = _build_segments(conn)

    tf_raw = assess_task_feasibility(
        conn.get("segment_signals", []),
        task_type=req.task_type,
        task_duration_min=req.task_duration_min,
        avg_speed_kmh=req.speed_kmh,
        total_distance_km=req.route.distance,
    )

    edge_cases = _detect_edge_cases(conn, bz_models)

    return AnalyzeRouteResponse(
        name=req.route.name,
        connectivity=conn,
        bad_zones=bz_models,
        segments=segments,
        task_feasibility=TaskFeasibility(**tf_raw),
        edge_cases_detected=edge_cases,
    )


# -----------------------------------------------------------------------
# PUT /model/detect-zones
# -----------------------------------------------------------------------

@app.put("/model/detect-zones", response_model=DetectZonesResponse)
def detect_zones_endpoint(req: DetectZonesRequest):
    towers_df = _towers_to_df(req.towers)
    path = _route_to_path(req.route)

    conn = score_route(
        path, towers_df, req.telecom,
        req.time_hour, req.weather_factor, req.speed_kmh,
    )

    bz_raw = detect_bad_zones(
        path, conn.get("segment_signals", []),
        avg_speed_kmh=req.speed_kmh,
    )
    bz_models = [BadZone(**bz) for bz in bz_raw]
    warnings = explain_bad_zones(bz_raw)

    total_km = sum(bz.length_km for bz in bz_models)
    total_min = sum(bz.zone_duration_min for bz in bz_models)

    return DetectZonesResponse(
        bad_zones=bz_models,
        total_bad_zone_km=round(total_km, 2),
        total_bad_zone_min=round(total_min, 1),
        warnings=warnings,
    )


# -----------------------------------------------------------------------
# PUT /model/health
# -----------------------------------------------------------------------

@app.put("/model/health", response_model=HealthResponse)
def health_endpoint():
    model_ok = WEIGHTS_PATH.exists()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    towers_csv = DATA_DIR / "towers.csv"
    samples_csv = DATA_DIR / "samples.csv"
    n_towers = len(pd.read_csv(towers_csv)) if towers_csv.exists() else 0
    n_samples = len(pd.read_csv(samples_csv)) if samples_csv.exists() else 0

    return HealthResponse(
        status="ok" if model_ok else "model_not_trained",
        model_loaded=model_ok,
        device=device,
        towers_in_training=n_towers,
        samples_in_training=n_samples,
    )


# -----------------------------------------------------------------------
# PUT /model/smart-route  (intent-driven routing)
# -----------------------------------------------------------------------

@app.put("/model/smart-route", response_model=SmartRouteResponse)
def smart_route_endpoint(req: SmartRouteRequest):
    """Score routes using user intent instead of manual preference slider.

    The user says what they need ("meeting", "fastest", "call", etc.) and
    the system auto-resolves the right preference.  If the user has enough
    history, learned preferences override defaults.
    """
    # Resolve intent -> preference
    pref_info = get_smart_preference(req.user_id, req.intent, req.time_hour)
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
            "path": _route_to_path(r),
            "zones": r.zones,
        })

    ranked = rank_routes(
        route_dicts, towers_df,
        preference=preference,
        telecom=req.telecom,
        time_hour=req.time_hour,
        weather_factor=req.weather_factor,
        speed_kmh=req.speed_kmh,
    )

    route_results = []
    all_edge_cases = []
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
    rec_name = valid[0].name if valid else (route_results[0].name if route_results else "None")
    rec_idx = next((i for i, r in enumerate(route_results) if r.name == rec_name), 0)
    explanation = explain_recommendation(
        [r.model_dump() for r in route_results], rec_idx, preference,
    )

    for rr in route_results:
        if rr.name == rec_name:
            rr.explanation = explanation

    comparison = compare_routes_summary([r.model_dump() for r in route_results])

    return SmartRouteResponse(
        user_id=req.user_id,
        intent=pref_info["intent"],
        resolved_preference=preference,
        preference_source=pref_info["source"],
        task_type=task_type,
        task_duration_min=task_dur,
        intent_description=pref_info["description"],
        recommended_route=rec_name,
        explanation=explanation,
        routes=route_results,
        comparison=comparison,
        edge_cases_detected=list(set(all_edge_cases)),
        task_feasibility=best_tf,
    )


# -----------------------------------------------------------------------
# PUT /model/record-choice  (learn from user selection)
# -----------------------------------------------------------------------

@app.put("/model/record-choice", response_model=RecordChoiceResponse)
def record_choice_endpoint(req: RecordChoiceRequest):
    """Record what route the user actually chose, so the system learns."""
    record_choice(
        user_id=req.user_id,
        intent=req.intent,
        preference_used=req.preference_used,
        time_hour=req.time_hour,
        chosen_route_name=req.chosen_route_name,
        chosen_signal_score=req.chosen_signal_score,
        chosen_eta=req.chosen_eta,
    )
    profiles = _load_profiles()
    total = len(profiles.get(req.user_id, {}).get("choices", []))
    return RecordChoiceResponse(
        recorded=True,
        user_id=req.user_id,
        total_choices=total,
    )


# -----------------------------------------------------------------------
# PUT /model/resolve-intent  (preview intent -> preference mapping)
# -----------------------------------------------------------------------

@app.put("/model/resolve-intent", response_model=ResolveIntentResponse)
def resolve_intent_endpoint(req: ResolveIntentRequest):
    """Preview what preference an intent maps to for a given user."""
    result = get_smart_preference(req.user_id, req.intent, req.time_hour)
    return ResolveIntentResponse(
        intent=result["intent"],
        preference=result["preference"],
        task_type=result["task_type"],
        task_duration_min=result["task_duration_min"],
        description=result["description"],
        source=result["source"],
        total_choices=result.get("total_choices", 0),
    )
