"""
Benchmark: measure execution time of each model in the order they run
during a real /api/routes + /api/auto-route request.

Five distinct ML models in the application:

  /api/routes pipeline:
    1. ResidualSignalNet (MC Dropout)  -- rank_routes -> score_route -> predict_with_uncertainty
    2. Dead Zone Predictor             -- predict_carrier_zones (per-carrier, no MC)
    3. Bad Zone Detector               -- detect_bad_zones + assess_task_feasibility

  /api/auto-route pipeline (adds):
    4. Thompson Sampling Bandit (RL)   -- ContextualBandit.select / update
    5. Smart Preference Engine         -- resolve_intent / get_smart_preference
"""

import sys, time, statistics, datetime, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

TOWERS_CSV = Path(__file__).parent / "data" / "towers.csv"

# Representative 5-route scenario (similar to a real Bangalore request)
PATH_LEN = 120  # typical TomTom path points
N_ROUTES  = 5

def make_path(n=PATH_LEN, lat_start=12.97, lng_start=77.59):
    return [{"lat": lat_start + i * 0.002, "lng": lng_start + i * 0.001} for i in range(n)]

def make_routes(n=N_ROUTES):
    return [
        {
            "name": f"Route {i+1}",
            "eta": 20 + i * 4,
            "distance": 9.0 + i * 1.5,
            "path": make_path(PATH_LEN, 12.97 + i * 0.01, 77.59 + i * 0.005),
            "zones": ["MG Road", "Koramangala"],
            "traffic_delay": i * 2,
        }
        for i in range(n)
    ]

TOWERS_DF = pd.read_csv(TOWERS_CSV)
ROUTES    = make_routes()
TIME_HOUR = 8.5   # morning commute
WEATHER   = 0.92
SPEED     = 40.0

RUNS = 5  # repeat each benchmark this many times for stable averages


# =========================================================================
# MODEL 1 -- ResidualSignalNet (MC Dropout)
#   Called by: rank_routes -> score_route -> predict_with_uncertainty
#   Input: 22-dim feature vectors, one per route point
#   Output: signal_strength, drop_probability, handoff_risk + uncertainties
#   Triggered FIRST in both /api/routes and /api/auto-route
# =========================================================================

def bench_model1_residual_signal_net():
    from model.scoring import rank_routes

    times = []
    result = None
    for _ in range(RUNS):
        routes_copy = make_routes()
        t0 = time.perf_counter()
        ranked = rank_routes(
            routes_copy, TOWERS_DF,
            preference=70, telecom="all",
            time_hour=TIME_HOUR, weather_factor=WEATHER, speed_kmh=SPEED,
        )
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        result = ranked

    return {
        "min_s":  round(min(times), 4),
        "max_s":  round(max(times), 4),
        "mean_s": round(statistics.mean(times), 4),
        "std_s":  round(statistics.stdev(times) if len(times) > 1 else 0, 4),
        "top_route": result[0]["name"] if result else None,
        "top_signal": round(result[0].get("signal_score", 0), 2) if result else None,
        "confidence": result[0].get("confidence", "unknown") if result else None,
    }


# =========================================================================
# MODEL 2 -- Dead Zone Predictor (ResidualSignalNet per carrier, no MC)
#   Called by: predict_carrier_zones (parallel via asyncio after rank_routes)
#   Input: path + per-carrier tower subsets -> extract_features -> predict()
#   Output: per-carrier signal arrays, dead zone list, best carrier per point
#   Triggered SECOND in /api/routes
# =========================================================================

