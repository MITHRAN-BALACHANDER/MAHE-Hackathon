"""Score candidate routes using the trained model and preference slider."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from model.utils import extract_features, haversine, segment_distances
from model.inference import predict
from model.config import BAD_ZONE_THRESHOLD, MAX_ETA_RATIO, OPERATORS


def _ensure_towers_df(towers) -> pd.DataFrame:
    """Accept list-of-dicts or DataFrame, return standardised DataFrame."""
    if isinstance(towers, list):
        towers = pd.DataFrame(towers)
    df = towers.copy()
    # Fill optional columns with defaults
    if "signal_score" not in df.columns:
        df["signal_score"] = 70.0
    if "frequency_mhz" not in df.columns:
        df["frequency_mhz"] = 1800
    if "tx_power_dbm" not in df.columns:
        df["tx_power_dbm"] = 43.0
    if "height_m" not in df.columns:
        df["height_m"] = 30.0
    return df


def score_route(
    path: list[dict],
    towers,
    telecom: str = "all",
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
) -> dict:
    """Score a single route's connectivity using the trained model.

    Parameters
    ----------
    path : list of {"lat": float, "lng": float}
    towers : list[dict] | DataFrame  -- tower data
    telecom : carrier filter ("all", "Jio", "Airtel", "Vi", "BSNL")
    time_hour, weather_factor, speed_kmh : environment conditions

    Returns
    -------
    dict with per-segment and aggregate metrics
    """
    df = _ensure_towers_df(towers)
    if telecom.lower() != "all" and "operator" in df.columns:
        df = df[df["operator"].str.lower() == telecom.lower()]
        if df.empty:
            # Fall back to all towers if filter yields nothing
            df = _ensure_towers_df(towers)

    # Extract features for every path point
    feats = np.stack([
        extract_features(p["lat"], p["lng"], df, time_hour, weather_factor, speed_kmh)
        for p in path
    ])

    preds = predict(feats)
    seg_signal = preds["signal_strength"]      # (N,) 0-100
    seg_drop = preds["drop_probability"]       # (N,) 0-1
    seg_handoff = preds["handoff_risk"]        # (N,) 0-1

    # Segment distances
    seg_dists = segment_distances(path)  # (N-1,)

    # --- Aggregate metrics ---
    avg_connectivity = float(np.mean(seg_signal))
    min_connectivity = float(np.min(seg_signal))
    max_connectivity = float(np.max(seg_signal))
    drop_segments = int(np.sum(seg_signal < BAD_ZONE_THRESHOLD))

    # Continuity: low variance = more stable
    continuity_score = float(max(0, 100 - np.std(seg_signal) * 2.5))

    # Longest stable window (consecutive points with signal >= 50)
    longest_stable = 0
    current_stable = 0
    for s in seg_signal:
        if s >= 50:
            current_stable += 1
            longest_stable = max(longest_stable, current_stable)
        else:
            current_stable = 0

    # Average drop probability & handoff risk
    avg_drop_prob = float(np.mean(seg_drop))
    avg_handoff_risk = float(np.mean(seg_handoff))
    max_drop_prob = float(np.max(seg_drop))

    # Single-tower dependency risk: segments where towers_within_1km (feature[4]) <= 1
    single_tower_count = int(np.sum(feats[:, 4] <= 1.0))

    # Signal strength classification per segment
    seg_colors = []
    for s in seg_signal:
        if s >= 70:
            seg_colors.append("strong")
        elif s >= 40:
            seg_colors.append("medium")
        else:
            seg_colors.append("weak")

    # Signal variance (lower = more stable)
    signal_variance = float(np.var(seg_signal))

    # Stability score: combines continuity + longest stable window
    # longest_stable as fraction of total, weighted into 0-100
    stable_fraction = longest_stable / max(len(seg_signal), 1)
    stability_score = float(
        0.5 * continuity_score + 0.5 * (stable_fraction * 100)
    )

    return {
        "segment_signals": seg_signal.tolist(),
        "segment_drop_probs": seg_drop.tolist(),
        "segment_handoff_risks": seg_handoff.tolist(),
        "segment_colors": seg_colors,
        "avg_connectivity": round(avg_connectivity, 2),
        "min_connectivity": round(min_connectivity, 2),
        "max_connectivity": round(max_connectivity, 2),
        "drop_segments": drop_segments,
        "continuity_score": round(continuity_score, 2),
        "longest_stable_window": longest_stable,
        "signal_variance": round(signal_variance, 2),
        "stability_score": round(stability_score, 2),
        "avg_drop_probability": round(avg_drop_prob, 4),
        "max_drop_probability": round(max_drop_prob, 4),
        "avg_handoff_risk": round(avg_handoff_risk, 4),
        "single_tower_dependency_segments": single_tower_count,
        "total_segments": len(path),
    }


def score_route_multi_sim(
    path: list[dict],
    towers,
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
) -> dict:
    """Score a route across ALL carriers and pick best per segment.

    Returns per-carrier scores + a combined best-of-all score.
    """
    df = _ensure_towers_df(towers)
    available_ops = OPERATORS
    if "operator" in df.columns:
        available_ops = [
            op for op in OPERATORS
            if not df[df["operator"].str.lower() == op.lower()].empty
        ]
    if not available_ops:
        available_ops = OPERATORS

    per_carrier: dict[str, dict] = {}
    all_signals: list[list[float]] = []

    for op in available_ops:
        result = score_route(
            path, towers, telecom=op,
            time_hour=time_hour, weather_factor=weather_factor,
            speed_kmh=speed_kmh,
        )
        per_carrier[op] = {
            "avg_connectivity": result["avg_connectivity"],
            "continuity_score": result["continuity_score"],
            "stability_score": result["stability_score"],
            "drop_segments": result["drop_segments"],
            "signal_variance": result["signal_variance"],
        }
        all_signals.append(result["segment_signals"])

    # Best-of-all: for each segment, pick the best carrier's signal
    if all_signals:
        stacked = np.array(all_signals)  # (n_carriers, n_segments)
        best_per_segment = np.max(stacked, axis=0)
        best_carrier_idx = np.argmax(stacked, axis=0)
        best_carrier_names = [available_ops[i] for i in best_carrier_idx]

        combined_avg = float(np.mean(best_per_segment))
        combined_continuity = float(
            max(0, 100 - np.std(best_per_segment) * 2.5)
        )
        combined_variance = float(np.var(best_per_segment))
    else:
        combined_avg = 50.0
        combined_continuity = 50.0
        combined_variance = 0.0
        best_carrier_names = []

    # Recommend the best overall carrier
    best_carrier = max(
        per_carrier, key=lambda k: per_carrier[k]["avg_connectivity"]
    ) if per_carrier else "Unknown"

    return {
        "per_carrier": per_carrier,
        "best_carrier": best_carrier,
        "combined_avg_signal": round(combined_avg, 2),
        "combined_continuity": round(combined_continuity, 2),
        "combined_variance": round(combined_variance, 2),
        "best_carrier_per_segment": best_carrier_names,
    }


def rank_routes(
    routes: list[dict],
    towers,
    preference: float = 50.0,
    telecom: str = "all",
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
    max_eta_ratio: float = MAX_ETA_RATIO,
    include_multi_sim: bool = False,
) -> list[dict]:
    """Score and rank multiple routes.

    Parameters
    ----------
    routes : list of route dicts, each with at least "path", "eta", "distance", "name"
    preference : 0 = fastest, 100 = best connectivity
    telecom, time_hour, weather_factor, speed_kmh : conditions
    max_eta_ratio : hard constraint -- reject routes with ETA > fastest * ratio
    include_multi_sim : if True, compute per-carrier scoring

    Returns
    -------
    list of route dicts with added scoring fields, sorted best-first
    """
    signal_w = preference / 100.0
    time_w = 1.0 - signal_w

    # First pass: score connectivity for all routes
    conn_results = []
    multi_sim_results = []
    for route in routes:
        conn = score_route(
            route["path"], towers, telecom, time_hour, weather_factor, speed_kmh,
        )
        conn_results.append(conn)

        if include_multi_sim or telecom.lower() == "multi":
            msim = score_route_multi_sim(
                route["path"], towers, time_hour, weather_factor, speed_kmh,
            )
            multi_sim_results.append(msim)
        else:
            multi_sim_results.append(None)

    etas = [r["eta"] for r in routes]
    sigs = [c["avg_connectivity"] for c in conn_results]
    min_eta, max_eta = min(etas) if etas else 1, max(etas) if etas else 1
    min_sig, max_sig = min(sigs) if sigs else 0, max(sigs) if sigs else 1
    eta_range = max(max_eta - min_eta, 0.1)
    sig_range = max(max_sig - min_sig, 0.1)

    scored = []
    for route, conn, msim in zip(routes, conn_results, multi_sim_results):
        # Normalise both ETA and signal to 0-100 relative to the candidate set
        eta_norm = 100.0 * (1.0 - (route["eta"] - min_eta) / eta_range)
        sig_norm = 100.0 * ((conn["avg_connectivity"] - min_sig) / sig_range)

        # Stability bonus: up to +10 points for high stability
        stability_bonus = conn["stability_score"] / 100.0 * 10.0

        weighted = signal_w * sig_norm + time_w * eta_norm + stability_bonus * signal_w

        # Penalties
        if conn["drop_segments"] > 3:
            weighted -= 10
        if conn["max_drop_probability"] > 0.7:
            weighted -= 5
        if conn["single_tower_dependency_segments"] > len(route["path"]) * 0.4:
            weighted -= 5
        # Extra penalty for very low absolute signal
        if conn["avg_connectivity"] < BAD_ZONE_THRESHOLD:
            weighted -= 15
        # Penalty for high signal variance (unstable connection)
        if conn["signal_variance"] > 400:
            weighted -= 5

        # Hard reject: ETA too far above fastest
        rejected = route["eta"] > min_eta * max_eta_ratio

        entry = {
            **route,
            "signal_score": round(conn["avg_connectivity"], 2),
            "weighted_score": round(weighted, 2),
            "connectivity": conn,
            "rejected": rejected,
            "stability_score": conn["stability_score"],
            "continuity_score": conn["continuity_score"],
            "signal_variance": conn["signal_variance"],
            "longest_stable_window": conn["longest_stable_window"],
        }

        if msim is not None:
            entry["multi_sim"] = msim

        scored.append(entry)

    scored.sort(key=lambda r: (-1 if r["rejected"] else r["weighted_score"]), reverse=True)
    return scored
