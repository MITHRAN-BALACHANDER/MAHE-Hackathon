"""Generate synthetic tower placements and signal-measurement samples.

Ground truth is computed using COST-231 Hata + Ericsson 9999 ensemble
propagation models with shadow fading, rain attenuation, structure
penetration, and peak-hour congestion effects.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import numpy as np
import pandas as pd

from model.config import (
    DATA_DIR, ZONES, EDGE_ZONES, OPERATORS, FREQUENCY_BANDS_MHZ,
    LAT_RANGE, LNG_RANGE, SEED, EDGE_TYPE_TO_TERRAIN,
    MOBILE_HEIGHT_M, N_TOWERS, N_SAMPLES, SAMPLE_SPLIT,
    TERRAIN_TO_ENV, INPUT_DIM,
)
from model.utils import haversine_vec, haversine, detect_edge_zone, tower_load_factor
from model.propagation import (
    received_signal_dbm, dbm_to_quality, itu_structure_loss,
)


# ---------------------------------------------------------------------------
# Tower generation
# ---------------------------------------------------------------------------

# Frequency -> radio technology mapping for synthetic towers
_FREQ_TO_RADIO = {
    700: "LTE", 850: "GSM", 900: "GSM", 1800: "LTE",
    2100: "UMTS", 2300: "LTE", 3500: "NR",
}

# Density -> typical range_m and sample count ranges
_DENSITY_RANGES = {
    "high":   (300, 1500, 50, 500),    # (range_min, range_max, samp_min, samp_max)
    "medium": (800, 4000, 10, 200),
    "low":    (1500, 10000, 2, 50),
}


def generate_towers(seed: int = SEED) -> pd.DataFrame:
    """Place ~500 towers across Bangalore with realistic properties.

    High-density zones (MG Road, Koramangala, etc.): 6-10 towers per operator
    Medium-density zones: 3-6 per operator
    Low-density zones: 1-3 per operator
    Plus ~50 sparse inter-zone towers
    """
    rng = np.random.default_rng(seed)
    towers = []
    tid = 0
    density_range = {"high": (6, 10), "medium": (3, 6), "low": (1, 3)}

    for zone_name, info in ZONES.items():
        clat, clng = info["center"]
        r_km = info["radius_km"]
        lo, hi = density_range[info["density"]]

        for operator in OPERATORS:
            n = rng.integers(lo, hi + 1)
            for _ in range(n):
                # Gaussian offset around zone center
                lat = clat + rng.normal(0, r_km * 0.009 * 0.5)
                lng = clng + rng.normal(0, r_km * 0.009 * 0.5)

                # Realistic per-operator frequency allocation
                if operator == "Jio":
                    freq = int(rng.choice([850, 1800, 2300]))
                elif operator == "Airtel":
                    freq = int(rng.choice([900, 1800, 2100, 2300]))
                elif operator == "Vi":
                    freq = int(rng.choice([900, 1800, 2100]))
                else:  # BSNL
                    freq = int(rng.choice([700, 850, 2100]))

                height = rng.uniform(25, 55)
                tx_power = rng.uniform(40, 46)
                base_sig = {"high": 85, "medium": 65, "low": 50}[info["density"]]
                sig = float(np.clip(base_sig + rng.uniform(-12, 12), 20, 100))

                radio = _FREQ_TO_RADIO.get(freq, "LTE")
                rng_min, rng_max, smp_min, smp_max = _DENSITY_RANGES[info["density"]]
                range_m = int(rng.uniform(rng_min, rng_max))
                samples_count = int(rng.uniform(smp_min, smp_max))
                # Convert signal_score back to approximate dBm for avg_signal_dbm
                avg_dbm = int(-140 + sig / 100.0 * 96) if radio in ("LTE", "NR") else int(-110 + sig / 100.0 * 60)

                towers.append({
                    "tower_id": f"TWR_{tid:04d}",
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "operator": operator,
                    "signal_score": round(sig, 1),
                    "frequency_mhz": freq,
                    "tx_power_dbm": round(tx_power, 1),
                    "height_m": round(height, 1),
                    "zone": zone_name,
                    "radio": radio,
                    "range_m": range_m,
                    "samples": samples_count,
                    "avg_signal_dbm": avg_dbm,
                })
                tid += 1

    # Sparse random towers in inter-zone gaps
    n_sparse = max(50, N_TOWERS - tid)
    for _ in range(n_sparse):
        freq = int(rng.choice(FREQUENCY_BANDS_MHZ))
        sig_val = round(float(rng.uniform(35, 75)), 1)
        radio = _FREQ_TO_RADIO.get(freq, "LTE")
        avg_dbm = int(-140 + sig_val / 100.0 * 96) if radio in ("LTE", "NR") else int(-110 + sig_val / 100.0 * 60)
        towers.append({
            "tower_id": f"TWR_{tid:04d}",
            "lat": round(float(rng.uniform(*LAT_RANGE)), 6),
            "lng": round(float(rng.uniform(*LNG_RANGE)), 6),
            "operator": str(rng.choice(OPERATORS)),
            "signal_score": sig_val,
            "frequency_mhz": freq,
            "tx_power_dbm": round(float(rng.uniform(40, 46)), 1),
            "height_m": round(float(rng.uniform(25, 50)), 1),
            "zone": "Outer",
            "radio": radio,
            "range_m": int(rng.uniform(2000, 15000)),
            "samples": int(rng.uniform(1, 30)),
            "avg_signal_dbm": avg_dbm,
        })
        tid += 1

    return pd.DataFrame(towers)


# ---------------------------------------------------------------------------
# Dynamic road corridors derived from ZONES configuration
# ---------------------------------------------------------------------------

def _build_road_corridors(
    min_dist_km: float = 3.0,
    max_dist_km: float = 25.0,
    max_corridors: int = 15,
) -> list[tuple[float, float, float, float, str]]:
    """Build road corridor pairs dynamically from ZONES center coordinates.

    Pairs zone centers that are between *min_dist_km* and *max_dist_km* apart,
    then picks a diverse subset that spans Bangalore's major axes.

    Returns
    -------
    List of (start_lat, start_lng, end_lat, end_lng, name) tuples, same
    format as the old ROAD_CORRIDORS constant.
    """
    zone_list = [(name, info["center"], info["density"]) for name, info in ZONES.items()]

    # Collect all qualifying pairs with their distance
    candidates: list[tuple[float, float, float, float, str, float]] = []
    for i, (n1, (lat1, lng1), d1) in enumerate(zone_list):
        for n2, (lat2, lng2), d2 in zone_list[i + 1:]:
            dist = haversine(lat1, lng1, lat2, lng2)
            if min_dist_km <= dist <= max_dist_km:
                # Prefer pairs where at least one end is high-density
                priority = 0 if "high" in (d1, d2) else (1 if "medium" in (d1, d2) else 2)
                candidates.append((lat1, lng1, lat2, lng2, f"{n1} - {n2}", dist, priority))

    # Sort: high-density pairs first, then by distance (shorter first)
    candidates.sort(key=lambda c: (c[6], c[5]))

    # Greedy diversity selection: avoid using the same zone more than twice
    zone_usage: dict[str, int] = {}
    corridors: list[tuple[float, float, float, float, str]] = []
    for lat1, lng1, lat2, lng2, name, dist, _ in candidates:
        z1, z2 = name.split(" - ", 1)
        if zone_usage.get(z1, 0) >= 2 or zone_usage.get(z2, 0) >= 2:
            continue
        zone_usage[z1] = zone_usage.get(z1, 0) + 1
        zone_usage[z2] = zone_usage.get(z2, 0) + 1
        corridors.append((lat1, lng1, lat2, lng2, name))
        if len(corridors) >= max_corridors:
            break

    # Safety: always return at least a minimal set using first few zones
    if len(corridors) < 3:
        for i in range(min(3, len(zone_list) - 1)):
            n1, (lat1, lng1), _ = zone_list[i]
            n2, (lat2, lng2), _ = zone_list[i + 1]
            corridors.append((lat1, lng1, lat2, lng2, f"{n1} - {n2}"))

    return corridors


# Build once at module load time (uses only already-loaded ZONES dict, no I/O)
ROAD_CORRIDORS = _build_road_corridors()



# ---------------------------------------------------------------------------
# Physics-based ground truth computation
# ---------------------------------------------------------------------------

def compute_ground_truth(
    lat: float, lng: float,
    towers_df: pd.DataFrame,
    rng: np.random.Generator,
    time_hour: float,
    weather_factor: float,
    speed_kmh: float,
) -> tuple[float, float, float]:
    """Compute (signal_quality_0_100, drop_probability, handoff_risk).

    Uses the ensemble propagation model (COST-231 + Ericsson) with
    realistic corrections for weather, congestion, and edge zones.
    """
    t_lats = towers_df["lat"].values.astype(float)
    t_lngs = towers_df["lng"].values.astype(float)
    dists = haversine_vec(lat, lng, t_lats, t_lngs)

    if len(dists) == 0:
        return 0.0, 1.0, 0.0

    order = np.argsort(dists)
    nearest = order[0]
    d_near = dists[nearest]

    tx_power = towers_df["tx_power_dbm"].values[nearest]
    freq = towers_df["frequency_mhz"].values[nearest]
    height = towers_df["height_m"].values[nearest]

    # Determine propagation environment from nearest zone
    from model.utils import nearest_zone_environment
    env = nearest_zone_environment(lat, lng)

    # Rain rate from weather factor
    rain_rate = (1.0 - weather_factor) * 50.0  # 0 = 50 mm/h, 1 = 0 mm/h

    # Check edge zone
    _, _, edge_name, structure = detect_edge_zone(lat, lng)

    # Compute received signal using ensemble propagation model
    rx_dbm = received_signal_dbm(
        tx_power_dbm=tx_power,
        freq_mhz=freq,
        hb=height,
        hm=MOBILE_HEIGHT_M,
        dist_km=d_near,
        environment=env,
        city_size="large",
        structure_type=structure,
        rain_rate_mmh=rain_rate,
        rng=rng,
        sigma_db=8.0,
    )

    # Peak-hour congestion penalty
    load = tower_load_factor(time_hour)
    congestion_db = load * rng.uniform(2, 10)
    rx_dbm -= congestion_db

    # Convert to quality score
    signal = dbm_to_quality(rx_dbm)

    # --- Drop probability (physics-correlated) ---
    if signal < 10:
        drop = 0.90 + rng.uniform(-0.05, 0.05)
    elif signal < 20:
        drop = 0.65 + rng.uniform(-0.10, 0.10)
    elif signal < 35:
        drop = 0.35 + rng.uniform(-0.10, 0.10)
    elif signal < 55:
        drop = 0.12 + rng.uniform(-0.05, 0.05)
    elif signal < 75:
        drop = 0.04 + rng.uniform(-0.02, 0.02)
    else:
        drop = 0.01 + rng.uniform(-0.005, 0.01)
    drop = float(np.clip(drop, 0, 1))

    # --- Handoff risk (speed + tower geometry dependent) ---
    if len(order) >= 2:
        d_second = dists[order[1]]
        # Close towers at high speed = frequent handoffs
        ratio = d_near / max(d_second, 0.01)
        speed_factor = speed_kmh / 80.0
        raw = ratio * speed_factor
        handoff = float(1.0 / (1.0 + np.exp(-5 * (raw - 0.5))))
        handoff += rng.normal(0, 0.04)
    else:
        handoff = 0.0

    # Edge zones increase handoff risk
    if edge_name:
        handoff += 0.15

    handoff = float(np.clip(handoff, 0, 1))

    return signal, drop, handoff


# ---------------------------------------------------------------------------
# Sample generation
# ---------------------------------------------------------------------------

def generate_samples(towers_df: pd.DataFrame, n_samples: int = N_SAMPLES, seed: int = SEED):
    """Generate labelled signal-measurement samples with diverse spatial coverage."""
    rng = np.random.default_rng(seed + 1)
    from model.utils import extract_features

    records = []
    n_random = int(n_samples * SAMPLE_SPLIT["random"])
    n_roads = int(n_samples * SAMPLE_SPLIT["along_roads"])
    n_edge = int(n_samples * SAMPLE_SPLIT["edge_zones"])
    n_sparse = n_samples - n_random - n_roads - n_edge

    def _make_sample(lat, lng):
        t_h = float(rng.uniform(0, 24))
        w_f = float(rng.choice([1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.55]))
        spd = float(rng.uniform(5, 120))
        traf = float(rng.choice([0.0, 0.0, 0.0, 0.1, 0.3, 0.5, 0.7, 1.0]))
        feats = extract_features(lat, lng, towers_df, t_h, w_f, spd, traf)
        sig, drop, ho = compute_ground_truth(lat, lng, towers_df, rng, t_h, w_f, spd)
        return (*feats, sig / 100.0, drop, ho)

    # --- Random points across Bangalore ---
    print(f"  [gen] {n_random} random points ...")
    for _ in range(n_random):
        lat = float(rng.uniform(*LAT_RANGE))
        lng = float(rng.uniform(*LNG_RANGE))
        records.append(_make_sample(lat, lng))

    # --- Along-road corridor points ---
    print(f"  [gen] {n_roads} along-road points ...")
    per_road = n_roads // len(ROAD_CORRIDORS)
    for slat, slng, elat, elng, _ in ROAD_CORRIDORS:
        for _ in range(per_road):
            t = float(rng.uniform(0, 1))
            lat = slat + t * (elat - slat) + rng.normal(0, 0.001)
            lng = slng + t * (elng - slng) + rng.normal(0, 0.001)
            records.append(_make_sample(lat, lng))

    # --- Edge-zone points ---
    print(f"  [gen] {n_edge} edge-zone points ...")
    for _ in range(n_edge):
        ez = EDGE_ZONES[rng.integers(0, len(EDGE_ZONES))]
        lat = ez["center"][0] + rng.normal(0, ez["radius_km"] * 0.005)
        lng = ez["center"][1] + rng.normal(0, ez["radius_km"] * 0.005)
        records.append(_make_sample(lat, lng))

    # --- Sparse / low-density zone points ---
    print(f"  [gen] {n_sparse} sparse-zone points ...")
    sparse_zones = [z for z, v in ZONES.items() if v["density"] == "low"]
    for _ in range(n_sparse):
        zone_name = str(rng.choice(sparse_zones))
        zinfo = ZONES[zone_name]
        lat = zinfo["center"][0] + rng.normal(0, zinfo["radius_km"] * 0.012)
        lng = zinfo["center"][1] + rng.normal(0, zinfo["radius_km"] * 0.012)
        records.append(_make_sample(lat, lng))

    feat_cols = [f"f{i}" for i in range(INPUT_DIM)]
    label_cols = ["signal", "drop_prob", "handoff_risk"]
    df = pd.DataFrame(records, columns=feat_cols + label_cols)
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[generate] Creating towers ...")
    towers = generate_towers()
    towers_path = DATA_DIR / "towers.csv"
    towers.to_csv(towers_path, index=False)
    print(f"  -> {len(towers)} towers saved to {towers_path}")

    print("[generate] Saving edge zones ...")
    ez_path = DATA_DIR / "edge_zones.json"
    with open(ez_path, "w") as f:
        json.dump(EDGE_ZONES, f, indent=2)
    print(f"  -> {len(EDGE_ZONES)} edge zones saved to {ez_path}")

    print(f"[generate] Creating {N_SAMPLES:,} signal samples ...")
    samples = generate_samples(towers, n_samples=N_SAMPLES)
    samples_path = DATA_DIR / "samples.csv"
    samples.to_csv(samples_path, index=False)
    print(f"  -> {len(samples)} samples saved to {samples_path}")

    # Summary stats
    print("\n[generate] Data summary:")
    print(f"  Towers:  {len(towers)}")
    print(f"  Zones:   {towers['zone'].nunique()}")
    print(f"  Operators: {dict(towers['operator'].value_counts())}")
    print(f"  Samples: {len(samples)}")
    print(f"  Signal range:  {samples['signal'].min():.3f} - {samples['signal'].max():.3f}")
    print(f"  Drop range:    {samples['drop_prob'].min():.3f} - {samples['drop_prob'].max():.3f}")
    print(f"  Handoff range: {samples['handoff_risk'].min():.3f} - {samples['handoff_risk'].max():.3f}")
    print("[generate] Done.")


if __name__ == "__main__":
    main()