def bench_model2_dead_zone_predictor():
    from backend.dead_zone_predictor import predict_carrier_zones

    times_per_route = []
    times_all = []
    result = None

    for _ in range(RUNS):
        t_all_start = time.perf_counter()
        results = []
        for r in ROUTES:
            t0 = time.perf_counter()
            cz = predict_carrier_zones(
                r["path"], TOWERS_DF,
                time_hour=TIME_HOUR,
                weather_factor=WEATHER,
                speed_kmh=SPEED,
            )
            elapsed = time.perf_counter() - t0
            times_per_route.append(elapsed)
            results.append(cz)
        times_all.append(time.perf_counter() - t_all_start)
        result = results[0]

    return {
        "per_route_min_s":  round(min(times_per_route), 4),
        "per_route_max_s":  round(max(times_per_route), 4),
        "per_route_mean_s": round(statistics.mean(times_per_route), 4),
        "all_routes_mean_s": round(statistics.mean(times_all), 4),
        "dead_zones_found": len(result.get("dead_zones", [])) if result else 0,
        "carriers_checked": list(result.get("carriers", {}).keys()) if result else [],
    }


# =========================================================================
# MODEL 3 -- Bad Zone Detector (contiguous weak-signal zone detection)
#   Called by: detect_bad_zones + assess_task_feasibility
#   Input: path + segment_signals (from Model 1 output) + speed
#   Output: zone locations, arrival time, duration, edge zone warnings
#   Triggered THIRD in /api/routes (after rank_routes + dead zones)
# =========================================================================

def bench_model3_bad_zone_detector():
    from model.scoring import rank_routes
    from model.bad_zones import detect_bad_zones, assess_task_feasibility

    # First get scored routes so we have real segment_signals
    routes_copy = make_routes()
    ranked = rank_routes(
        routes_copy, TOWERS_DF,
        preference=70, telecom="all",
        time_hour=TIME_HOUR, weather_factor=WEATHER, speed_kmh=SPEED,
    )

    # Benchmark detect_bad_zones across all routes
    times_detect = []
    zones_found = 0
    for _ in range(RUNS):
        t0 = time.perf_counter()
        for r in ranked:
            conn = r.get("connectivity", {})
            zones = detect_bad_zones(
                r["path"],
                conn.get("segment_signals", []),
                avg_speed_kmh=SPEED,
            )
            zones_found = max(zones_found, len(zones))
        times_detect.append(time.perf_counter() - t0)

    # Benchmark assess_task_feasibility
    times_feasibility = []
    feasibility_result = None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        for r in ranked:
            conn = r.get("connectivity", {})
            feasibility_result = assess_task_feasibility(
                conn.get("segment_signals", []),
                task_type="meeting",
                task_duration_min=30.0,
                avg_speed_kmh=SPEED,
                total_distance_km=r.get("distance", 10.0),
            )
        times_feasibility.append(time.perf_counter() - t0)

    return {
        "detect_mean_ms": round(statistics.mean(times_detect) * 1000, 4),
        "detect_min_ms":  round(min(times_detect) * 1000, 4),
        "detect_max_ms":  round(max(times_detect) * 1000, 4),
        "feasibility_mean_ms": round(statistics.mean(times_feasibility) * 1000, 4),
        "feasibility_min_ms":  round(min(times_feasibility) * 1000, 4),
        "feasibility_max_ms":  round(max(times_feasibility) * 1000, 4),
        "bad_zones_found": zones_found,
        "feasible": feasibility_result.get("feasible") if feasibility_result else None,
        "task_type": "meeting",
    }


# =========================================================================
# MODEL 4 -- Thompson Sampling Contextual Bandit (RL)
#   Called by: /api/auto-route -> get_bandit -> bandit.select()
#   Input: user_id + context (time_hour, day_of_week, origin, dest)
#   Output: recommended intent + confidence + pattern key
#   Triggered in /api/auto-route before ranking
# =========================================================================

