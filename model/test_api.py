"""End-to-end test for all PUT endpoints."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

BASE = "http://localhost:8000"

SAMPLE_TOWERS = [
    {"lat": 12.9716, "lng": 77.5946, "operator": "Jio", "signal_score": 85,
     "frequency_mhz": 1800, "tx_power_dbm": 43, "height_m": 35},
    {"lat": 12.9279, "lng": 77.6271, "operator": "Airtel", "signal_score": 78,
     "frequency_mhz": 2100, "tx_power_dbm": 44, "height_m": 40},
    {"lat": 12.9698, "lng": 77.7499, "operator": "Vi", "signal_score": 62,
     "frequency_mhz": 900, "tx_power_dbm": 42, "height_m": 30},
    {"lat": 13.0358, "lng": 77.5970, "operator": "BSNL", "signal_score": 55,
     "frequency_mhz": 700, "tx_power_dbm": 41, "height_m": 28},
]

SAMPLE_PATH = [
    {"lat": 12.9716, "lng": 77.5946},
    {"lat": 12.9600, "lng": 77.6100},
    {"lat": 12.9500, "lng": 77.6200},
    {"lat": 12.9400, "lng": 77.6300},
    {"lat": 12.9279, "lng": 77.6271},
]


def test_health():
    print("[test] PUT /model/health ...")
    r = requests.put(f"{BASE}/model/health")
    assert r.status_code == 200
    data = r.json()
    print(f"  status={data['status']}, device={data['device']}, "
          f"towers={data['towers_in_training']}, samples={data['samples_in_training']}")
    return data


def test_predict_signal():
    print("[test] PUT /model/predict-signal ...")
    payload = {
        "lat": 12.9716, "lng": 77.5946,
        "towers": SAMPLE_TOWERS,
        "telecom": "all",
        "time_hour": 14.0,
        "weather_factor": 0.9,
        "speed_kmh": 50.0,
    }
    r = requests.put(f"{BASE}/model/predict-signal", json=payload)
    assert r.status_code == 200
    data = r.json()
    print(f"  signal={data['signal_strength']}, drop={data['drop_probability']}, "
          f"handoff={data['handoff_risk']}, confidence={data['confidence']}")
    return data


def test_analyze_route():
    print("[test] PUT /model/analyze-route ...")
    payload = {
        "route": {
            "name": "Test Route",
            "eta": 25,
            "distance": 8.5,
            "path": SAMPLE_PATH,
            "zones": ["MG Road", "Koramangala"],
        },
        "towers": SAMPLE_TOWERS,
        "telecom": "all",
        "time_hour": 14.0,
        "weather_factor": 0.9,
        "speed_kmh": 50.0,
        "task_type": "call",
        "task_duration_min": 10.0,
    }
    r = requests.put(f"{BASE}/model/analyze-route", json=payload)
    assert r.status_code == 200
    data = r.json()
    conn = data.get("connectivity", {})
    print(f"  avg_conn={conn.get('avg_connectivity')}, "
          f"bad_zones={len(data.get('bad_zones', []))}, "
          f"task_feasible={data.get('task_feasibility', {}).get('feasible')}")
    return data


def test_detect_zones():
    print("[test] PUT /model/detect-zones ...")
    payload = {
        "route": {
            "name": "Zone Check",
            "eta": 20,
            "distance": 6.0,
            "path": SAMPLE_PATH,
            "zones": ["MG Road"],
        },
        "towers": SAMPLE_TOWERS,
        "telecom": "all",
        "time_hour": 9.0,
        "weather_factor": 1.0,
        "speed_kmh": 35.0,
    }
    r = requests.put(f"{BASE}/model/detect-zones", json=payload)
    assert r.status_code == 200
    data = r.json()
    print(f"  bad_zones={len(data.get('bad_zones', []))}, "
          f"total_km={data.get('total_bad_zone_km')}, "
          f"warnings={len(data.get('warnings', []))}")
    return data


def test_score_routes():
    print("[test] PUT /model/score-routes ...")
    payload = {
        "routes": [
            {
                "name": "Route A - Fast",
                "eta": 18, "distance": 7.0,
                "path": SAMPLE_PATH,
                "zones": ["MG Road", "Koramangala"],
            },
            {
                "name": "Route B - Scenic",
                "eta": 28, "distance": 12.0,
                "path": [
                    {"lat": 12.9716, "lng": 77.5946},
                    {"lat": 12.9800, "lng": 77.6000},
                    {"lat": 12.9750, "lng": 77.6150},
                    {"lat": 12.9500, "lng": 77.6250},
                    {"lat": 12.9279, "lng": 77.6271},
                ],
                "zones": ["MG Road", "Indiranagar", "Koramangala"],
            },
        ],
        "towers": SAMPLE_TOWERS,
        "preference": 50.0,
        "telecom": "all",
        "time_hour": 14.0,
        "weather_factor": 0.9,
        "speed_kmh": 50.0,
    }
    r = requests.put(f"{BASE}/model/score-routes", json=payload)
    assert r.status_code == 200
    data = r.json()
    print(f"  recommended={data['recommended_route']}")
    for rt in data.get("routes", []):
        print(f"    {rt['name']}: signal={rt['signal_score']}, "
              f"weighted={rt['weighted_score']}, rejected={rt['rejected']}")
    return data


if __name__ == "__main__":
    print("=" * 60)
    print("Cellular Maze Model API -- Endpoint Tests")
    print("=" * 60)
    try:
        test_health()
        test_predict_signal()
        test_analyze_route()
        test_detect_zones()
        test_score_routes()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
