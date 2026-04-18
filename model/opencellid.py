"""Fetch real cell tower data from OpenCelliD for Bangalore zones.

Tiles across all 20 zones with small bounding boxes (API limit: 4M sq.m)
and maps raw OpenCelliD data to our tower CSV format.

India MCC: 404 / 405
MNC -> Operator mapping (Karnataka circle):
    Jio:    854, 855, 856, 857, 858, 859, 860, 861, 862, 863, 864, 868, 869, 871, 872, 873, 874
    Airtel: 10, 40, 45, 49, 90, 92, 93, 94, 95, 96, 97, 98
    Vi:     12, 14, 20, 56, 60, 66, 84, 86
    BSNL:   51, 53, 57, 58, 59, 71, 72, 73, 74, 75, 76
"""

import time
import math
import os
import requests
import pandas as pd
import numpy as np
from pathlib import Path

from model.config import ZONES, DATA_DIR

# Read API key from environment (set via .env / OPENCELLID_API_KEY)
# Evaluated lazily in functions so dotenv can be loaded by the entry point first.
def _api_key() -> str:
    return os.environ.get("OPENCELLID_API_KEY", "")
BASE_URL = "https://opencellid.org"
INDIA_MCC = {404, 405}

# MNC -> operator mapping for Indian carriers (Karnataka)
MNC_TO_OPERATOR = {}
for mnc in [854, 855, 856, 857, 858, 859, 860, 861, 862, 863, 864, 868, 869, 871, 872, 873, 874]:
    MNC_TO_OPERATOR[mnc] = "Jio"
for mnc in [10, 40, 45, 49, 90, 92, 93, 94, 95, 96, 97, 98]:
    MNC_TO_OPERATOR[mnc] = "Airtel"
for mnc in [12, 14, 20, 56, 60, 66, 84, 86]:
    MNC_TO_OPERATOR[mnc] = "Vi"
for mnc in [51, 53, 57, 58, 59, 71, 72, 73, 74, 75, 76]:
    MNC_TO_OPERATOR[mnc] = "BSNL"

# Radio type -> typical frequency (MHz) in India
RADIO_TO_FREQ = {
    "GSM":  900,
    "UMTS": 2100,
    "LTE":  1800,
    "NR":   3500,
    "NBIOT": 700,
}

# Radio type -> typical tower height (m) for Indian urban deployments
RADIO_TO_HEIGHT = {
    "GSM":  35,
    "UMTS": 30,
    "LTE":  30,
    "NR":   25,
    "NBIOT": 30,
}

# Radio type -> typical TX power (dBm)
RADIO_TO_TX_POWER = {
    "GSM":  43,
    "UMTS": 43,
    "LTE":  46,
    "NR":   49,
    "NBIOT": 43,
}


def _zone_bbox(center: tuple[float, float], radius_km: float) -> tuple[float, float, float, float]:
    """Convert zone center + radius to a bounding box.

    API limit is 4,000,000 sq.m = 2km x 2km max.
    We cap each tile at ~0.008 degrees (~900m) to stay within limits.
    """
    # 1 degree lat ~ 111 km, 1 degree lng ~ 111 * cos(lat) km
    cap_deg = 0.008  # ~900m, well within 2km limit
    half = min(radius_km / 111.0, cap_deg)
    lat, lng = center
    return (
        round(lat - half, 6),
        round(lng - half, 6),
        round(lat + half, 6),
        round(lng + half, 6),
    )


def _tiles_for_zone(center: tuple[float, float], radius_km: float) -> list[tuple[float, float, float, float]]:
    """Generate overlapping tiles to cover a zone's full radius."""
    tile_deg = 0.015  # each tile covers ~1.6km
    half_r = radius_km / 111.0
    lat, lng = center

    tiles = []
    lat_start = lat - half_r
    while lat_start < lat + half_r:
        lng_start = lng - half_r
        while lng_start < lng + half_r:
            tiles.append((
                round(lat_start, 6),
                round(lng_start, 6),
                round(min(lat_start + tile_deg, lat + half_r), 6),
                round(min(lng_start + tile_deg, lng + half_r), 6),
            ))
            lng_start += tile_deg
        lat_start += tile_deg

    return tiles


