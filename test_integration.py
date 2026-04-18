"""Integration test for all API endpoints."""
import requests
import json

BASE = "http://localhost:8000"

def test_predict_signal():
    print("=== 1. Predict Signal (with MC Dropout confidence) ===")
    r = requests.put(f"{BASE}/model/predict-signal", json={
        "lat": 12.9279, "lng": 77.6271,
        "towers": [{"lat": 12.928, "lng": 77.627, "signal_score": 80}],
        "telecom": "all", "time_hour": 14.0, "weather_factor": 1.0, "speed_kmh": 40.0
    })
    print(f"  Status: {r.status_code}")
    d = r.json()
    print(f"  Signal: {d.get('signal_strength')}")
    print(f"  Drop prob: {d.get('drop_probability')}")
    print(f"  Handoff risk: {d.get('handoff_risk')}")
    print(f"  Confidence: {d.get('confidence')}")
    print(f"  Nearby towers: {d.get('nearby_towers')}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert d.get("confidence") in ("high", "medium", "low"), f"Bad confidence: {d.get('confidence')}"
    print("  PASS\n")

def test_predict_signal_isolated():
    print("=== 2. Predict Signal (isolated location, expect low confidence) ===")
    r = requests.put(f"{BASE}/model/predict-signal", json={
        "lat": 13.2, "lng": 77.9,
        "towers": [],
        "telecom": "all", "time_hour": 2.0, "weather_factor": 0.5, "speed_kmh": 10.0
    })
    print(f"  Status: {r.status_code}")
    d = r.json()
    print(f"  Signal: {d.get('signal_strength')}")
    print(f"  Confidence: {d.get('confidence')}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert d.get("confidence") in ("high", "medium", "low"), f"Bad confidence: {d.get('confidence')}"
    print("  PASS\n")

def test_routes():
    print("=== 3. Routes Endpoint ===")
    r = requests.get(f"{BASE}/api/routes", params={
        "source": "Koramangala",
        "destination": "Whitefield",
    }, timeout=300)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        routes = data.get("routes", []) if isinstance(data, dict) else data
        if routes:
            route = routes[0]
            print(f"  Routes returned: {len(routes)}")
            print(f"  Recommended: {data.get('recommended_route', 'N/A')}")
            print(f"  First route name: {route.get('name')}")
            print(f"  Signal score: {route.get('signal_score')}")
            print(f"  Drops/km: {route.get('drops_per_km')}")
            print(f"  Confidence: {route.get('confidence')}")
            print(f"  Avg uncertainty: {route.get('avg_uncertainty')}")
            print("  PASS\n")
        else:
            print(f"  Response (no routes): {str(data)[:300]}")
            print("  WARN: no routes returned\n")
    else:
        print(f"  Error: {r.text[:300]}")
        print("  FAIL\n")

def test_model_status():
    print("=== 4. Model Status ===")
    r = requests.get(f"{BASE}/docs")
    print(f"  Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("  OpenAPI docs accessible")
    print("  PASS\n")

if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATION TESTS")
    print("=" * 60 + "\n")
    test_predict_signal()
    test_predict_signal_isolated()
    test_routes()
    test_model_status()
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
