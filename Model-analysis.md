# Model Analysis -- Signal-Aware Navigation

> Benchmark environment: Windows 11, NVIDIA GPU (CUDA), PyTorch 2.x  
> Test scenario: 5 routes x 120 path points, morning commute (08:30), 5 runs averaged  
> Benchmark script: `model/benchmark_execution_order.py`

---

## Five ML Models

The application uses five distinct ML models across two API pipelines:

### `/api/routes` pipeline (standard search):
1. **ResidualSignalNet** (MC Dropout) -- neural network signal/drop/handoff prediction
2. **Dead Zone Predictor** -- per-carrier signal prediction to find complete dead zones
3. **Bad Zone Detector** -- contiguous weak-signal zone detection + task feasibility

### `/api/auto-route` pipeline (RL-powered smart routing):
4. **Thompson Sampling Bandit** (RL) -- learns user intent from trip history
5. **Smart Preference Engine** -- maps intent to preference weight + user profile learning

---

## Model Execution Order

### /api/routes pipeline

```
Request received (/api/routes)
      |
      v
[MODEL 1] ResidualSignalNet (MC Dropout)           <-- FIRST
  rank_routes() -> score_route() -> predict_with_uncertainty()
  5 routes scored in parallel (ThreadPoolExecutor)
      |  ranked routes + connectivity scores
      v
[MODEL 2] Dead Zone Predictor                       <-- SECOND
  predict_carrier_zones() per route (asyncio parallel)
  4 carriers (Jio/Airtel/Vi/BSNL) x predict() per route
      |  dead zones + carrier summaries
      v
[MODEL 3] Bad Zone Detector                         <-- THIRD
  detect_bad_zones() + offline_cache_alerts()
  Contiguous weak-signal zones from Model 1 output
      |
      v
  Response returned
```

### /api/auto-route pipeline

```
Request received (/api/auto-route)
      |
      v
[MODEL 4] Thompson Sampling Bandit (RL)             <-- FIRST
  ContextualBandit.select() -> recommended intent
      |  intent (e.g. "meeting")
      v
[MODEL 5] Smart Preference Engine                   <-- SECOND
  get_smart_preference() -> preference weight (0-100)
      |  preference = 85 (for "meeting")
      v
[MODEL 1] ResidualSignalNet (MC Dropout)            <-- THIRD
  rank_routes() with learned preference
      |  ranked routes
      v
[MODEL 3] Bad Zone Detector                         <-- FOURTH
  detect_bad_zones() + assess_task_feasibility()
      |
      v
  Response returned with RL explanation
```

---

## Model 1 -- ResidualSignalNet (MC Dropout)

**File:** `model/inference.py`, `model/architecture.py`  
**Called by:** `model/scoring.py` -> `rank_routes()` -> `score_route()` -> `predict_with_uncertainty()`

**What it does:** Predicts signal strength, call-drop probability, and handoff risk for every sampled point along each candidate route. Monte Carlo Dropout runs the model N times with dropout active to produce uncertainty estimates alongside mean predictions.

**Architecture:**
- Input: 22-dimensional feature vector per point (tower distances, signal, terrain, time, weather, radio type, traffic)
- Backbone: 4x ResidualBlock (256-dim) with SiLU activations and BatchNorm
- Bottleneck: 64-dim projection
- 3 output heads: signal_strength (0-100), drop_probability (0-1), handoff_risk (0-1)
- Parameters: ~200K (lightweight, runs on GPU and CPU)
- Weights: `model/weights/best_model.pt` (2.29 MB)

**Parallelism:** 5 routes scored simultaneously via `ThreadPoolExecutor`  
**Path sampling:** Capped at 60 points per route (down-sampled from up to 200+ TomTom points)  
**MC samples:** 5 stochastic forward passes per batch

### Execution Times

| Metric | Time |
|--------|------|
| Mean (5 routes parallel) | **0.2193 s** |
| Minimum | 0.1509 s |
| Maximum (includes cold GPU load) | 0.4876 s |
| Std deviation | 0.15 s |
| Single predict_single() | 6.76 ms |
| Batch predict_with_uncertainty (60 pts x 5 MC) | **27.31 ms** |
| Share of /api/routes pipeline | **21.8%** |

**Output:**
- top_route: Route 1, signal_score: 38.4, confidence: high

---

## Model 2 -- Dead Zone Predictor

**File:** `backend/dead_zone_predictor.py`  
**Called by:** `predict_carrier_zones()` in `/api/routes`

