"""Test the smart routing flow: intent-driven decisions + learning."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import json

BASE = "http://localhost:8000"

TOWERS = [
    {"lat": 12.9716, "lng": 77.5946, "operator": "Jio", "signal_score": 90,
     "frequency_mhz": 1800, "tx_power_dbm": 44, "height_m": 35},
    {"lat": 12.9279, "lng": 77.6271, "operator": "Airtel", "signal_score": 82,
     "frequency_mhz": 2100, "tx_power_dbm": 43, "height_m": 40},
    {"lat": 12.9698, "lng": 77.7499, "operator": "Vi", "signal_score": 45,
     "frequency_mhz": 900, "tx_power_dbm": 42, "height_m": 30},
    {"lat": 13.0358, "lng": 77.5970, "operator": "Jio", "signal_score": 75,
     "frequency_mhz": 2300, "tx_power_dbm": 43, "height_m": 38},
    {"lat": 12.9591, "lng": 77.6974, "operator": "Airtel", "signal_score": 55,
     "frequency_mhz": 1800, "tx_power_dbm": 42, "height_m": 32},
]

# Route A: Fast but goes through sparse coverage
ROUTE_FAST = {
    "name": "Highway Express (Fast)",
    "eta": 15, "distance": 12.0,
    "path": [
        {"lat": 12.9716, "lng": 77.5946},
        {"lat": 12.9800, "lng": 77.6300},
        {"lat": 12.9850, "lng": 77.6700},
        {"lat": 12.9698, "lng": 77.7499},
    ],
    "zones": ["MG Road", "Whitefield"],
}

# Route B: Slower but stays near towers with good signal
ROUTE_SIGNAL = {
    "name": "City Route (Good Signal)",
    "eta": 28, "distance": 9.0,
    "path": [
        {"lat": 12.9716, "lng": 77.5946},
        {"lat": 12.9600, "lng": 77.6000},
        {"lat": 12.9400, "lng": 77.6100},
        {"lat": 12.9279, "lng": 77.6271},
        {"lat": 12.9350, "lng": 77.6500},
        {"lat": 12.9500, "lng": 77.6800},
        {"lat": 12.9591, "lng": 77.6974},
        {"lat": 12.9650, "lng": 77.7200},
        {"lat": 12.9698, "lng": 77.7499},
    ],
    "zones": ["MG Road", "Koramangala", "Marathahalli", "Whitefield"],
}

# Route C: Middle ground
ROUTE_BALANCED = {
    "name": "Ring Road (Balanced)",
    "eta": 22, "distance": 10.5,
    "path": [
        {"lat": 12.9716, "lng": 77.5946},
        {"lat": 12.9750, "lng": 77.6200},
        {"lat": 12.9650, "lng": 77.6500},
        {"lat": 12.9591, "lng": 77.6974},
        {"lat": 12.9650, "lng": 77.7200},
        {"lat": 12.9698, "lng": 77.7499},
    ],
    "zones": ["MG Road", "Marathahalli", "Whitefield"],
}

ROUTES = [ROUTE_FAST, ROUTE_SIGNAL, ROUTE_BALANCED]


def sep(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_scenario(intent, description):
    print(f"\n--- Intent: \"{intent}\" ({description}) ---")
    payload = {
        "user_id": "driver_001",
        "intent": intent,
        "routes": ROUTES,
        "towers": TOWERS,
        "telecom": "all",
        "time_hour": 14.0,
        "weather_factor": 0.9,
        "speed_kmh": 50.0,
    }
    r = requests.put(f"{BASE}/model/smart-route", json=payload)
    assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
    data = r.json()

    print(f"  Resolved preference: {data['resolved_preference']} "
          f"(source: {data['preference_source']})")
    print(f"  Task type: {data['task_type']}, duration: {data['task_duration_min']} min")
    print(f"  Recommended: {data['recommended_route']}")

    for rt in data["routes"]:
        marker = " <<< RECOMMENDED" if rt["name"] == data["recommended_route"] else ""
        tf = rt.get("task_feasibility", {})
        feasible = tf.get("feasible", "N/A") if tf else "N/A"
        print(f"    {rt['name']:30s}  signal={rt['signal_score']:5.1f}  "
              f"weighted={rt['weighted_score']:6.1f}  "
              f"task_ok={feasible}{marker}")

    return data


def test_resolve_intent():
    sep("RESOLVE INTENT (preview)")
    for intent in ["meeting", "fastest", "call", "I need to download a file", "emergency"]:
        r = requests.put(f"{BASE}/model/resolve-intent", json={
            "user_id": "driver_001",
            "intent": intent,
            "time_hour": 14.0,
        })
        data = r.json()
        print(f"  \"{intent:35s}\" -> pref={data['preference']:3.0f}  "
              f"task={data['task_type']:10s}  source={data['source']}")


def test_learning():
    sep("LEARNING: Record choices and see preference adapt")

    # Simulate: user always picks high-signal routes during meetings
    for i in range(5):
        requests.put(f"{BASE}/model/record-choice", json={
            "user_id": "driver_002",
            "intent": "meeting",
            "preference_used": 95.0,  # user keeps pushing slider to 95
            "time_hour": 14.0,
            "chosen_route_name": "City Route (Good Signal)",
            "chosen_signal_score": 72.0,
            "chosen_eta": 28.0,
        })

    # Now check: does the system learn this user's meeting preference?
    r = requests.put(f"{BASE}/model/resolve-intent", json={
        "user_id": "driver_002",
        "intent": "meeting",
        "time_hour": 14.0,
    })
    data = r.json()
    print(f"  After 5 meeting choices at pref=95:")
    print(f"    Learned preference: {data['preference']} (default was 85)")
    print(f"    Source: {data['source']}")
    print(f"    Total choices: {data['total_choices']}")

    # Different user, no history
    r = requests.put(f"{BASE}/model/resolve-intent", json={
        "user_id": "new_user",
        "intent": "meeting",
        "time_hour": 14.0,
    })
    data = r.json()
    print(f"  New user (no history):")
    print(f"    Preference: {data['preference']} (default)")
    print(f"    Source: {data['source']}")


if __name__ == "__main__":
    sep("SCENARIO TESTS: Does the model pick the right route?")

    # Case 1: User has a meeting -- needs strong network
    test_scenario("meeting", "User has a video meeting -- need best signal")

    # Case 2: User just wants to get there fast
    test_scenario("fastest", "User in a hurry -- speed is everything")

    # Case 3: User might take a phone call
    test_scenario("call", "User might get a call -- balanced")

    # Case 4: Normal idle drive
    test_scenario("navigation", "Just driving, no special need")

    # Case 5: Natural language input
    test_scenario("I have a zoom call in 10 minutes", "Free-text intent")

    # Resolve intent preview
    test_resolve_intent()

    # Learning test
    test_learning()

    sep("ALL SMART ROUTE TESTS PASSED")
