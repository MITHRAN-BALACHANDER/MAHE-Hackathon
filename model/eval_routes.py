"""Offline route evaluation: compare routes across OD pairs.

Generates a summary table showing route choice quality for demo.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from model.config import DATA_DIR, ZONES
from model.scoring import score_route, rank_routes
from model.inference import reload_model


# 10 representative OD pairs across Bangalore
OD_PAIRS = [
    ("Koramangala",      "Whitefield"),
    ("MG Road",          "Electronic City"),
    ("Indiranagar",      "Hebbal"),
    ("Jayanagar",        "KR Puram"),
    ("BTM Layout",       "Yelahanka"),
    ("HSR Layout",       "Peenya"),
    ("Rajajinagar",      "Sarjapur Road"),
    ("Marathahalli",     "Bannerghatta"),
    ("Silk Board",       "Devanahalli"),
    ("JP Nagar",         "Whitefield"),
]


def _interpolate_path(start: tuple, end: tuple, n_points: int = 30) -> list[dict]:
    """Create a straight-line path between two zone centers."""
    lats = np.linspace(start[0], end[0], n_points)
    lngs = np.linspace(start[1], end[1], n_points)
    return [{"lat": float(la), "lng": float(lo)} for la, lo in zip(lats, lngs)]


def _make_routes(origin: str, dest: str) -> list[dict]:
    """Generate 3 synthetic route variants for an OD pair."""
    start = ZONES[origin]["center"]
    end = ZONES[dest]["center"]

    # Direct route
    direct = _interpolate_path(start, end, 30)
    dist_direct = np.sqrt((start[0] - end[0])**2 + (start[1] - end[1])**2) * 111
    eta_direct = dist_direct / 30 * 60  # ~30 km/h avg

    # Detour via a midpoint (shifted)
    mid = ((start[0] + end[0]) / 2 + 0.02, (start[1] + end[1]) / 2 + 0.02)
    detour = _interpolate_path(start, mid, 15) + _interpolate_path(mid, end, 15)
    eta_detour = eta_direct * 1.25

    # Highway route (shifted other direction)
    mid2 = ((start[0] + end[0]) / 2 - 0.015, (start[1] + end[1]) / 2 - 0.015)
    highway = _interpolate_path(start, mid2, 15) + _interpolate_path(mid2, end, 15)
    eta_highway = eta_direct * 1.15

    return [
        {"name": "Direct", "path": direct, "eta": round(eta_direct, 1),
         "distance": round(dist_direct, 1)},
        {"name": "Detour", "path": detour, "eta": round(eta_detour, 1),
         "distance": round(dist_direct * 1.2, 1)},
        {"name": "Highway", "path": highway, "eta": round(eta_highway, 1),
         "distance": round(dist_direct * 1.1, 1)},
    ]


def evaluate_routes():
    """Run route evaluation across all OD pairs and print summary table."""
    reload_model()

    towers_df = pd.read_csv(DATA_DIR / "towers.csv")
    rows = []

    for origin, dest in OD_PAIRS:
        routes = _make_routes(origin, dest)
        ranked = rank_routes(routes, towers_df, preference=50.0)

        for i, r in enumerate(ranked):
            conn = r["connectivity"]
            rows.append({
                "OD Pair": f"{origin} -> {dest}",
                "Route": r["name"],
                "ETA (min)": r["eta"],
                "Avg Signal": conn["avg_connectivity"],
                "Min Signal": conn["min_connectivity"],
                "Drops/km": conn["drops_per_km"],
                "Longest Gap": conn["drop_segments"],
                "Confidence": conn["confidence"],
                "Uncertainty": conn["avg_uncertainty"],
                "Score": r["weighted_score"],
                "Picked": ">>>" if i == 0 else "",
            })

    df = pd.DataFrame(rows)

    print("\n" + "=" * 120)
    print("ROUTE EVALUATION TABLE")
    print("=" * 120)
    print(df.to_string(index=False))
    print("=" * 120)

    # Summary stats
    picked = df[df["Picked"] == ">>>"]
    print(f"\nPicked routes summary:")
    print(f"  Avg signal of picked routes:    {picked['Avg Signal'].mean():.1f}")
    print(f"  Avg uncertainty:                {picked['Uncertainty'].mean():.1f}")
    print(f"  High confidence picks:          {(picked['Confidence'] == 'high').sum()}/{len(picked)}")
    print(f"  Avg drops/km:                   {picked['Drops/km'].mean():.2f}")

    return df


if __name__ == "__main__":
    evaluate_routes()
