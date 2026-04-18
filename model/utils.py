"""Utility functions: haversine, feature extraction, edge-zone detection."""

import math
import numpy as np
import pandas as pd
from model.config import (
    EARTH_RADIUS_KM, EDGE_ZONES, EDGE_TYPE_TO_TERRAIN, ZONES,
    TERRAIN_CODE, TERRAIN_TO_ENV,
    RADIO_ENCODING, RANGE_NORMALIZATION, SAMPLE_COUNT_NORM,
    SPEED_NORMALIZATION,
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
    traffic_factor: float = 0.0,
) -> np.ndarray:
    """Extract a 22-dim feature vector for a single geographic point.

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
    -- real-time features --
    17 radio_generation   (nearest tower radio tech: GSM=0.2, UMTS=0.4, LTE=0.6, NR=0.8)
    18 nearest_range_norm (nearest tower coverage range / 50000)
    19 nearest_samples_norm (log(1+samples)/log(1001) of nearest tower)
    20 tower_tech_diversity (unique radio types within 2km / 5)
    21 traffic_factor     (route-level traffic congestion, 0=free, 1=heavy)
    """
    feats = np.zeros(22, dtype=np.float32)

    if towers_df.empty or "lat" not in towers_df.columns:
        feats[:3] = 10.0
        feats[8] = nearest_zone_terrain(lat, lng) / 6.0
        edge_terrain, _, _, _ = detect_edge_zone(lat, lng)
        feats[9] = edge_terrain / 6.0
        feats[11] = np.sin(2 * np.pi * time_hour / 24.0)
        feats[12] = np.cos(2 * np.pi * time_hour / 24.0)
        feats[13] = float(weather_factor)
        feats[14] = min(speed_kmh / 120.0, 1.0)
        feats[16] = tower_load_factor(time_hour)
        feats[21] = float(traffic_factor)
        return feats

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

    # --- Real-time features (17-21) ---
    # f17: radio generation of nearest tower
    radio_gen_map = RADIO_ENCODING
    radios = towers_df["radio"].values if "radio" in towers_df.columns else None
    if radios is not None:
        feats[17] = radio_gen_map.get(str(radios[order[0]]), 0.5)
    else:
        # Infer from frequency if radio column missing
        nearest_freq = freqs[order[0]]
        if nearest_freq <= 900:
            feats[17] = 0.2  # GSM
        elif nearest_freq <= 2100:
            feats[17] = 0.4  # UMTS
        elif nearest_freq <= 2300:
            feats[17] = 0.6  # LTE
        else:
            feats[17] = 0.8  # NR

    # f18: nearest tower coverage range (normalised)
    ranges = _safe_col(towers_df, "range_m", 2000.0)
    feats[18] = min(ranges[order[0]] / RANGE_NORMALIZATION, 1.0)

    # f19: nearest tower sample count (log-normalised data quality)
    samples = _safe_col(towers_df, "samples", 10.0)
    feats[19] = min(np.log1p(samples[order[0]]) / np.log1p(SAMPLE_COUNT_NORM), 1.0)

    # f20: tower technology diversity within 2km (unique radio types / 5)
    if radios is not None:
        mask_2km = dists < 2.0
        if np.any(mask_2km):
            unique_radios = len(set(str(r) for r in radios[mask_2km]))
            feats[20] = min(unique_radios / 5.0, 1.0)

    # f21: traffic congestion factor (from TomTom route data)
    feats[21] = float(np.clip(traffic_factor, 0.0, 1.0))

    # --- Data quality guards: clip all features to valid ranges ---
    feats[0:3] = np.clip(feats[0:3], 0.0, 50.0)     # distances (km)
    feats[3:6] = np.clip(feats[3:6], 0.0, 200.0)     # tower counts
    feats[6:8] = np.clip(feats[6:8], 0.0, 1.0)       # normalised signals
    feats[8:10] = np.clip(feats[8:10], 0.0, 1.0)     # terrain codes
    feats[10] = np.clip(feats[10], 0.0, 1.5)          # freq normalised
    feats[11:13] = np.clip(feats[11:13], -1.0, 1.0)  # sin/cos
    feats[13:16] = np.clip(feats[13:16], 0.0, 1.0)   # weather/speed/signal
    feats[16] = np.clip(feats[16], 0.0, 1.0)          # load factor
    feats[17] = np.clip(feats[17], 0.0, 1.0)          # radio gen
    feats[18:20] = np.clip(feats[18:20], 0.0, 1.0)   # range/samples
    feats[20] = np.clip(feats[20], 0.0, 1.0)          # diversity
    feats[21] = np.clip(feats[21], 0.0, 1.0)          # traffic

    # Replace NaN/inf with 0
    feats = np.nan_to_num(feats, nan=0.0, posinf=1.0, neginf=0.0)

    return feats


def extract_features_batch(
    lats: np.ndarray,
    lngs: np.ndarray,
    towers_df: pd.DataFrame,
    time_hour: float = 12.0,
    weather_factor: float = 1.0,
    speed_kmh: float = 40.0,
    traffic_factor: float = 0.0,
) -> np.ndarray:
    """Batch version -- returns (N, 22) array."""
    return np.stack([
        extract_features(float(la), float(lo), towers_df, time_hour, weather_factor, speed_kmh, traffic_factor)
        for la, lo in zip(lats, lngs)
    ])


def segment_distances(path: list[dict]) -> np.ndarray:
    """Return array of haversine distances (km) between consecutive path points."""
    dists = []
    for i in range(len(path) - 1):
        d = haversine(path[i]["lat"], path[i]["lng"], path[i + 1]["lat"], path[i + 1]["lng"])
        dists.append(d)
    return np.array(dists) if dists else np.array([0.0])
