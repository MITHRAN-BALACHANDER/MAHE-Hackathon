"""Quick model test: inference correctness + speed benchmark."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

def test_predict_single():
    from model.inference import predict_single
    feats = np.random.rand(22).astype(np.float32)
    t0 = time.time()
    r = predict_single(feats)
    elapsed = time.time() - t0
    assert "signal_strength" in r
    assert 0 <= r["signal_strength"] <= 100
    assert 0 <= r["drop_probability"] <= 1
    print(f"  predict_single: signal={r['signal_strength']:.1f}, drop={r['drop_probability']:.3f}, t={elapsed:.3f}s")

def test_predict_with_uncertainty():
    from model.inference import predict_with_uncertainty
    feats = np.random.rand(60, 22).astype(np.float32)
    t0 = time.time()
    r = predict_with_uncertainty(feats, n_samples=5)
    elapsed = time.time() - t0
    assert r["signal_strength"].shape == (60,)
    assert "signal_uncertainty" in r
    print(f"  predict_with_uncertainty (60pts,5 samples): mean={r['signal_strength'].mean():.1f}, t={elapsed:.3f}s")

def test_score_route_speed():
    from model.scoring import score_route
    towers_df = pd.read_csv(Path(__file__).parent / "data" / "towers.csv")
    # Long path (200 pts) -- should be downsampled to 60
    path = [{"lat": 12.97 + i * 0.001, "lng": 77.59 + i * 0.001} for i in range(200)]
    t0 = time.time()
    conn = score_route(path, towers_df, telecom="all", time_hour=14.0)
    elapsed = time.time() - t0
    assert "avg_connectivity" in conn
    assert 0 <= conn["avg_connectivity"] <= 100
    assert conn["total_segments"] == 200  # reports full path length
    print(f"  score_route (200pts->60 sampled): avg={conn['avg_connectivity']:.1f}, confidence={conn['confidence']}, t={elapsed:.3f}s")

def test_rank_routes_parallel():
    from model.scoring import rank_routes
    towers_df = pd.read_csv(Path(__file__).parent / "data" / "towers.csv")
    path = [{"lat": 12.97 + i * 0.005, "lng": 77.59 + i * 0.003} for i in range(40)]
    routes = [
        {"name": f"Route{i}", "eta": 20 + i * 5, "distance": 8.0 + i, "path": path, "zones": [], "traffic_delay": 0}
        for i in range(5)
    ]
    t0 = time.time()
    ranked = rank_routes(routes, towers_df, preference=70)
    elapsed = time.time() - t0
    assert len(ranked) == 5
    assert all("signal_score" in r for r in ranked)
    print(f"  rank_routes (5 routes parallel): top={ranked[0]['name']}, signal={ranked[0]['signal_score']:.1f}, t={elapsed:.3f}s")

def test_bad_zones():
    from model.bad_zones import detect_bad_zones
    segment_signals = [80.0] * 10 + [15.0] * 5 + [75.0] * 10
    path = [{"lat": 12.97 + i * 0.001, "lng": 77.59 + i * 0.001} for i in range(25)]
    zones = detect_bad_zones(path, segment_signals, avg_speed_kmh=40.0)
    assert isinstance(zones, list)
    print(f"  detect_bad_zones: found {len(zones)} zone(s)")

if __name__ == "__main__":
    tests = [test_predict_single, test_predict_with_uncertainty, test_score_route_speed, test_rank_routes_parallel, test_bad_zones]
    failed = 0
    for fn in tests:
        print(f"\n[TEST] {fn.__name__}")
        try:
            fn()
            print(f"  PASS")
        except Exception as e:
            print(f"  FAIL: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {len(tests)-failed}/{len(tests)} passed")
    if failed:
        sys.exit(1)