def bench_model4_thompson_bandit():
    from model.rl_learning import ContextualBandit

    times_cold = []
    times_warm = []

    bandit = ContextualBandit(user_id="bench_user")
    bandit.reset()  # ensure clean state
    now = datetime.datetime.now()

    context = {
        "time_hour": 8.5,
        "day_of_week": now.weekday(),
        "origin_lat": 12.9255,
        "origin_lng": 77.5468,
        "dest_lat": 12.9279,
        "dest_lng": 77.6271,
    }

    # Cold runs (no priors)
    cold_result = None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        cold_result = bandit.select(**context)
        times_cold.append(time.perf_counter() - t0)

    # Simulate 20 trips to warm up Beta distributions
    for _ in range(20):
        bandit.update(
            time_hour=8.5,
            day_of_week=now.weekday(),
            origin_lat=context["origin_lat"],
            origin_lng=context["origin_lng"],
            dest_lat=context["dest_lat"],
            dest_lng=context["dest_lng"],
            chosen_intent="meeting",
        )

    # Warm runs (with learned priors)
    warm_result = None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        warm_result = bandit.select(**context)
        times_warm.append(time.perf_counter() - t0)

    # Clean up benchmark user data
    bandit.reset()

    return {
        "cold_mean_ms": round(statistics.mean(times_cold) * 1000, 4),
        "cold_min_ms":  round(min(times_cold) * 1000, 4),
        "cold_max_ms":  round(max(times_cold) * 1000, 4),
        "warm_mean_ms": round(statistics.mean(times_warm) * 1000, 4),
        "warm_min_ms":  round(min(times_warm) * 1000, 4),
        "warm_max_ms":  round(max(times_warm) * 1000, 4),
        "cold_intent": cold_result.get("intent") if cold_result else None,
        "warm_intent": warm_result.get("intent") if warm_result else None,
        "warm_confidence": round(warm_result.get("confidence", 0), 4) if warm_result else None,
        "pattern_key": warm_result.get("pattern_key") if warm_result else None,
    }


# =========================================================================
# MODEL 5 -- Smart Preference Engine (intent -> preference resolver)
#   Called by: /api/auto-route after bandit selects intent
#   Input: user_id + intent string + time_hour
#   Output: preference weight (0-100), task_type, task_duration_min
#   Triggered in /api/auto-route after bandit
# =========================================================================

def bench_model5_smart_preference():
    from model.smart_preference import resolve_intent, get_smart_preference

    intents_to_test = ["meeting", "call", "navigation", "fastest", "download",
                       "streaming", "emergency", "work", "idle", "best_signal"]

    # Benchmark resolve_intent (rule-based, pure dict lookup)
    times_resolve = []
    resolve_results = {}
    for _ in range(RUNS * 4):
        t0 = time.perf_counter()
        for intent in intents_to_test:
            r = resolve_intent(intent)
            resolve_results[intent] = r
        times_resolve.append(time.perf_counter() - t0)

    # Benchmark get_smart_preference (includes file I/O for learned history)
    times_smart = []
    smart_result = None
    for _ in range(RUNS):
        t0 = time.perf_counter()
        smart_result = get_smart_preference(
            user_id="bench_user",
            intent="meeting",
            time_hour=TIME_HOUR,
        )
        times_smart.append(time.perf_counter() - t0)

    # Benchmark fuzzy keyword matching
    times_fuzzy = []
    fuzzy_result = None
    for _ in range(RUNS * 4):
        t0 = time.perf_counter()
        fuzzy_result = resolve_intent("I have a zoom call in 10 minutes")
        times_fuzzy.append(time.perf_counter() - t0)

    return {
        "resolve_all_intents_mean_ms": round(statistics.mean(times_resolve) * 1000, 4),
        "resolve_all_intents_min_ms":  round(min(times_resolve) * 1000, 4),
        "smart_pref_mean_ms": round(statistics.mean(times_smart) * 1000, 4),
        "smart_pref_min_ms":  round(min(times_smart) * 1000, 4),
        "smart_pref_max_ms":  round(max(times_smart) * 1000, 4),
        "fuzzy_mean_ms": round(statistics.mean(times_fuzzy) * 1000, 4),
        "fuzzy_matched_intent": fuzzy_result.get("intent") if fuzzy_result else None,
        "fuzzy_matched_keyword": fuzzy_result.get("matched_keyword") if fuzzy_result else None,
        "meeting_preference": resolve_results.get("meeting", {}).get("preference"),
        "navigation_preference": resolve_results.get("navigation", {}).get("preference"),
        "smart_source": smart_result.get("source") if smart_result else None,
        "intents_tested": len(intents_to_test),
    }


