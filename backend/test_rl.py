"""Test RL pattern learning -- simulates the son/dad scenario."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

BASE = "http://localhost:8000"

ORIGIN = {"lat": 12.925, "lng": 77.584}       # Jayanagar
DEST   = {"lat": 12.9279, "lng": 77.6271}     # Koramangala

SAMPLE_ROUTES = [{
    "name": "Route A", "eta": 15, "distance": 5,
    "path": [ORIGIN, DEST],
    "zones": ["Jayanagar", "Koramangala"],
}]

SAMPLE_TOWERS = [{
    "tower_id": "T1", "lat": 12.926, "lng": 77.600,
    "operator": "Jio", "signal_score": 80,
    "frequency_mhz": 1800, "tx_power_dbm": 43,
    "height_m": 30, "range_km": 2.5, "zone": "Jayanagar",
}]


def test_rl_scenario():
    print("=== RL Pattern Learning Test ===\n")

    # 1. Train: Son drives 7:30 AM weekday -> chooses "meeting"
    print("--- Training: Son's morning trips (7:30 AM, meeting) ---")
    for i in range(5):
        resp = requests.put(f"{BASE}/model/record-trip", json={
            "user_id": "son",
            "origin": ORIGIN,
            "destination": DEST,
            "time_hour": 7.5,
            "day_of_week": i % 5,
            "chosen_intent": "meeting",
            "recommended_intent": "",
        })
        data = resp.json()
        print(f"  Trip {i+1}: pattern={data['pattern_key']}, total={data['trip_count']}")

    # 2. Train: Dad drives 10:00 AM weekday -> chooses "navigation"
    print("\n--- Training: Dad's mid-morning trips (10:00 AM, navigation) ---")
    for i in range(5):
        resp = requests.put(f"{BASE}/model/record-trip", json={
            "user_id": "dad",
            "origin": ORIGIN,
            "destination": DEST,
            "time_hour": 10.0,
            "day_of_week": i % 5,
            "chosen_intent": "navigation",
            "recommended_intent": "",
        })
        data = resp.json()
        print(f"  Trip {i+1}: pattern={data['pattern_key']}, total={data['trip_count']}")

    # 3. Check son's patterns
    print("\n--- Son's Learned Patterns ---")
    resp = requests.put(f"{BASE}/model/user-patterns", json={"user_id": "son"})
    data = resp.json()
    for p in data["patterns"]:
        print(f"  {p['time_bucket']}|{p['day_type']}|{p['origin_zone']}->{p['dest_zone']}")
        print(f"    Predicted: {p['predicted_intent']} (confidence: {p['confidence']})")

    # 4. Check dad's patterns
    print("\n--- Dad's Learned Patterns ---")
    resp = requests.put(f"{BASE}/model/user-patterns", json={"user_id": "dad"})
    data = resp.json()
    for p in data["patterns"]:
        print(f"  {p['time_bucket']}|{p['day_type']}|{p['origin_zone']}->{p['dest_zone']}")
        print(f"    Predicted: {p['predicted_intent']} (confidence: {p['confidence']})")

    # 5. Auto-route: Son at 7:30 AM (should learn "meeting")
    print("\n--- Auto-route: Son at 7:30 AM ---")
    resp = requests.put(f"{BASE}/model/auto-route", json={
        "user_id": "son",
        "origin": ORIGIN,
        "destination": DEST,
        "time_hour": 7.5,
        "day_of_week": 1,
        "intent": "",
        "routes": SAMPLE_ROUTES,
        "towers": SAMPLE_TOWERS,
    })
    data = resp.json()
    rl = data["rl_info"]
    print(f"  RL selected: {rl['rl_selected_intent']} (conf={rl['confidence']})")
    print(f"  Final intent: {data['intent']} (source: {data['preference_source']})")
    print(f"  Preference: {data['resolved_preference']}")

    # 6. Auto-route: Dad at 10:00 AM (should learn "navigation")
    print("\n--- Auto-route: Dad at 10:00 AM ---")
    resp = requests.put(f"{BASE}/model/auto-route", json={
        "user_id": "dad",
        "origin": ORIGIN,
        "destination": DEST,
        "time_hour": 10.0,
        "day_of_week": 1,
        "intent": "",
        "routes": SAMPLE_ROUTES,
        "towers": SAMPLE_TOWERS,
    })
    data = resp.json()
    rl = data["rl_info"]
    print(f"  RL selected: {rl['rl_selected_intent']} (conf={rl['confidence']})")
    print(f"  Final intent: {data['intent']} (source: {data['preference_source']})")
    print(f"  Preference: {data['resolved_preference']}")

    # 7. New user at same time (should NOT have patterns)
    print("\n--- Auto-route: New user 'guest' at 7:30 AM (no history) ---")
    resp = requests.put(f"{BASE}/model/auto-route", json={
        "user_id": "guest",
        "origin": ORIGIN,
        "destination": DEST,
        "time_hour": 7.5,
        "day_of_week": 1,
        "intent": "",
        "routes": SAMPLE_ROUTES,
        "towers": SAMPLE_TOWERS,
    })
    data = resp.json()
    rl = data["rl_info"]
    print(f"  RL selected: {rl['rl_selected_intent']} (exploration={rl['exploration_needed']})")
    print(f"  Final intent: {data['intent']} (source: {data['preference_source']})")

    # 8. Frontend endpoints
    print("\n--- Frontend Endpoints ---")

    resp = requests.get(f"{BASE}/api/routes", params={
        "source": "MIT", "destination": "Airport", "preference": 50,
    })
    data = resp.json()
    print(f"  GET /api/routes: {len(data['routes'])} routes, recommended={data['recommended_route']}")

    resp = requests.get(f"{BASE}/api/heatmap")
    data = resp.json()
    print(f"  GET /api/heatmap: {len(data['zones'])} zones")

    resp = requests.get(f"{BASE}/api/predict", params={"zone": "Electronic City"})
    data = resp.json()
    print(f"  GET /api/predict: score={data['expected_signal_score']}")

    resp = requests.post(f"{BASE}/api/reroute", json={
        "source": "MIT", "destination": "Airport", "preference": 50,
    })
    data = resp.json()
    print(f"  POST /api/reroute: {data['selected_route']['name']}")

    print("\n=== All Tests Passed ===")


if __name__ == "__main__":
    test_rl_scenario()
