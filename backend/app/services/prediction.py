from datetime import datetime

import numpy as np
from sklearn.linear_model import LinearRegression

from app.services.data_loader import load_signal_zones, load_tower_data


def predict_zone_signal(zone_name: str, horizon_minutes: int = 15) -> dict:
    zones = {zone["name"].lower(): zone for zone in load_signal_zones()}
    zone = zones.get(zone_name.lower(), zones["electronic city"])

    baseline = zone["score"]
    current_hour = datetime.now().hour

    tower_df = load_tower_data()
    historical = tower_df[tower_df["zone"].str.lower() == zone["name"].lower()]

    if historical.empty:
        sample_minutes = np.array([0, 5, 10, 15, 20], dtype=float).reshape(-1, 1)
        sample_scores = np.array([baseline, baseline - 2, baseline - 5, baseline - 8, baseline - 10], dtype=float)
    else:
        normalized_scores = historical["signal_score"].to_numpy(dtype=float)
        hour_penalty = abs(current_hour - 18) / 10.0
        sample_minutes = np.arange(0, normalized_scores.shape[0] * 5, 5, dtype=float).reshape(-1, 1)
        sample_scores = np.clip(normalized_scores - hour_penalty, 0, 100)

    model = LinearRegression()
    model.fit(sample_minutes, sample_scores)
    prediction = float(model.predict(np.array([[horizon_minutes]], dtype=float))[0])

    prediction = max(0.0, min(100.0, prediction))
    if prediction < 40:
        message = f"Weak signal expected near {zone['name']} in {horizon_minutes} mins"
    elif prediction < 70:
        message = f"Moderate signal expected near {zone['name']} in {horizon_minutes} mins"
    else:
        message = f"Strong signal expected near {zone['name']} in {horizon_minutes} mins"

    return {
        "zone": zone["name"],
        "horizon_minutes": horizon_minutes,
        "expected_signal_score": round(prediction, 2),
        "message": message,
    }