# =========================================================================
# ATOMIC INFERENCE -- Single predict_single / predict_with_uncertainty
# =========================================================================

def bench_atomic_inference():
    from model.inference import predict_single, predict_with_uncertainty
    from model.utils import extract_features

    feats = extract_features(12.9716, 77.5946, TOWERS_DF, TIME_HOUR, WEATHER, SPEED)

    times_single = []
    for _ in range(RUNS * 4):
        t0 = time.perf_counter()
        predict_single(feats)
        times_single.append(time.perf_counter() - t0)

    times_mc = []
    feats_batch = np.stack([feats] * 60)
    for _ in range(RUNS):
        t0 = time.perf_counter()
        predict_with_uncertainty(feats_batch, n_samples=5)
        times_mc.append(time.perf_counter() - t0)

    return {
        "single_mean_ms": round(statistics.mean(times_single) * 1000, 4),
        "single_min_ms":  round(min(times_single) * 1000, 4),
        "single_max_ms":  round(max(times_single) * 1000, 4),
        "mc5_batch60_mean_ms": round(statistics.mean(times_mc) * 1000, 4),
        "mc5_batch60_min_ms":  round(min(times_mc) * 1000, 4),
        "mc5_batch60_max_ms":  round(max(times_mc) * 1000, 4),
    }


# =========================================================================
# FULL END-TO-END: /api/routes pipeline simulation
# =========================================================================

def bench_end_to_end_routes():
    from model.scoring import rank_routes
    from backend.dead_zone_predictor import predict_carrier_zones
    from model.bad_zones import detect_bad_zones

    times = []

    for _ in range(RUNS):
        t0 = time.perf_counter()

        routes_copy = make_routes()

        # Step 1: rank_routes (Model 1)
        t_rank = time.perf_counter()
        ranked = rank_routes(routes_copy, TOWERS_DF, preference=70, telecom="all",
                             time_hour=TIME_HOUR, weather_factor=WEATHER, speed_kmh=SPEED)
        t_rank_elapsed = time.perf_counter() - t_rank

        # Step 2: dead zone prediction (Model 2)
        t_dz = time.perf_counter()
        for r in ranked:
            predict_carrier_zones(r["path"], TOWERS_DF,
                                  time_hour=TIME_HOUR, weather_factor=WEATHER, speed_kmh=SPEED)
        t_dz_elapsed = time.perf_counter() - t_dz

        # Step 3: bad zone detection (Model 3)
        t_bz = time.perf_counter()
        for r in ranked:
            conn = r.get("connectivity", {})
            detect_bad_zones(r["path"], conn.get("segment_signals", []), avg_speed_kmh=SPEED)
        t_bz_elapsed = time.perf_counter() - t_bz

        total = time.perf_counter() - t0
        times.append((total, t_rank_elapsed, t_dz_elapsed, t_bz_elapsed))

    totals  = [t[0] for t in times]
    ranks   = [t[1] for t in times]
    dzones  = [t[2] for t in times]
    bzones  = [t[3] for t in times]

    return {
        "total_mean_s":    round(statistics.mean(totals), 4),
        "total_min_s":     round(min(totals), 4),
        "total_max_s":     round(max(totals), 4),
        "rank_routes_mean_s": round(statistics.mean(ranks), 4),
        "dead_zones_mean_s":  round(statistics.mean(dzones), 4),
        "bad_zones_mean_s":   round(statistics.mean(bzones), 4),
        "rank_pct":  round(statistics.mean(ranks) / statistics.mean(totals) * 100, 1),
        "dz_pct":    round(statistics.mean(dzones) / statistics.mean(totals) * 100, 1),
        "bz_pct":    round(statistics.mean(bzones) / statistics.mean(totals) * 100, 1),
    }