**What it does:** Runs signal prediction separately for each carrier (Jio, Airtel, Vi, BSNL) along the full route path without MC Dropout. Identifies stretches where ALL carriers score below 30 (complete dead zones). Also generates offline cache alerts and call-drop estimates.

**Carriers checked:** Jio, Airtel, Vi, BSNL (4 carriers x full path per route = 4 forward passes per route)

**When it runs:** After `rank_routes()` completes, in parallel across all 5 routes via `asyncio.gather` + executor thread pool. Uses `predict()` (deterministic, no MC) for speed.

**Key thresholds:**
- Dead zone: all carriers < 30 signal
- Offline alert: dead zone within 5 minutes of travel at current speed

### Execution Times

| Metric | Time |
|--------|------|
| Per-route mean | **201.7 ms** |
| Per-route minimum | 77.2 ms |
| Per-route maximum | 259.7 ms |
| All 5 routes sequential | 1008.3 ms |
| Dead zones found (test routes) | **4 zones** |
| Share of /api/routes pipeline | **78.0%** |

> In production the backend runs all 5 routes in parallel via `asyncio.gather`, so the effective wall-clock cost is ~1 route (~200 ms) not 5x sequential.

---

## Model 3 -- Bad Zone Detector

**File:** `model/bad_zones.py`  
**Called by:** `detect_bad_zones()` + `assess_task_feasibility()` in both `/api/routes` and `/api/auto-route`

**What it does:** Finds contiguous stretches of weak signal along a route and estimates arrival time, zone duration, and edge zone warnings. Also checks whether connectivity-dependent tasks (call, meeting, download) can be completed on the route.

**Input:** Path coordinates + segment_signals array from Model 1 output  
**Output:** Zone locations (start/end coords), length_km, time_to_zone_min, zone_duration_min, warning messages, task feasibility verdict

**Key thresholds:**
- Bad zone: signal below `BAD_ZONE_THRESHOLD` (configurable)
- Meeting feasibility: continuous signal > 60 for task_duration_min
- Call feasibility: continuous signal > 40 for task_duration_min
- Download feasibility: average signal > 50

### Execution Times

| Metric | Time |
|--------|------|
| detect_bad_zones (5 routes) mean | **2.00 ms** |
| detect_bad_zones min | 1.29 ms |
| detect_bad_zones max | 2.41 ms |
| assess_task_feasibility (5 routes) mean | **0.036 ms** |
| assess_task_feasibility min | 0.033 ms |
| Bad zones found | **5 zones** |
| Meeting feasible (test route) | **No** |
| Share of /api/routes pipeline | **0.1%** |

> This model is pure NumPy/Python arithmetic over Model 1's output. No GPU needed, no neural network inference.

---

## Model 4 -- Thompson Sampling Contextual Bandit (RL)

**File:** `model/rl_learning.py`  
**Class:** `ContextualBandit`  
**Called by:** `bandit.select()` in `/api/auto-route`

**What it does:** Reinforcement learning model that learns per-user route intent preferences over time. Maintains Beta distributions for each `(time_bucket, day_type, origin_zone, dest_zone)` context key. Uses Thompson Sampling to choose the most likely intent (meeting, call, navigation, fastest, download, streaming, emergency, work, idle, best_signal).

**Context dimensions:**
- Time bucket: 8 slots (early_morning, morning_commute, late_morning, midday, afternoon, evening_commute, evening, night)
- Day type: weekday / weekend
- Origin zone: nearest of 25 Bangalore zones
- Destination zone: nearest of 25 Bangalore zones

**Learning:** `bandit.update()` updates Beta(a, b) parameters -- a += 1 on success, b += 1 on override. After `MIN_OBS` (3) observations the bandit auto-selects intents.

**Persistence:** File-backed per user (`model/data/rl_profiles/{user_id}.json`)

### Execution Times

| Metric | Time |
|--------|------|
| Cold start (no prior data) mean | **0.046 ms** |
| Cold start min / max | 0.029 / 0.095 ms |
| Warm (20 learned trips) mean | **0.255 ms** |
| Warm min / max | 0.042 / 1.091 ms |
| Cold selected intent | None (insufficient data) |
| Warm selected intent | **meeting** |
| Warm confidence | **0.997** |
| Pattern key | morning_commute\|weekend\|Banashankari\|Koramangala |

> The bandit is essentially instant -- Beta distribution sampling via NumPy is pure arithmetic. CPU-only, no GPU needed. The warm time increase vs cold is due to file I/O for loading learned Beta parameters.

---

## Model 5 -- Smart Preference Engine

**File:** `model/smart_preference.py`  
**Called by:** `resolve_intent()` / `get_smart_preference()` in `/api/auto-route`

