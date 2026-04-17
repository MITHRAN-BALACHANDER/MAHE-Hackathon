"""Utility functions: haversine, feature extraction, edge-zone detection."""

import math
import numpy as np
import pandas as pd
from model.config import (
    EARTH_RADIUS_KM, EDGE_ZONES, EDGE_TYPE_TO_TERRAIN, ZONES,
    TERRAIN_CODE, TERRAIN_TO_ENV,
)


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in km between two (lat, lng) points."""
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def haversine_vec(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Vectorised haversine from one point to array of points (km)."""
    lat_r, lng_r = np.radians(lat), np.radians(lng)
    lats_r, lngs_r = np.radians(lats), np.radians(lngs)
    dlat = lats_r - lat_r
    dlng = lngs_r - lng_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_r) * np.cos(lats_r) * np.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ---------------------------------------------------------------------------
# Zone / terrain lookups
# ---------------------------------------------------------------------------

def nearest_zone_info(lat: float, lng: float) -> tuple[str, dict]:
    """Return (zone_name, zone_dict) of the nearest known zone."""
    best_dist = float("inf")
    best_name = "Unknown"
    best_info = list(ZONES.values())[0]
    for name, info in ZONES.items():
        d = haversine(lat, lng, info["center"][0], info["center"][1])
        if d < best_dist:
            best_dist = d
            best_name = name
            best_info = info
    return best_name, best_info


def nearest_zone_terrain(lat: float, lng: float) -> int:
    """Return the numeric terrain code of the nearest zone."""
    _, info = nearest_zone_info(lat, lng)
    return TERRAIN_CODE.get(info["terrain"], 0)


def nearest_zone_environment(lat: float, lng: float) -> str:
    """Return propagation environment string for nearest zone."""
    _, info = nearest_zone_info(lat, lng)
    return TERRAIN_TO_ENV.get(info["terrain"], "urban")


def detect_edge_zone(lat: float, lng: float):
    """Return (terrain_code, penalty_db, zone_name, structure_type) if inside an edge zone."""
    for zone in EDGE_ZONES:
        d = haversine(lat, lng, zone["center"][0], zone["center"][1])
        if d <= zone["radius_km"]:
            tc = EDGE_TYPE_TO_TERRAIN.get(zone["type"], 0)
            return tc, zone["penalty_db"], zone["name"], zone.get("structure", "concrete")
    return 0, 0.0, None, None


# ---------------------------------------------------------------------------
# Tower load / congestion
# ---------------------------------------------------------------------------

def tower_load_factor(hour: float) -> float:
    """Estimate tower congestion factor (0-1) based on hour of day."""
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        return 0.85   # peak
    if 10 < hour < 17:
        return 0.55   # business hours
    if 6 <= hour < 8:
        return 0.35   # early morning
    return 0.15       # night


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _safe_col(df: pd.DataFrame, col: str, default: float) -> np.ndarray:
    if col in df.columns:
        return df[col].values.astype(float)
    return np.full(len(df), default, dtype=float)


def extract_features(
    lat: float,
    lng: float,
    towers_df: pd.DataFrame,
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
) -> np.ndarray:
    """Extract a 17-dim feature vector for a single geographic point.

    Features
    --------
    0  dist_nearest_tower_km
    1  dist_2nd_nearest_km
    2  dist_3rd_nearest_km
    3  towers_within_500m
    4  towers_within_1km
    5  towers_within_2km
    6  avg_signal_nearby  (within 3 km, normalised 0-1)
    7  max_signal_nearby  (within 3 km, normalised 0-1)
    8  road_type          (terrain code / 6.0)
    9  terrain_type       (edge-zone code / 6.0)
    10 dominant_freq_norm (nearest tower freq / 3500)
    11 time_sin           (cyclic hour encoding)
    12 time_cos           (cyclic hour encoding)
    13 weather_factor     (1=clear, 0=worst)
    14 speed_norm         (speed / 120)
    15 nearest_signal     (nearest tower signal / 100)
    16 load_factor        (congestion proxy)
    """
    feats = np.zeros(17, dtype=np.float32)

    t_lats = towers_df["lat"].values.astype(float)
    t_lngs = towers_df["lng"].values.astype(float)
    dists = haversine_vec(lat, lng, t_lats, t_lngs)

    if len(dists) == 0:
        feats[:3] = 10.0
        return feats

    order = np.argsort(dists)
    sorted_d = dists[order]

    feats[0] = sorted_d[0]
    feats[1] = sorted_d[1] if len(sorted_d) > 1 else 10.0
    feats[2] = sorted_d[2] if len(sorted_d) > 2 else 10.0

    feats[3] = float(np.sum(dists < 0.5))
    feats[4] = float(np.sum(dists < 1.0))
    feats[5] = float(np.sum(dists < 2.0))

    sig_scores = _safe_col(towers_df, "signal_score", 70.0)
    nearby_mask = dists < 3.0
    if np.any(nearby_mask):
        feats[6] = np.mean(sig_scores[nearby_mask]) / 100.0
        feats[7] = np.max(sig_scores[nearby_mask]) / 100.0

    feats[8] = nearest_zone_terrain(lat, lng) / 6.0

    edge_terrain, _, _, _ = detect_edge_zone(lat, lng)
    feats[9] = edge_terrain / 6.0

    freqs = _safe_col(towers_df, "frequency_mhz", 1800.0)
    feats[10] = freqs[order[0]] / 3500.0

    feats[11] = np.sin(2 * np.pi * time_hour / 24.0)
    feats[12] = np.cos(2 * np.pi * time_hour / 24.0)
    feats[13] = float(weather_factor)
    feats[14] = min(speed_kmh / 120.0, 1.0)

    feats[15] = sig_scores[order[0]] / 100.0
    feats[16] = tower_load_factor(time_hour)

    return feats


def extract_features_batch(
    lats: np.ndarray,
    lngs: np.ndarray,
    towers_df: pd.DataFrame,
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
) -> np.ndarray:
    """Batch version -- returns (N, 17) array."""
    return np.stack([
        extract_features(float(la), float(lo), towers_df, time_hour, weather_factor, speed_kmh)
        for la, lo in zip(lats, lngs)
    ])


def segment_distances(path: list[dict]) -> np.ndarray:
    """Return array of haversine distances (km) between consecutive path points."""
    dists = []
    for i in range(len(path) - 1):
        d = haversine(path[i]["lat"], path[i]["lng"], path[i + 1]["lat"], path[i + 1]["lng"])
        dists.append(d)
    return np.array(dists) if dists else np.array([0.0])