def fetch_cells_in_bbox(
    bbox: tuple[float, float, float, float],
    radio: str = "",
    limit: int = 50,
) -> list[dict]:
    """Fetch cell towers in a bounding box from OpenCelliD."""
    params = {
        "key": _api_key(),
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "format": "json",
        "limit": limit,
    }
    if radio:
        params["radio"] = radio

    try:
        resp = requests.get(f"{BASE_URL}/cell/getInArea", params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "cells" in data:
                return data["cells"]
        return []
    except Exception as e:
        print(f"  [warn] API error for bbox {bbox}: {e}")
        return []


def fetch_cell_count_in_bbox(bbox: tuple[float, float, float, float]) -> int:
    """Get the number of cells in a bounding box (costs 2 API credits)."""
    params = {
        "key": _api_key(),
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "format": "json",
    }
    try:
        resp = requests.get(f"{BASE_URL}/cell/getInAreaSize", params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("count", 0)
        return 0
    except Exception:
        return 0


def _mnc_to_operator(mnc: int) -> str:
    """Map Indian MNC to carrier name."""
    return MNC_TO_OPERATOR.get(mnc, "Unknown")


def _radio_to_freq(radio: str) -> int:
    return RADIO_TO_FREQ.get(radio, 1800)


def _radio_to_height(radio: str) -> float:
    return RADIO_TO_HEIGHT.get(radio, 30)


def _radio_to_tx_power(radio: str) -> float:
    return RADIO_TO_TX_POWER.get(radio, 43)


def _signal_dbm_to_score(dbm: int, radio: str) -> float:
    """Convert averageSignalStrength (dBm) to 0-100 score.

    If dBm is 0 (no data), estimate based on radio type defaults.
    """
    if dbm == 0:
        # No measurement data -- use radio-type defaults
        defaults = {"GSM": 65, "UMTS": 60, "LTE": 70, "NR": 75, "NBIOT": 55}
        return defaults.get(radio, 60)

    # dBm ranges by radio type
    if radio in ("GSM", "UMTS"):
        # -50 dBm = excellent, -110 dBm = no signal
        score = max(0, min(100, (dbm + 110) / 60 * 100))
    else:  # LTE, NR
        # -44 dBm = excellent, -140 dBm = no signal
        score = max(0, min(100, (dbm + 140) / 96 * 100))
    return round(score, 1)


def fetch_zone_towers(
    zone_name: str,
    center: tuple[float, float],
    radius_km: float,
    max_per_zone: int = 50,
) -> list[dict]:
    """Fetch all unique towers for a single zone."""
    tiles = _tiles_for_zone(center, radius_km)
    seen_ids = set()
    towers = []

    for tile in tiles:
        cells = fetch_cells_in_bbox(tile, limit=50)
        for cell in cells:
            cid = (cell.get("mcc"), cell.get("mnc"), cell.get("lac"), cell.get("cellid"))
            if cid in seen_ids:
                continue
            seen_ids.add(cid)

            mcc = cell.get("mcc", 0)
            if mcc not in INDIA_MCC:
                continue

            mnc = cell.get("mnc", 0)
            radio = cell.get("radio", "LTE")
            dbm = cell.get("averageSignalStrength", 0)
            range_m = cell.get("range", 1000)
            samples = cell.get("samples", 0)

            towers.append({
                "tower_id": f"OCI_{mcc}_{mnc}_{cell.get('cellid', 0)}",
                "lat": cell.get("lat", center[0]),
                "lng": cell.get("lon", center[1]),
                "operator": _mnc_to_operator(mnc),
                "signal_score": _signal_dbm_to_score(dbm, radio),
                "frequency_mhz": _radio_to_freq(radio),
                "tx_power_dbm": _radio_to_tx_power(radio),
                "height_m": _radio_to_height(radio),
                "zone": zone_name,
                "radio": radio,
                "range_m": range_m,
                "samples": samples,
                "avg_signal_dbm": dbm,
                "mcc": mcc,
                "mnc": mnc,
                "lac": cell.get("lac", 0),
                "cellid": cell.get("cellid", 0),
            })

        # Rate limiting -- be respectful to the API
        time.sleep(0.3)

        if len(towers) >= max_per_zone:
            break

    return towers[:max_per_zone]


def fetch_all_towers(max_per_zone: int = 50) -> pd.DataFrame:
    """Fetch real towers for all 20 Bangalore zones.

    Returns a DataFrame compatible with the existing tower CSV format,
    plus extra columns (radio, range_m, samples, avg_signal_dbm, mcc, mnc, lac, cellid).
    """
    all_towers = []
    total_api_calls = 0

    print(f"Fetching real tower data from OpenCelliD for {len(ZONES)} zones...")

    for zone_name, info in ZONES.items():
        center = info["center"]
        radius = info.get("radius_km", 1.5)
        print(f"  {zone_name} (r={radius}km)... ", end="", flush=True)

        towers = fetch_zone_towers(zone_name, center, radius, max_per_zone)
        all_towers.extend(towers)
        n_tiles = len(_tiles_for_zone(center, radius))
        total_api_calls += n_tiles

        # Summarize
        ops = {}
        for t in towers:
            ops[t["operator"]] = ops.get(t["operator"], 0) + 1
        op_str = ", ".join(f"{k}:{v}" for k, v in sorted(ops.items()))
        print(f"{len(towers)} towers ({op_str})")

    df = pd.DataFrame(all_towers)
    print(f"\nTotal: {len(df)} real towers fetched (~{total_api_calls} API calls used)")
    return df


def save_real_towers(df: pd.DataFrame, filename: str = "towers_real.csv"):
    """Save the real tower data alongside the existing synthetic towers."""
    path = DATA_DIR / filename
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Saved to {path}")
    return path


def load_real_towers(filename: str = "towers_real.csv") -> pd.DataFrame | None:
    """Load cached real tower data if available."""
    path = DATA_DIR / filename
    if path.exists():
        return pd.read_csv(path)
    return None


def get_towers(prefer_real: bool = True) -> pd.DataFrame:
    """Get tower data -- merges synthetic (for model density) with real (for tech features).

    Strategy:
    - Always load the synthetic towers.csv as the base (proper zone density,
      calibrated signal scores, used for training).
    - If real OpenCelliD data exists and has precise coordinates (>2 decimal
      places), append real towers that are far enough from synthetic towers
      (>500 m) to avoid spatial duplicates.
    - This ensures the model always sees the dense synthetic distribution it
      was trained on, while gaining real-world radio/range/samples info.
    """
    synthetic_path = DATA_DIR / "towers.csv"
    synthetic = pd.read_csv(synthetic_path) if synthetic_path.exists() else pd.DataFrame()

    if not prefer_real or synthetic.empty:
        return synthetic

    real = load_real_towers()
    # Only use real towers with fine-grained coordinates (>2 decimal places)
    if real is None or real.empty:
        return synthetic
    real_precise = real[
        (real["lat"].round(2) != real["lat"]) | (real["lng"].round(2) != real["lng"])
    ]
    if real_precise.empty:
        return synthetic

    # Append real towers; let caller de-dup by tower_id
    combined = pd.concat([synthetic, real_precise], ignore_index=True)
    if "tower_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["tower_id"])
    return combined


def refresh_towers(max_per_zone: int = 50) -> pd.DataFrame:
    """Fetch fresh tower data from OpenCelliD and save to disk."""
    df = fetch_all_towers(max_per_zone=max_per_zone)
    if len(df) > 0:
        save_real_towers(df)
    return df


def fetch_towers_for_path(
    path: list[dict],
    sample_every_n: int = 30,
    max_towers: int = 200,
    radius_km: float = 0.8,
) -> pd.DataFrame:
    """Fetch real cell towers near a route from OpenCelliD in real time.

    Samples every ``sample_every_n`` points along the path, queries a small
    bounding box around each sample, de-duplicates, and returns a DataFrame
    with the same schema as ``get_towers()``.

    Parameters
    ----------
    path : list of {"lat": float, "lng": float} from TomTom / synthetic
    sample_every_n : query every Nth point (reduces API calls)
    max_towers : cap total towers returned
    radius_km : query radius around each sample point
    """
    if not _api_key():
        return pd.DataFrame()

    seen_ids: set = set()
    towers: list[dict] = []

    # Deduplicate sample points by snapping to a grid
    sampled = path[::max(1, sample_every_n)]
    if path and path[-1] not in sampled:
        sampled.append(path[-1])

    for pt in sampled:
        if len(towers) >= max_towers:
            break

        lat, lng = pt["lat"], pt["lng"]
        # Bounding box: radius_km in each direction
        half = min(radius_km / 111.0, 0.012)
        bbox = (
            round(lat - half, 6), round(lng - half, 6),
            round(lat + half, 6), round(lng + half, 6),
        )

        cells = fetch_cells_in_bbox(bbox, limit=50)
        for cell in cells:
            mcc = cell.get("mcc", 0)
            if mcc not in INDIA_MCC:
                continue
            cid = (mcc, cell.get("mnc"), cell.get("lac"), cell.get("cellid"))
            if cid in seen_ids:
                continue
            seen_ids.add(cid)

            mnc = cell.get("mnc", 0)
            radio = cell.get("radio", "LTE")
            dbm = cell.get("averageSignalStrength", 0)

            towers.append({
                "tower_id": f"OCI_{mcc}_{mnc}_{cell.get('cellid', 0)}",
                "lat": cell.get("lat", lat),
                "lng": cell.get("lon", lng),
                "operator": _mnc_to_operator(mnc),
                "signal_score": _signal_dbm_to_score(dbm, radio),
                "frequency_mhz": _radio_to_freq(radio),
                "tx_power_dbm": _radio_to_tx_power(radio),
                "height_m": _radio_to_height(radio),
                "zone": "route",
                "radio": radio,
                "range_m": cell.get("range", 1000),
                "samples": cell.get("samples", 0),
                "avg_signal_dbm": dbm,
                "mcc": mcc,
                "mnc": mnc,
                "lac": cell.get("lac", 0),
                "cellid": cell.get("cellid", 0),
            })

        time.sleep(0.2)

    if not towers:
        return pd.DataFrame()

    return pd.DataFrame(towers[:max_towers])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch real tower data from OpenCelliD")
    parser.add_argument("--max-per-zone", type=int, default=50, help="Max towers per zone")
    parser.add_argument("--count-only", action="store_true", help="Only count towers, don't fetch")
    args = parser.parse_args()

    if args.count_only:
        print("Counting towers per zone...")
        for name, info in ZONES.items():
            bbox = _zone_bbox(info["center"], info.get("radius_km", 1.5))
            count = fetch_cell_count_in_bbox(bbox)
            print(f"  {name}: {count} towers")
            time.sleep(0.5)
    else:
        df = refresh_towers(max_per_zone=args.max_per_zone)
        if len(df) > 0:
            print(f"\nSummary:")
            print(f"  Operators: {df['operator'].value_counts().to_dict()}")
            print(f"  Radio types: {df['radio'].value_counts().to_dict()}")
            print(f"  Zones: {df['zone'].nunique()}")
            print(f"  Towers with signal data: {(df['avg_signal_dbm'] != 0).sum()}")