**What it does:** Maps intent strings to preference weights (0-100), task types, and duration. Supports exact intent matching (10 predefined intents), fuzzy keyword matching (e.g. "I have a zoom call" -> meeting), and learned user history (file-backed profiles that track past choices per time bucket).

**10 Intent Profiles:**

| Intent | Preference | Task Type | Duration |
|--------|-----------|-----------|----------|
| meeting | 85 | meeting | 30 min |
| call | 60 | call | 10 min |
| navigation | 10 | call | 0 min |
| fastest | 0 | call | 0 min |
| download | 70 | download | 5 min |
| streaming | 75 | download | 15 min |
| emergency | 0 | call | 0 min |
| work | 65 | call | 10 min |
| idle | 30 | call | 0 min |
| best_signal | 100 | meeting | 0 min |

**Learning:** `record_choice()` stores user choices. After 3+ data points, `get_smart_preference()` overrides default mapping with per-user learned preferences by (intent, time_bucket).

### Execution Times

| Metric | Time |
|--------|------|
| resolve_intent (all 10 intents) mean | **0.009 ms** |
| get_smart_preference (with file I/O) mean | **0.417 ms** |
| get_smart_preference min / max | 0.301 / 0.526 ms |
| Fuzzy keyword match ("zoom" -> meeting) | **0.002 ms** |
| Source (cold user) | exact_match |

> Pure Python dict/keyword lookup. No ML inference, no GPU. The file I/O for learned history adds ~0.3 ms.

---

## Atomic Inference (ResidualSignalNet internals)

| Metric | Time |
|--------|------|
| Single point predict_single() | **6.76 ms** |
| Single point min / max | 3.51 / 11.59 ms |
| MC Dropout batch (60 pts x 5 passes) | **27.31 ms** |
| MC batch min / max | 22.79 / 30.18 ms |

---

## End-to-End Pipeline Timings

### /api/routes (Models 1 + 2 + 3)

| Stage | Mean Time | % of Total |
|-------|-----------|------------|
| Model 1: ResidualSignalNet (rank_routes) | 303.8 ms | 21.8% |
| Model 2: Dead Zone Predictor (5 routes seq.) | 1085.8 ms | 78.0% |
| Model 3: Bad Zone Detector | 2.0 ms | 0.1% |
| **Total** | **1391.7 ms** | 100% |

> With asyncio parallelisation of dead zone prediction (as in production), effective total drops to ~500-600 ms.

### /api/auto-route (All 5 models)

| Stage | Mean Time |
|-------|-----------|
| Model 4: Thompson Bandit (select) | 0.15 ms |
| Model 5: Smart Preference (resolve) | 0.30 ms |
| Model 1: ResidualSignalNet (rank_routes) | 300.4 ms |
| Model 3: Bad Zone Detector + feasibility | 2.43 ms |
| **Total** | **303.3 ms** |

> The auto-route pipeline skips Model 2 (Dead Zone Predictor) and is therefore faster than the standard /api/routes pipeline.

---

## Summary Table

| Order in /api/routes | Order in /api/auto-route | Model | Mean Time | Device |
|---------------------|-------------------------|-------|-----------|--------|
| 1st | 3rd | ResidualSignalNet (MC Dropout) | **219 ms** (5 routes parallel) | CUDA GPU |
| 2nd | -- | Dead Zone Predictor | **202 ms** per route | CUDA GPU |
| 3rd | 4th | Bad Zone Detector | **2.0 ms** (5 routes) | CPU |
| -- | 1st | Thompson Sampling Bandit (RL) | **0.046 ms** cold / **0.255 ms** warm | CPU |
| -- | 2nd | Smart Preference Engine | **0.417 ms** | CPU |

---

## Notes

- Model 1 uses MC Dropout (5 passes) for uncertainty -- disabling MC and using predict() would cut time ~40% but loses confidence scores
- Model 2 dominates /api/routes time because it runs 4 carriers x path_length feature extractions per route; the asyncio parallelisation is critical for production latency
- Model 3 is pure arithmetic over Model 1 output (no neural network) and never a bottleneck
- Models 4 and 5 are CPU-only (Beta sampling + dict lookup) and contribute < 1 ms combined to /api/auto-route
- All neural network models (1 and 2) share the same ResidualSignalNet weights (`model/weights/best_model.pt`, 2.29 MB)
- GPU first-call overhead (~200 ms) is a one-time model load cost; subsequent calls use the cached singleton
- The Thompson Bandit learns after 3 observations per context pattern and achieves 0.997 confidence after 20 trips