# =========================================================================
# FULL END-TO-END: /api/auto-route pipeline simulation (all 5 models)
# =========================================================================

def bench_end_to_end_auto_route():
    from model.rl_learning import ContextualBandit
    from model.smart_preference import get_smart_preference
    from model.scoring import rank_routes
    from model.bad_zones import detect_bad_zones, assess_task_feasibility

    now = datetime.datetime.now()
    bandit = ContextualBandit(user_id="bench_e2e_user")
    bandit.reset()

    # Warm the bandit with a few trips
    for _ in range(10):
        bandit.update(
            time_hour=8.5, day_of_week=now.weekday(),
            origin_lat=12.9255, origin_lng=77.5468,
            dest_lat=12.9279, dest_lng=77.6271,
            chosen_intent="meeting",
        )

    times = []
    for _ in range(RUNS):
        t0 = time.perf_counter()

        # Step 1: Bandit selects intent (Model 4)
        t_bandit = time.perf_counter()
        rl_result = bandit.select(
            time_hour=8.5, day_of_week=now.weekday(),
            origin_lat=12.9255, origin_lng=77.5468,
            dest_lat=12.9279, dest_lng=77.6271,
        )
        t_bandit_elapsed = time.perf_counter() - t_bandit

        # Step 2: Smart preference resolves intent (Model 5)
        t_pref = time.perf_counter()
        intent = rl_result.get("intent") or "meeting"
        pref_result = get_smart_preference("bench_e2e_user", intent, TIME_HOUR)
        preference = pref_result["preference"]
        t_pref_elapsed = time.perf_counter() - t_pref

        # Step 3: Rank routes with learned preference (Model 1)
        t_rank = time.perf_counter()
        routes_copy = make_routes()
        ranked = rank_routes(routes_copy, TOWERS_DF, preference=preference, telecom="all",
                             time_hour=TIME_HOUR, weather_factor=WEATHER, speed_kmh=SPEED)
        t_rank_elapsed = time.perf_counter() - t_rank

        # Step 4: Bad zone detection + task feasibility (Model 3)
        t_bz = time.perf_counter()
        for r in ranked:
            conn = r.get("connectivity", {})
            detect_bad_zones(r["path"], conn.get("segment_signals", []), avg_speed_kmh=SPEED)
            assess_task_feasibility(
                conn.get("segment_signals", []),
                task_type=pref_result.get("task_type", "call"),
                task_duration_min=pref_result.get("task_duration_min", 10.0),
                avg_speed_kmh=SPEED,
                total_distance_km=r.get("distance", 10.0),
            )
        t_bz_elapsed = time.perf_counter() - t_bz

        total = time.perf_counter() - t0
        times.append((total, t_bandit_elapsed, t_pref_elapsed, t_rank_elapsed, t_bz_elapsed))

    bandit.reset()

    totals  = [t[0] for t in times]
    bandits = [t[1] for t in times]
    prefs   = [t[2] for t in times]
    ranks   = [t[3] for t in times]
    bzones  = [t[4] for t in times]

    return {
        "total_mean_s":       round(statistics.mean(totals), 4),
        "total_min_s":        round(min(totals), 4),
        "total_max_s":        round(max(totals), 4),
        "bandit_mean_ms":     round(statistics.mean(bandits) * 1000, 4),
        "smart_pref_mean_ms": round(statistics.mean(prefs) * 1000, 4),
        "rank_routes_mean_s": round(statistics.mean(ranks), 4),
        "bad_zones_mean_ms":  round(statistics.mean(bzones) * 1000, 4),
    }


