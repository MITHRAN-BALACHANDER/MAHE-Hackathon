"""Multi-carrier dead zone predictor and call-drop avoidance engine.

Predicts weak network zones per carrier (Jio, Airtel, Vi, BSNL, eSIM)
for a specific time window.  Counts estimated call drops avoided by
choosing the recommended route, and emits a pre-download alert when an
upcoming dead zone is detected so the frontend can cache content.

Key features:
  - Time-aware: signal predictions shift by time-of-day (rush hour,
    night, etc.) using the trained ResidualSignalNet
  - Per-carrier: runs model inference with carrier-filtered towers for
    each operator individually
  - Dead zone classification: zones where ALL carriers score below 30
  - Call-drop estimation: P(drop) integrated over weak segments, compared
    between recommended and worst alternative
  - Offline cache alert: emitted when a dead zone is approaching within
    N minutes of travel at current speed
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from model.config import ZONES, OPERATORS, BAD_ZONE_THRESHOLD
from model.utils import extract_features, haversine
from model.inference import predict
from model.bad_zones import detect_bad_zones

_DEAD_ZONE_THRESHOLD = 30  # all-carrier dead zone
_OFFLINE_ALERT_AHEAD_MIN = 5.0  # alert this many minutes before dead zone


def predict_carrier_zones(
    path: list[dict],
    towers_df,
    time_hour: float,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
) -> dict:
    """Run signal prediction for every carrier along a route path.

    Returns per-carrier signal arrays + dead zone identification.
    """
    import pandas as pd

    if towers_df is None or towers_df.empty:
        return {"carriers": {}, "dead_zones": [], "best_carrier_per_point": []}

    available_ops = OPERATORS[:]
    if "operator" in towers_df.columns:
        available_ops = [
            op for op in OPERATORS
            if not towers_df[towers_df["operator"].str.lower() == op.lower()].empty
        ]
    if not available_ops:
        available_ops = OPERATORS[:]

    carrier_signals: dict[str, list[float]] = {}
    n = len(path)

    for op in available_ops:
        op_df = towers_df[towers_df["operator"].str.lower() == op.lower()] \
            if "operator" in towers_df.columns else towers_df
        if op_df.empty:
            op_df = towers_df

        feats = np.stack([
            extract_features(p["lat"], p["lng"], op_df, time_hour, weather_factor, speed_kmh)
            for p in path
        ])
        preds = predict(feats)
        carrier_signals[op] = preds["signal_strength"].tolist()

    # Per-point best carrier
    best_carrier_per_point = []
    for i in range(n):
        best_op = max(available_ops, key=lambda op: carrier_signals[op][i])
        best_carrier_per_point.append(best_op)

    # Dead zones: where ALL carriers are below threshold
    dead_zones = []
    i = 0
    cum_dist = [0.0]
    for j in range(1, n):
        d = haversine(path[j-1]["lat"], path[j-1]["lng"], path[j]["lat"], path[j]["lng"])
        cum_dist.append(cum_dist[-1] + d)

    speed_kpm = max(speed_kmh / 60.0, 0.1)

    while i < n:
        all_below = all(
            carrier_signals[op][i] < _DEAD_ZONE_THRESHOLD
            for op in available_ops
        )
        if all_below:
            start = i
            while i < n and all(
                carrier_signals[op][i] < _DEAD_ZONE_THRESHOLD
                for op in available_ops
            ):
                i += 1
            end = i - 1
            zone_start_km = cum_dist[start]
            zone_end_km = cum_dist[min(end, len(cum_dist) - 1)]
            zone_len = zone_end_km - zone_start_km
            time_to = zone_start_km / speed_kpm
            duration = max(zone_len / speed_kpm, 0.1)

            # Best signal even in the dead zone
            best_in_zone = max(
                max(carrier_signals[op][start:end+1]) for op in available_ops
            )

            # Find which zone name this falls under
            mid_idx = (start + end) // 2
            area = _nearest_zone_name(path[mid_idx]["lat"], path[mid_idx]["lng"])

            dead_zones.append({
                "start_coord": path[start],
                "end_coord": path[min(end, n-1)],
                "start_index": start,
                "end_index": end,
                "length_km": round(zone_len, 2),
                "time_to_zone_min": round(time_to, 1),
                "zone_duration_min": round(duration, 1),
                "best_signal_in_zone": round(best_in_zone, 1),
                "area": area,
                "carrier_signals": {
                    op: round(float(np.mean(carrier_signals[op][start:end+1])), 1)
                    for op in available_ops
                },
            })
        else:
            i += 1

    return {
        "carriers": {
            op: {
                "signals": carrier_signals[op],
                "avg": round(float(np.mean(carrier_signals[op])), 1),
                "min": round(float(np.min(carrier_signals[op])), 1),
                "weak_segments": int(sum(1 for s in carrier_signals[op] if s < BAD_ZONE_THRESHOLD)),
            }
            for op in available_ops
        },
        "dead_zones": dead_zones,
        "best_carrier_per_point": best_carrier_per_point,
    }


def estimate_call_drops_avoided(
    routes: list[dict],
) -> dict:
    """Estimate call drops the user avoids by taking the recommended route.

    Compares the recommended (first) route against all alternatives.
    A "call drop" event is counted wherever drop_probability > 0.5
    in a segment.
    """
    if not routes:
        return {"drops_avoided": 0, "recommended_drops": 0, "worst_drops": 0, "message": ""}

    def _count_drops(route: dict) -> int:
        conn = route.get("connectivity", {})
        probs = conn.get("segment_drop_probs", [])
        return sum(1 for p in probs if p > 0.5)

    rec_drops = _count_drops(routes[0])
    alt_drops = [_count_drops(r) for r in routes[1:]] if len(routes) > 1 else [rec_drops]
    worst = max(alt_drops) if alt_drops else rec_drops
    avoided = max(0, worst - rec_drops)

    if avoided > 0:
        msg = f"~{avoided} potential call drop(s) avoided by choosing this route"
    elif rec_drops == 0:
        msg = "No call drop risk on this route"
    else:
        msg = f"{rec_drops} weak segment(s) with potential call drop risk"

    return {
        "drops_avoided": avoided,
        "recommended_drops": rec_drops,
        "worst_alternative_drops": worst,
        "message": msg,
    }


def offline_cache_alerts(
    path: list[dict],
    segment_signals: list[float],
    speed_kmh: float = 40.0,
    ahead_minutes: float = _OFFLINE_ALERT_AHEAD_MIN,
) -> list[dict]:
    """Generate alerts to pre-download/cache content before entering a dead zone.

    Returns alerts for dead zones that the user will reach within
    `ahead_minutes` of travel.
    """
    bad = detect_bad_zones(path, segment_signals, avg_speed_kmh=speed_kmh,
                           threshold=_DEAD_ZONE_THRESHOLD)
    alerts = []
    for bz in bad:
        time_to = bz["time_to_zone_min"]
        if time_to <= ahead_minutes:
            duration = bz["zone_duration_min"]
            alerts.append({
                "type": "offline_cache",
                "time_to_zone_min": round(time_to, 1),
                "zone_duration_min": round(duration, 1),
                "length_km": bz["length_km"],
                "area": bz.get("edge_zone_name") or _nearest_zone_name(
                    bz["start_coord"]["lat"], bz["start_coord"]["lng"]
                ),
                "message": (
                    f"Network dead zone in ~{time_to:.0f} min "
                    f"(~{bz['length_km']:.1f} km, ~{duration:.1f} min). "
                    f"Cache maps and media now."
                ),
            })
    return alerts


def _nearest_zone_name(lat: float, lng: float) -> str:
    best, best_d = "Unknown", float("inf")
    for name, info in ZONES.items():
        d = haversine(lat, lng, info["center"][0], info["center"][1])
        if d < best_d:
            best, best_d = name, d
    return best