# =========================================================================
# Run all benchmarks
# =========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print(" MODEL EXECUTION ORDER & TIMING BENCHMARK")
    print(f" Runs per test: {RUNS}   Routes: {N_ROUTES}   Path points: {PATH_LEN}")
    print("=" * 70)

    results = {}

    # --- Model 1 ---
    print("\n[1/7] Model 1: ResidualSignalNet (MC Dropout) -- rank_routes ...")
    r1 = bench_model1_residual_signal_net()
    results["model1_residual_signal_net"] = r1
    print(f"      mean={r1['mean_s']}s  min={r1['min_s']}s  max={r1['max_s']}s")
    print(f"      top_route={r1['top_route']}  signal={r1['top_signal']}  confidence={r1['confidence']}")

    # --- Model 2 ---
    print("\n[2/7] Model 2: Dead Zone Predictor -- predict_carrier_zones ...")
    r2 = bench_model2_dead_zone_predictor()
    results["model2_dead_zone_predictor"] = r2
    print(f"      per-route mean={r2['per_route_mean_s']}s  all-routes mean={r2['all_routes_mean_s']}s")
    print(f"      carriers={r2['carriers_checked']}  dead_zones={r2['dead_zones_found']}")

    # --- Model 3 ---
    print("\n[3/7] Model 3: Bad Zone Detector -- detect_bad_zones ...")
    r3 = bench_model3_bad_zone_detector()
    results["model3_bad_zone_detector"] = r3
    print(f"      detect mean={r3['detect_mean_ms']}ms  feasibility mean={r3['feasibility_mean_ms']}ms")
    print(f"      bad_zones_found={r3['bad_zones_found']}  meeting_feasible={r3['feasible']}")

    # --- Model 4 ---
    print("\n[4/7] Model 4: Thompson Sampling Bandit (RL) -- select ...")
    r4 = bench_model4_thompson_bandit()
    results["model4_thompson_bandit"] = r4
    print(f"      cold mean={r4['cold_mean_ms']}ms  warm mean={r4['warm_mean_ms']}ms")
    print(f"      cold_intent={r4['cold_intent']}  warm_intent={r4['warm_intent']}")
    print(f"      confidence={r4['warm_confidence']}  pattern={r4['pattern_key']}")

    # --- Model 5 ---
    print("\n[5/7] Model 5: Smart Preference Engine -- resolve_intent ...")
    r5 = bench_model5_smart_preference()
    results["model5_smart_preference"] = r5
    print(f"      resolve 10 intents mean={r5['resolve_all_intents_mean_ms']}ms")
    print(f"      smart_pref mean={r5['smart_pref_mean_ms']}ms  source={r5['smart_source']}")
    print(f"      fuzzy '{r5['fuzzy_matched_keyword']}' -> {r5['fuzzy_matched_intent']}")
    print(f"      meeting={r5['meeting_preference']}  navigation={r5['navigation_preference']}")

    # --- Atomic ---
    print("\n[6/7] Atomic inference: predict_single & predict_with_uncertainty ...")
    r6 = bench_atomic_inference()
    results["atomic_inference"] = r6
    print(f"      single mean={r6['single_mean_ms']}ms  MC-5/batch-60 mean={r6['mc5_batch60_mean_ms']}ms")

    # --- End-to-end /api/routes ---
    print("\n[7/7] Full end-to-end pipelines ...")
    print("  [7a] /api/routes (Models 1+2+3) ...")
    r7a = bench_end_to_end_routes()
    results["end_to_end_routes"] = r7a
    print(f"       total={r7a['total_mean_s']}s  (rank={r7a['rank_pct']}%  dz={r7a['dz_pct']}%  bz={r7a['bz_pct']}%)")

    print("  [7b] /api/auto-route (all 5 models) ...")
    r7b = bench_end_to_end_auto_route()
    results["end_to_end_auto_route"] = r7b
    print(f"       total={r7b['total_mean_s']}s  bandit={r7b['bandit_mean_ms']}ms  pref={r7b['smart_pref_mean_ms']}ms")
    print(f"       rank={r7b['rank_routes_mean_s']}s  bad_zones={r7b['bad_zones_mean_ms']}ms")

    print("\n" + "=" * 70)
    print(" COMPLETE RESULTS")
    print("=" * 70)
    print(json.dumps(results, indent=2))
    print("=" * 70)
