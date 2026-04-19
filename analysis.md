# SignalRoute: Cellular Network-Aware Routing for Connected Vehicles

---

## Project Name

**SignalRoute** -- Cellular Network-Aware Routing

---

## One-Line Project Pitch

An ML-powered routing engine that scores road routes by predicted cellular signal quality, enabling connected vehicles to proactively avoid dead zones before they happen.

---

## Problem Statement

Connected vehicles rely on continuous cellular data for navigation, OTA updates, emergency calls, and in-car streaming. Existing routing engines (Google Maps, Waze) optimise purely for time or distance -- they are completely blind to network conditions. A driver following the fastest route can lose signal mid-call, miss a critical OTA update window, or find that a scheduled Zoom meeting is impossible to complete while in transit.

The problem: **no commercial routing system today factors real-time or predicted cellular signal quality into route selection.** This is especially acute in dense urban environments like Bangalore where coverage varies dramatically by zone, tower load, and time of day.

---

## Target Users

- Vehicle fleet operators requiring guaranteed connectivity SLAs
- Commuters with recurring high-bandwidth tasks (video calls, downloads)
- L4 autonomous vehicle systems that need continuous data uplink
- Any connected-vehicle user on the HARMAN or similar automotive platform

---

## Your Role (Exact Responsibilities)

Built the entire ML backend from scratch as the model engineer:

- Designed and implemented the radio propagation physics engine
- Synthetic dataset generation (100,000 labelled samples, 500 towers)
- Model architecture design, GPU training, and evaluation
- REST API server with 39 endpoints across 3 route groups
- Smart preference / intent resolution engine
- Reinforcement learning pattern recognition system
- Backend integration bridging the ML model to the frontend

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML Model | PyTorch 2.11.0 + CUDA 13.0 |
| API Server | FastAPI 0.111.0 + Uvicorn 0.30.1 |
| Data Processing | NumPy, Pandas, scikit-learn |
| Frontend | Next.js 16.2.4, React 19, TypeScript |
| Maps | Mapbox GL JS (premium layered rendering) |
| Charts | Chart.js + react-chartjs-2 |
| Styling | Tailwind CSS v4 |
| HTTP Client | Axios |
| Animation | Framer Motion |
| Language | Python 3.11 (backend), TypeScript 5 (frontend) |

---

## Reason for Choosing the Tech Stack

**PyTorch**: Native CUDA support enabled GPU-accelerated training on the RTX 5050. Mixed-precision (torch.amp) halved training memory with no accuracy loss. The dynamic computation graph simplified rapid architecture iteration.

**FastAPI**: Automatic Pydantic validation, async-capable, OpenAPI docs generated for free. All-PUT endpoint design was required for ngrok tunnel compatibility (ngrok free tier blocks non-PUT HTTP methods inconsistently on some NAT setups).

**Next.js / React 19**: The frontend teammate's choice. The `src/app` directory structure and server/client component split made it straightforward to keep map rendering client-only (Mapbox GL JS requires `window`, loaded via `next/dynamic` with `ssr: false`).

**Mapbox GL JS**: Chosen over Leaflet for WebGL-accelerated vector tile rendering, native GeoJSON LineString support, layered line styling (glow/casing/main for premium route visuals), smooth camera transitions, and pitch/bearing 3D support. Routes render with 200-300+ geometry points from TomTom, following real roads precisely.

**Thompson Sampling (RL)**: Chosen over deep RL (DQN, PPO) because the problem has a small discrete action space (10 intents) and sparse rewards. Thompson Sampling provides principled uncertainty quantification with essentially zero training cost, converges in 3-5 observations, and is fully interpretable.

---

## High-Level System Architecture

```
[Vehicle / Browser]
       |
       | HTTP (localhost:8000)
       v
[Backend FastAPI Server]
   backend/main.py
       |
       |--- /api/*  (GET/POST)  -- Frontend UI endpoints
       |--- /model/* (PUT)      -- ML model + RL endpoints
       |
   model/
       |--- inference.py        -- ResidualSignalNet singleton
       |--- scoring.py          -- Route scoring engine
       |--- bad_zones.py        -- Dead zone detector
       |--- smart_preference.py -- Intent -> preference mapping
       |--- rl_learning.py      -- Contextual Bandit (Thompson Sampling)
       |--- propagation.py      -- COST-231 Hata + Ericsson 9999 physics
       |
   model/data/
       |--- towers.csv          -- 500 synthetic Bangalore towers
       |--- rl_profiles/        -- Per-user Beta distribution state
       |--- user_profiles.json  -- Legacy preference learning
```

---

## Data Flow (Client -> Server -> Model)

```
1. Browser calls GET /api/routes?source=MIT&destination=Airport&preference=50

2. backend/main.py resolves location names to (lat,lng) coordinates

3. _generate_routes() creates 3 candidate route paths (Fastest, Balanced, Best Signal)
   using zone geography and interpolated waypoints

4. rank_routes() calls score_route() per route:
     a. For each path segment, extract_features() builds a 22-dim feature vector:
        [dist_nearest, dist_2nd, dist_3rd, towers_500m, towers_1km, towers_2km,
         nearest_sig, max_sig_nearby, avg_sig_nearby, freq_norm, road_type,
         time_cos, time_sin, weather, speed_norm, nearest_raw_sig, load_factor,
         radio_gen, range_norm, sample_count, radio_diversity, terrain_type]
     b. MC Dropout inference (8 forward passes) -> (signal_score, drop_prob, handoff_risk) + uncertainty
     c. Physics validation: received_signal_dbm() using COST-231 Hata +
        Ericsson 9999 ensemble (55/45 weight) + ITU-R P.1238 structure loss

5. Routes ranked by weighted_score = signal_w * sig_norm + time_w * eta_norm
   with penalties for dead zones, single-tower dependency, low continuity

6. Response returns route list + recommended_route name

7. Frontend renders paths on Mapbox GL JS map with layered styling (glow + casing + main line)
```

For RL auto-routing:

```
1. PUT /model/auto-route with {user_id, origin, destination, time_hour, day_of_week}

2. ContextualBandit.select() checks distributions for pattern key:
   morning_commute|weekday|Jayanagar|Koramangala

3. If confident (>55% Thompson sample), returns learned intent (e.g. "meeting")

4. SmartPreference maps intent -> preference value (0-100)

5. Scoring proceeds as above with the resolved preference

6. After trip, PUT /model/record-trip updates Beta distributions:
   alpha += 1 for chosen intent, beta += 1 for rejected recommendation
```

---

## Core Features (Top 3)

### 1. Physics-Based Signal Prediction

Every route segment is scored using an ensemble of real-world propagation models:
- **COST-231 Hata** (55% weight): Urban macro-cell loss, frequency-dependent
- **Ericsson 9999** (45% weight): Empirical correction for suburban/highway terrain
- **ITU-R P.1238**: Building penetration and floor attenuation loss
- Rain attenuation (ITU-R P.838) and shadow fading (log-normal, sigma=8dB)

The ResidualSignalNet (560,259 parameters) learns residuals on top of these physics priors, achieving R2=0.8978 on held-out test data.

### 2. Dead Zone Detection and Task Feasibility

`detect_bad_zones()` identifies contiguous route segments where signal drops below 30 (configurable threshold `BAD_ZONE_THRESHOLD` in config.py). For each zone it reports: GPS coordinates, duration in minutes, distance in km, and proximity to the zone. `assess_task_feasibility()` then asks: "Can I complete a 30-minute Zoom call on this route?" and answers with the longest stable connectivity window vs. required duration.

### 3. RL-Powered Intent Learning per User

The contextual bandit maintains independent Beta(alpha, beta) distributions per `(user_id, time_bucket, day_type, origin_zone, dest_zone)` pattern. This naturally handles the multi-user scenario: son drives 7:30 AM Jayanagar->Koramangala daily (learns "meeting", preference=85), dad drives 10:00 AM same route (learns "navigation", preference=10). Same origin/destination, different time = different patterns = independent learning with no interference.

---

## Model Architecture: SignalNet

The signal prediction model is a multi-task residual MLP defined in `model/architecture.py`.

### Network Topology

```
Input (22 features)
  |
  Linear(22 -> 256) + SiLU    [Projection layer]
  |
  ResidualBlock x4 (256)       [Pre-activation: BN -> SiLU -> Linear -> BN -> SiLU -> Linear + skip]
  |
  Linear(256 -> 64) + SiLU     [Bottleneck]
  |
  +-- TaskHead -> signal_strength   (sigmoid, 0-1 scaled to 0-100)
  +-- TaskHead -> drop_probability  (sigmoid, 0-1)
  +-- TaskHead -> handoff_risk      (sigmoid, 0-1)
```

### Hyperparameters (model/config.py)

| Parameter | Value |
|---|---|
| INPUT_DIM | 22 |
| HIDDEN_DIM | 256 |
| RESIDUAL_BLOCKS | 4 |
| BOTTLENECK_DIM | 64 |
| HEAD_HIDDEN | 32 |
| DROPOUT | 0.12 |
| Total parameters | 560,259 |
| Checkpoint size | 2.2 MB |

### Training Configuration

| Setting | Value |
|---|---|
| Optimizer | AdamW (lr=3e-4, weight_decay=1e-5) |
| Scheduler | Cosine warmup (10 warmup epochs + cosine decay) |
| Batch size | 1024 |
| Max epochs | 300 (early stop at epoch 101, best at epoch 66) |
| Early stop patience | 35 epochs |
| Gradient clipping | max_norm=1.0 |
| Label smoothing | eps=0.02 |
| Mixed precision | float16 forward pass, float32 loss (AMP) |

### Multi-Task Loss

```
L = 1.0 * MSE(signal_pred, signal_true)
  + 0.6 * BCE(drop_pred, drop_true)
  + 0.4 * BCE(handoff_pred, handoff_true)
```

BCE losses are computed outside `torch.amp.autocast` to avoid float16 numerical instability (NaN gradients from log-sigmoid underflow).

### 22-Dimensional Input Feature Vector

| Index | Feature | Source |
|---|---|---|
| 0 | Distance to nearest tower (km) | Haversine from path point to closest tower |
| 1 | Distance to 2nd nearest tower (km) | Haversine |
| 2 | Distance to 3rd nearest tower (km) | Haversine |
| 3 | Number of towers within 500m | Spatial query |
| 4 | Number of towers within 1km | Spatial query |
| 5 | Number of towers within 2km | Spatial query |
| 6 | Signal score of nearest tower (norm) | Tower database |
| 7 | Max signal score nearby (norm) | Tower database |
| 8 | Average signal score nearby (norm) | Tower database |
| 9 | Frequency of nearest tower (norm) | Tower database |
| 10 | Road type / terrain code | Zone configuration |
| 11 | Time cosine (cos(2*pi*hour/24)) | Request time |
| 12 | Time sine (sin(2*pi*hour/24)) | Request time |
| 13 | Weather factor (0-1) | OpenWeather API |
| 14 | Speed (normalised, /120 km/h) | Route segment estimate |
| 15 | Nearest tower signal (raw norm) | Tower database |
| 16 | Tower load factor | Time-of-day simulation |
| 17 | Radio generation encoding | Tower database (GSM=0.2, LTE=0.6, NR=0.8) |
| 18 | Nearest tower range (normalised) | Tower database |
| 19 | Nearest tower sample count (log-norm) | Tower database / OpenCelliD |
| 20 | Radio type diversity (normalised) | Tower database |
| 21 | Terrain type code | Zone configuration |

### Route Scoring Pipeline (model/scoring.py)

`score_route()` processes each route path segment:
1. For each segment point, `extract_features()` builds a 22-dim vector using the tower database, time, weather, and terrain
2. The feature vector is passed through SignalNet with MC Dropout (8 forward passes) -> (signal, drop_prob, handoff_risk) + uncertainty estimates
3. Physics validation cross-checks against COST-231 Hata + Ericsson 9999 ensemble
4. Aggregate metrics computed: mean signal, mean drop probability, signal variance, dead zone count, continuity score, drops per km, confidence level, stability score

`rank_routes()` scores all candidate routes and ranks by:
```
weighted_score = preference * signal_norm + (1 - preference) * eta_norm
```
With penalties for:
- Drop segments > 3 (-10 pts)
- Max drop probability > 0.7 (-5 pts)
- Single-tower dependency ratio > 0.4 (-5 pts)
- Low avg connectivity < BAD_ZONE_THRESHOLD (-15 pts)
- High signal variance > 400 (-5 pts)
- Drops per km > 2.0 (-8 pts) or > 1.0 (-4 pts)
- Low MC Dropout confidence (-7 pts)
- All thresholds and penalties are centralised in `model/config.py`

### Test Results

| Metric | Value |
|---|---|
| Signal MAE | 7.42% |
| Signal RMSE | 10.50% |
| Signal R2 | 0.8978 |
| Drop probability accuracy | 91.1% |
| Drop precision / recall / F1 | 87.6% / 85.9% / 86.8% |
| Handoff risk accuracy | 96.8% |
| Handoff precision / recall / F1 | 97.1% / 96.8% / 96.9% |
| Bad-zone detection F1 | 89.7% |
| Drop calibration ECE | 0.0141 |
| Final val_loss | 0.41212 (best at epoch 66) |
| Stopped at epoch | 101 / 300 (early stop, patience=35) |

#### Per-Bucket Signal Accuracy

| Bucket | Samples | MAE | RMSE |
|---|---|---|---|
| Dead (0-15%) | 3,465 | 5.44% | 8.82% |
| Poor (15-35%) | 2,717 | 9.36% | 13.30% |
| Fair (35-55%) | 2,276 | 9.19% | 11.73% |
| Good (55-75%) | 1,351 | 8.94% | 10.96% |
| Great (75-100%) | 2,332 | 5.49% | 6.97% |

#### Edge-Zone Analysis

Edge zones (tunnels, underpasses, urban canyons) have higher error due to extreme signal attenuation:
- Samples: 1,161 | MAE: 17.46% | RMSE: 22.06%
- Mean actual: 49.3% | Mean predicted: 64.0% (model overestimates in edge zones)

#### MC Dropout Uncertainty Quantification

The model uses MC Dropout (8 forward passes with dropout active, BatchNorm kept in eval mode) to estimate prediction uncertainty. Confidence levels:
- **High**: avg uncertainty < 3.0 and > 80% of segments have low uncertainty
- **Medium**: avg uncertainty < 8.0 and > 50% of segments have low uncertainty  
- **Low**: otherwise

#### Geo-Spatial Cross-Validation

Training uses tile-based spatial splitting (~2.2 km tiles, TILE_SIZE=0.02 degrees) to prevent data leakage between geographically adjacent samples. 471 tiles are divided into train/val/test (70/15/15). Falls back to random split if lat/lng columns are missing.

---

## Two-Phase Loading Architecture

The frontend uses a two-phase loading pattern to show routes instantly while ML scoring runs in the background.

### Phase 1: Fast Routes (~2-3 seconds)

`GET /api/routes/fast` returns TomTom-routed paths with heuristic signal scores:
- TomTom provides up to 7 road-snapped alternative routes
- Signal scores are computed using zone density + terrain heuristics (no ML inference, no tower API calls)
- Heuristic scoring: `density_score = {"high": 75, "medium": 55, "low": 35}` + `terrain_bonus = {"urban_main": 10, "residential": 5, "suburban": 0, "highway": -5}`
- Routes are tagged (fastest, best_signal, best_overall) and sorted by weighted score
- Frontend shows routes immediately with these scores

### Phase 2: Full ML Scoring (~15-60 seconds)

`GET /api/routes` runs the complete pipeline:
- TomTom routing + OpenCelliD tower fetch + ResidualSignalNet inference + weather + traffic flow
- When results arrive, frontend replaces the heuristic scores with ML scores
- A pulsing indicator shows "Running ML models..." during this phase

### Frontend Implementation

React Query manages both phases independently:
- `useFastRoutes()`: staleTime 60s, retry 1 -- fires immediately
- `useRoutes()`: staleTime 30s, retry 1 -- fires in parallel, results replace fast data when ready
- `displayRoutes` is a `useMemo` that maps fast routes to the full RouteOption shape until ML data arrives
- Route intent toggle ("speed" | "signal") controls sorting preference

---

## Mapbox GL JS Route Rendering

The map uses Mapbox GL JS with WebGL-accelerated vector tile rendering, replacing the earlier Leaflet implementation.

### Layered Route Styling

Each selected route renders with 3 GeoJSON layers for a premium appearance:
1. **Glow layer**: width 18, opacity 0.12, blur 10 -- soft ambient highlight
2. **Casing layer**: dark color (#1e3a5f), width 9, opacity 0.35 -- depth/shadow effect
3. **Main line**: route color, width 5, opacity 1 -- the visible route path

Alternative (unselected) routes render with dashed lines at 50% opacity and respond to hover (popup with route name/ETA) and click (route selection).

### Map Features

- Draggable A/B pin markers with `dragend` events that fire `onPinDrag` for live rerouting
- Tower dot markers color-coded by operator (Jio=blue, Airtel=red, Vi=yellow, BSNL=green)
- Smooth camera flyTo with padding and pitch adjustments on route change
- User location marker with heading indicator
- Tracking position marker with CSS pulse animation

---

## APIs Created

### Frontend Endpoints (GET/POST /api/*)

| Method | Path | Description |
|---|---|---|
| GET | /api/routes/fast | Fast route geometry from TomTom, no ML scoring |
| GET | /api/routes | Full route scoring with ML, towers, weather, dead zones |
| GET | /api/heatmap | Multi-layer heatmap data (signal/traffic) for Bangalore zones |
| GET | /api/weather | Current weather conditions + signal impact factor |
| GET | /api/alerts | Active congestion/crowd alerts near user position |
| GET | /api/traffic-flow | Real-time TomTom traffic flow for a road point |
| GET | /api/incidents | TomTom traffic incidents in a bounding box |
| GET | /api/dead-zones | Predict dead zones per carrier along a route |
| GET | /api/predict | Short-horizon signal prediction for a zone |
| POST | /api/reroute | Reroute with signal bias when dead zone detected |
| GET | /api/geocode | Forward geocoding via Nominatim |
| GET | /api/reverse-geocode | Reverse geocoding via Nominatim |
| GET | /api/towers | Tower data summary (count, operators, source) |
| GET | /api/towers/geo | Individual tower lat/lng for map rendering |
| GET | /api/offline-bundle | Pre-computed offline navigation bundle |
| GET | /api/detect-network | ISP/carrier detection from client IP |
| GET | /api/network-strength | Signal strength estimate for current user |
| GET | /api/services/health | Health check for all internal services |

### Model Endpoints (PUT /model/*)

| Method | Path | Description |
|---|---|---|
| PUT | /model/score-routes | Score candidate routes with ML model |
| PUT | /model/predict-signal | Predict signal strength at a point |
| PUT | /model/analyze-route | Analyze route connectivity with bad zones |
| PUT | /model/detect-zones | Detect edge-case zones along a route |
| PUT | /model/health | Model status and training metadata |
| PUT | /model/smart-route | Smart routing with user intent resolution |
| PUT | /model/record-choice | Record route choice for preference learning |
| PUT | /model/resolve-intent | Resolve text intent to preference value |
| PUT | /model/auto-route | RL-powered routing (pattern recognition) |
| PUT | /model/record-trip | Update RL distributions after trip |
| PUT | /model/user-patterns | View learned RL patterns for a user |
| PUT | /model/refresh-towers | Fetch fresh tower data from OpenCelliD API |

### Auth Endpoints (/api/v1/*)

| Method | Path | Description |
|---|---|---|
| POST | /api/v1/login | JWT login (in-memory or MongoDB-backed) |
| POST | /api/v1/register | User registration |
| GET | /api/v1/me | Get current user profile from JWT |
| GET | /api/v1/health | Service health check |
| POST | /api/v1/route | MongoDB-backed ranked route generation |
| POST | /api/v1/rl/update | Record route outcome for RL profile update |

---

## Database Schema / Models

No relational database. All state is file-backed JSON for hackathon simplicity.

**model/data/towers.csv** -- Tower registry
```
tower_id, lat, lng, zone, operator, signal_score, frequency_mhz,
tx_power_dbm, height_m, range_km
```

**model/data/rl_profiles/{user_id}.json** -- Per-user RL state
```json
{
  "user_id": "son",
  "trip_count": 5,
  "distributions": {
    "morning_commute|weekday|Jayanagar|Koramangala": {
      "meeting": [6.0, 1.0],
      "navigation": [1.0, 1.0],
      ...
    }
  }
}
```

**model/data/user_profiles.json** -- Legacy preference learning
```json
{
  "user_id": {
    "choices": [ { "intent", "preference", "time_bucket", ... } ],
    "learned_preferences": { "meeting_morning_commute": 85.0 }
  }
}
```

**Pydantic models** (model/schemas.py) enforce all API I/O types with Field validators.

---

## Authentication and Authorization

Dual authentication system implemented:

**In-memory demo store** (default, no MongoDB required):
- Demo account: `demo` / `demo123` (bcrypt-hashed)
- Registration creates users in-memory (lost on server restart)
- JWT tokens with `python-jose`, configurable expiration

**MongoDB-backed persistence** (when `MONGO_URI` is configured):
- Motor async driver for user storage
- bcrypt password hashing via passlib
- Users persist across server restarts

**Auth flow:**
- AuthProvider on the frontend hydrates token from `localStorage` on mount
- Unauthenticated users are redirected to `/login`
- JWT bearer token sent via Authorization header
- `GET /api/v1/me` validates token and returns user profile

**Production gaps (acceptable for hackathon):**
- user_id on some RL endpoints is still client-supplied
- No rate limiting on heavy inference endpoints
- CORS is `allow_origins=["*"]`
- JWT secret regenerated on restart (in-memory mode)

---

## State Management Approach

**Frontend**: React `useState` hooks per UI concern (source, destination, preference, telecom mode, emergency toggle). The `useRoutes` hook centralises all data fetching with `useCallback` + `useEffect` for reactive re-fetch on parameter changes. No global state library (Redux/Zustand) needed at this scale.

**Backend**: Stateless request handling. RL bandit instances are in-process module-level cache (`_bandits: dict[str, ContextualBandit]`) for the lifetime of the server process, with file-backed persistence on every `update()` call. ML model loaded once as a lazy singleton (`_model`, `_device` in inference.py).

---

## Hardest Technical Challenge

**Training the model with BCE loss under PyTorch mixed precision (AMP).**

The drop_probability and handoff_risk heads use BCE loss. When `torch.amp.autocast` is active, BCE internally converts inputs to float16. BCE is numerically unstable in float16 (values saturate at 65504; log(sigmoid(x)) underflows). This caused silent NaN gradients that corrupted the entire training run without raising an explicit exception -- the loss would silently become 0.0 and the model weights would stop updating.

---

## How You Solved It

Moved all BCE loss computations **outside** the `autocast` context manager. The forward pass (expensive matrix multiplications in the residual blocks) runs in float16 for speed. The loss calculation (numerically sensitive) runs in float32. This is the pattern recommended in the PyTorch AMP documentation but easy to miss when building custom multi-head architectures.

```python
with torch.amp.autocast(device_type="cuda"):
    sig, drop, ho = model(x)          # float16 forward pass

# BCE outside autocast -- float32 for numerical stability
loss_drop = F.binary_cross_entropy(drop.float(), y_drop)
loss_ho   = F.binary_cross_entropy(ho.float(), y_ho)
```

---

## Trade-offs Made

| Decision | Trade-off |
|---|---|
| Synthetic dataset (100K samples) | No real carrier data access at hackathon; physics-based generation ensures realistic signal gradients but can't capture carrier-specific anomalies |
| File-backed RL state | Zero infrastructure cost; not suitable for concurrent multi-process deployment (race condition on JSON write) |
| Thompson Sampling vs deep RL | Converges in 3-5 trips; cannot model complex sequential dependencies or multi-step reward horizons |
| All-PUT endpoints | ngrok compatibility; breaks REST conventions (PUT /model/health is semantically wrong) |
| In-process model singleton | Avoids model reload overhead on every request; prevents horizontal scaling without sticky sessions |
| Route generation via interpolation | Avoids Google Maps API dependency/cost; ~~generated paths are approximate~~ **Now uses TomTom Routing API for road-snapped geometry** |

---

## Limitations of the Project

- ~~**No real tower data**: Uses 500 synthetic towers.~~ **Resolved**: OpenCelliD integration fetches real tower lat/lng for Bangalore zones. Individual tower positions are rendered on the map at their actual coordinates.
- ~~**Static route generation**: Routes are interpolated between zone centroids, not road-snapped.~~ **Resolved**: TomTom Routing API provides real road-snapped geometry with up to 7 alternative routes per query.
- **Single-server RL**: Bandit state is per-process; a load-balanced deployment would require Redis or a shared store.
- ~~**No live signal data**: The model uses static tower parameters.~~ **Resolved**: Real-time tower data fetched from OpenCelliD along each route path during route generation.
- **Urban Bangalore only**: Zone definitions and tower placement cover 12.78-13.15N, 77.45-77.82E (25 zones + 12 edge zones). Outside this bounding box, predictions degrade to physics defaults.
- ~~**Weather is a static parameter**: The user passes weather_factor; there is no integration with a weather API.~~ **Resolved**: OpenWeather API integration provides real-time weather conditions. Weather factor is automatically fetched and cached per ~1km grid cell with 10-minute TTL.

---

## Performance Considerations

- **GPU inference**: ResidualSignalNet forward pass is ~0.8ms on RTX 5050. MC Dropout uncertainty (8 samples) adds ~6ms. A full route score (20-30 segments) completes in under 50ms including feature extraction.
- **Heatmap endpoint latency**: `GET /api/heatmap` runs inference for all 25 zones sequentially (~750ms total). Should be cached with a TTL.
- **Model loading**: Lazy singleton ensures the 2.2MB checkpoint is loaded once at first request, not at server start.
- **Feature extraction is CPU-bound**: `extract_features()` iterates over all towers in the DataFrame per segment point. With 500 towers, this is ~50,000 distance calculations per segment. Vectorised with NumPy haversine (`haversine_vec()`). Data quality guards clip ranges and replace NaN/inf with 0.
- **Centralised configuration**: All hyperparameters, scoring thresholds, feature normalisation constants, and penalty values are defined in `model/config.py` -- no hardcoded magic numbers in model code.
- **RL update cost**: Beta distribution update is O(1). File write is the only latency; JSON with 10 intents per pattern writes in under 1ms.

---

## Recent Enhancements

### Real Tower Positioning (OpenCelliD Integration)

The map now renders individual cell towers at their real geographic coordinates from OpenCelliD data. A dedicated `GET /api/towers/geo` endpoint returns up to 500 tower positions with lat/lng, operator (Jio, Airtel, Vi, BSNL), signal score, and zone. Each tower is rendered as a color-coded dot on the Mapbox GL JS map (Jio=blue, Airtel=red, Vi=yellow, BSNL=green) replacing the earlier static zone-center badges.

### TomTom Road-Snapped Routing

Routes now use the TomTom Routing API for road-snapped geometry with up to 7 alternative paths. If TomTom returns fewer than the requested count, synthetic alternatives are generated and appended to ensure visual variety on the map.

### Sidebar Route Detail View

The route sidebar toggles between two views:
- **List view**: Shows all routes with signal score, ETA, distance, and a "View Route" button
- **Detail view**: Shows the selected route with large signal bars (color-coded with glow effect), route name, ETA/distance stats, and a Start/Stop Navigation button
- Back button in both views; in tracking mode, back also stops navigation
- Signal bars use a `signalInfo()` helper that returns `{ filled, color, glow, label }` based on signal score thresholds

### Real GPS Navigation Tracking

The `useTracking` hook was rewritten to use the browser's `navigator.geolocation.watchPosition` API instead of simulated position animation. The system finds the closest point on the route path to the user's real GPS coordinates and computes progress as `closestIndex / (pathLength - 1)`. Uses `enableHighAccuracy: true, maximumAge: 3000, timeout: 10000`.

### Nominatim Geocoding Pipeline

Forward and reverse geocoding via OpenStreetMap Nominatim, with Bangalore viewbox bias (`77.35,12.70,77.82,13.20`), rate-limited via `asyncio.Semaphore(1)`, and LRU-cached. Reverse geocode uses `zoom=14` with `addressdetails=1` for suburb-level precision and smart name parsing.

### Live GPS Location for Source

When the browser grants geolocation, the app reverse-geocodes the GPS coordinates to populate the "From" field with a human-readable name, while using the raw GPS lat/lng (not the Nominatim-snapped position) as the routing source for maximum accuracy.

### Periodic Re-prediction During Navigation

Once navigation starts, the system periodically re-evaluates the route based on estimated travel progress:

- **Interval**: `max(2 minutes, 20% of total ETA)` -- adapts to route length
- **Progress gate**: only fires if the user has traveled at least 15% since the last check
- **Skip near end**: no re-prediction after 90% progress
- **Source**: uses the current tracking position as the new origin
- **Application logic**: the new route is applied automatically only if signal score improves by >10 or ETA drops by >15%, preventing unnecessary route flickers

This handles post-departure incidents (accidents, tower outages) that were invisible at planning time.

### Weather-Aware Signal Adjustment

The system integrates the OpenWeather API to factor real-time weather conditions into signal predictions. Weather degrades RF propagation: heavy rain attenuates signals, fog reduces visibility (proxy for atmospheric moisture), and high winds can cause antenna sway.

- **Module**: `backend/weather.py` calls OpenWeather Current Weather API
- **Cache**: 10-minute TTL per ~1km grid cell (`round(lat,2), round(lng,2)`)
- **Output**: A `weather_factor` (0.0-1.0) derived from the weather condition code. Clear sky = 1.0, light rain = 0.85, thunderstorm = 0.6
- **Integration**: The weather factor multiplies into the signal prediction at route scoring time, penalising routes through areas with adverse weather
- **Frontend**: A `WeatherBadge` component shows current conditions (icon, temperature, signal impact) overlaid on the map

### Real-Time Traffic Congestion via TomTom Flow API

Congestion data is sourced live from the **TomTom Traffic API** instead of using static time-of-day simulation. Two TomTom services are used:

**Flow Segment Data** (`/traffic/services/4/flowSegmentData`):
- Returns `currentSpeed` and `freeFlowSpeed` (km/h) for the road segment nearest to any lat/lng
- Congestion ratio = `1 - currentSpeed / freeFlowSpeed` (0 = free-flowing, 1 = standstill)
- Cached per ~500m grid cell for 90 seconds to avoid API quota pressure
- Dedicated endpoint: `GET /api/traffic-flow?lat=...&lng=...` — returns current speed, free-flow speed, confidence, congestion ratio, source
- Tested: MG Road Bangalore at evening → 19 km/h current vs 26 km/h free-flow → 0.269 congestion ratio

**Traffic Incidents** (`/traffic/services/5/incidentDetails`):
- Returns accidents, road closures, queuing traffic, slow traffic within a bounding box
- Per-incident data: lat/lng, description, severity (low/medium/high), from/to road names, delay seconds
- Dedicated endpoint: `GET /api/incidents?min_lat=...&min_lng=...&max_lat=...&max_lng=...`

---

## Integration Status & Verification

### Backend-Frontend Endpoint Mapping (Verified)

| Frontend Service | Endpoint | Backend | Status |
|------------------|----------|---------|--------|
| `routeService.getRoutes` | `GET /api/routes` | `@app.get("/api/routes")` | Working |
| `routeService.getFastRoutes` | `GET /api/routes/fast` | `@app.get("/api/routes/fast")` | Working |
| `routeService.reroute` | `POST /api/reroute` | `@app.post("/api/reroute")` | Working |
| `heatmapService.getHeatmap` | `GET /api/heatmap` | `@app.get("/api/heatmap")` | Working |
| `predictionService.getPrediction` | `GET /api/predict` | `@app.get("/api/predict")` | Working |
| `towerService.getTowers` | `GET /api/towers` | `@app.get("/api/towers")` | Working |
| `towerGeoService.fetchAll` | `GET /api/towers/geo` | `@app.get("/api/towers/geo")` | Working |
| `weatherService.getWeather` | `GET /api/weather` | `@app.get("/api/weather")` | Working |
| `alertsService.getAlerts` | `GET /api/alerts` | `@app.get("/api/alerts")` | Working |
| `deadZoneService.predict` | `GET /api/dead-zones` | `@app.get("/api/dead-zones")` | Working |
| `offlineService.downloadBundle` | `GET /api/offline-bundle` | `@app.get("/api/offline-bundle")` | Working |
| `login()` | `POST /api/v1/login` | In-memory auth handler | Working |
| `register()` | `POST /api/v1/register` | In-memory auth handler | Working |

### Authentication Flow

- AuthProvider hydrates token from `localStorage` on mount
- `page.tsx` waits for `hydrated` flag before rendering the map
- Unauthenticated users are redirected to `/login`
- Login/Register use in-memory auth (no MongoDB dependency)
- Demo account: `demo` / `demo123`

### Data Reality

| Source | Real / Synthetic |
|--------|-----------------|
| Cell tower locations (OpenCelliD, 601 towers) | Real |
| Cell tower signal quality | Synthetic (hardcoded by radio type) |
| Training samples (100K) | Synthetic (generated from propagation models) |
| Route geometry (TomTom) | Real |
| Weather (OpenWeatherMap) | Real |
| Traffic flow (TomTom) | Real |
| Zone definitions (25 Bangalore zones) | Curated |

---

## Honest Rating: 6.5 / 10

### Breakdown

| Category | Score | Notes |
|----------|-------|-------|
| Concept/Innovation | 8/10 | Signal-aware navigation is genuinely useful. Multi-SIM, dead zones, RL personalisation add real depth. |
| ML Implementation | 7/10 | Architecture is sound (residual MLP, MC Dropout, multi-task). Trained on synthetic data, so real-world accuracy is unproven. |
| Backend Engineering | 5/10 | Functional but monolithic (1,481-line main.py), dual auth systems (in-memory + MongoDB), no rate limiting, global mutable state. |
| Frontend | 7/10 | Clean React/Next.js with hooks, Mapbox GL, React Query. Good UX (two-phase loading, onboarding). Polished visuals. |
| Data Pipeline | 5/10 | Training on synthetic propagation data is the biggest weakness. Real towers provide location only, not measured signal. |
| Security | 4/10 | Plaintext demo passwords, JWT secret regenerated on restart, no endpoint auth, no rate limiting. Acceptable for hackathon only. |
| Code Quality | 6/10 | Well-structured frontend and model code. Backend is a monolith with sys.path hacks. Good Pydantic schemas throughout. |
| Completeness | 7/10 | 39 endpoints, 14 components, full ML pipeline, auth, chatbot, heatmaps, offline mode -- impressive surface area. |

### What lifts the score

- The idea is original and practical -- no existing nav app scores by cellular signal
- ML pipeline is complete end-to-end (data generation -> training -> inference -> scoring -> API -> UI)
- RL contextual bandit and dead zone prediction are genuine differentiators
- Two-phase route loading provides excellent perceived performance
- Frontend is visually polished with good UX patterns

### What holds it back

- Synthetic training data means ML accuracy claims are unverifiable against real-world conditions
- Backend won't scale (monolith, in-process globals, no shared cache)
- Security is hackathon-grade -- would need significant hardening for production
- Some features are shallower than they appear (temporal prediction returns current value, traffic heatmap uses zone metadata)
- Dual auth systems (in-memory + MongoDB) add complexity; should consolidate to MongoDB-only

### Bottom line

A strong hackathon project with genuine ML depth and a polished frontend. The concept is compelling and differentiated. The biggest gap is synthetic training data -- the model architecture is well-designed, but its accuracy is unproven without real signal measurements. For a hackathon demo, this is solid work. Production viability would require real data collection, backend restructuring, and security hardening.
- Tested: Central Bangalore bbox → 77 live incidents returned with full street detail

**Graceful fallback**: When TomTom is unavailable (network error, quota exceeded, no API key), the system falls back to a time-of-day + zone-density simulation so routing still works offline.

**Crowd/congestion persistence tracking** (`backend/crowd_tracker.py`):
- Samples up to 20 path points per route, fetches live TomTom flow for each
- Crowd level = blend of real congestion (70%) + time-based pedestrian estimate (30%)
- ~500m grid cells with running-average persistence. Cells active for ≥5 min with ≥2 samples and congestion/crowd > 0.65 trigger alerts
- Stale entries (no update in 30 min) are evicted lazily
- Alert messages include real speeds: "current 19 km/h vs free-flow 26 km/h"
- `GET /api/alerts` returns on-route alerts first, then by proximity

### Multi-Carrier Dead Zone Prediction

The system predicts signal quality for all major carriers (Jio, Airtel, Vi, BSNL) independently at each point along a route, at any specified time of day. This is critical for users who can switch SIMs or have dual-SIM/eSIM devices.

- **Module**: `backend/dead_zone_predictor.py`
- **Function**: `predict_carrier_zones(path, towers_df, time_hour, weather_factor, speed_kmh)`
- **Per-carrier scoring**: Each carrier's towers are filtered from the tower database. For each path point, the ResidualSignalNet model with MC Dropout predicts signal strength, drop probability, and handoff risk, weighted by time-of-day and weather factor
- **Dead zone definition**: A segment where ALL carriers predict signal strength < 30 (on 0-100 scale)
- **Output per route**: `carrier_dead_zones` (list of dead zone segments with coordinates, length, duration, area name, per-carrier signal levels) and `carrier_summary` (per-carrier average signal, minimum signal, count of weak segments)
- **Dedicated endpoint**: `GET /api/dead-zones?source=...&destination=...&time_hour=14` returns full carrier-level analysis for trip planning at specific times
- **Frontend**: Dead zone count is displayed as a toast warning when zones are detected

### Call-Drop Avoidance Estimation

The system computes how many potential call drops the recommended route avoids compared to alternatives:

- **Function**: `estimate_call_drops_avoided(routes)` in `dead_zone_predictor.py`
- **Method**: For each route, counts segments where `drop_probability > 0.5` (from the multi-task model). Compares the recommended route's count against the worst alternative
- **Output**: `call_drop_stats` in the route response containing `drops_avoided`, `recommended_drops`, `worst_alternative_drops`, and a human-readable `message`
- **Frontend**: A green badge displays the call-drop avoidance message when drops are avoided (e.g., "Recommended route avoids 3 potential call drops")

### Offline Cache Pre-Download Alerts

When the system detects an approaching dead zone during navigation, it proactively alerts the user to cache data before losing connectivity:

- **Function**: `offline_cache_alerts(path, segment_signals, speed_kmh, ahead_minutes=5)` in `dead_zone_predictor.py`
- **Lookahead**: Scans 5 minutes of travel distance ahead of the current position
- **Trigger**: Fires when a dead zone (signal < 30 for 3+ consecutive segments) is within the lookahead window
- **Alert content**: Includes time-to-zone, estimated duration in the zone, zone length, area name, and a pre-formatted message
- **Frontend**: Offline alerts have highest toast priority, appearing as warnings with messages like "Dead zone in 2.3 min -- download maps & media now"

### Request Clustering (Route Result Cache)

Backend implements a 30-second TTL cache for the `GET /api/routes` endpoint. The cache key is `(src_lat_3dp, src_lng_3dp, dst_lat_3dp, dst_lng_3dp, preference, telecom)` -- coordinates rounded to 3 decimal places (~100m). When multiple users request similar routes within 30 seconds (e.g. same bus stop to same office at rush hour), only the first request runs model inference; subsequent requests get the cached result instantly.

- **Key design**: coordinates rounded to ~100m eliminates trivial GPS jitter differences
- **TTL**: 30 seconds balances freshness (traffic changes) vs compute savings
- **Lazy GC**: expired entries are evicted when cache exceeds 50 entries
- **Response field**: `cache_hit: true/false` in the API response for observability

---

## Security Considerations

- **CORS is open** (`allow_origins=["*"]`): Acceptable for local/ngrok demo; must be restricted in production.
- **user_id is client-supplied**: No authentication means any client can write to any user's RL profile. In production, derive user_id from a JWT sub claim.
- **No input sanitisation on location names**: `_resolve_location()` does a `.lower().strip()` lookup against a fixed dict -- no SQL injection surface (no database), but arbitrary strings are accepted. Rate limiting recommended.
- **Model weights are not signed**: The checkpoint `best_model.pt` is loaded with `torch.load(weights_map_location=device)`. In production, verify a SHA-256 checksum before loading.
- **No secrets in code**: API keys (TomTom, OpenCelliD, OpenWeather) are stored in `backend/.env` and loaded via `python-dotenv`. The `.env` file is excluded from version control.

---

## Error Handling Strategy

- **Pydantic validation**: All API request bodies are validated at the boundary. Invalid types return HTTP 422 with field-level error details automatically.
- **Model inference fallback**: `predict_single()` wraps the forward pass in a try/except; on failure returns a neutral `{signal: 50, drop: 0.1, handoff: 0.1}` rather than crashing the route scoring.
- **Zone lookup fallback**: `coord_to_zone()` always returns the nearest known zone; `_resolve_location()` falls back to Silk Board (12.9172, 77.6225) for unknown place names.
- **RL bandit cold start**: If no patterns exist for a user+context, `select()` returns `intent=None, exploration_needed=True`; the caller falls back to intent=balanced rather than failing.
- **Training stability**: Gradient clipping (`max_norm=1.0`) prevents exploding gradients. Early stopping (patience=35 epochs) prevents overfitting when val_loss plateaus.

---

## Testing Done

**Unit / Integration (automated):**
- `test_models.py`: Comprehensive 12-component test suite covering config, architecture (560,259 params, forward pass shapes, output ranges), propagation (COST-231 Hata, Ericsson 9999, ITU structure loss, rain attenuation, shadow fading), utils (haversine, feature extraction with full/empty/single towers, edge zones, load factor), inference (predict_single, MC Dropout uncertainty, batch predict, edge cases), scoring (score_route, rank_routes with penalties), bad_zones (detection, task feasibility), explainability (recommendation text, bad zone descriptions), smart_preference (all 10 intents, fuzzy matching), rl_learning (time buckets, day types, zone mapping, Thompson Sampling), evaluate (full metrics suite), and schemas (Pydantic validation). **73 tests, all pass.**
- `test_integration.py`: API integration tests for predict-signal, score-routes, route scoring, and full routes endpoints. **4 tests, all pass.**
- `model/test_api.py`: Tests all 5 core PUT model endpoints (score-routes, predict-signal, analyze-route, detect-zones, health). Validates response schema and non-null recommended_route.
- `model/test_smart.py`: Tests 5 smart-route intent scenarios (meeting, fastest, call, navigation, free-text fuzzy match), intent resolution preview, and the preference learning loop (record 5 choices, verify learned preference).
- `backend/test_rl.py`: Full RL scenario test -- trains son (5 morning trips) and dad (5 mid-morning trips), verifies independent pattern learning (different pattern keys), auto-route returns `rl_learned` source with correct intent, guest user correctly returns `exploration_needed=True`. Also validates all 4 frontend endpoints.

**Manual:**
- Opened the Next.js frontend in Chrome, verified Mapbox GL JS map renders routes with layered styling (glow/casing/main) and smooth camera transitions.
- Verified heatmap zones display correct strong/medium/weak colouring.
- Tested the preference slider (0=fastest, 100=best signal) produces reordered route recommendations.
- Triggered "Smart Reroute" button, verified advisory message appears.

---

## Deployment Method

Local development with ngrok tunnel for external access:

```bash
# Terminal 1 -- Backend
cd D:\Github\MAHE-Hackathon
python -m backend.main

# Terminal 2 -- Frontend
cd D:\Github\MAHE-Hackathon\frontend
pnpm dev

# Terminal 3 -- Tunnel (optional, for external judges)
ngrok http 8000
```

Docker Compose is provided for containerised deployment:
```bash
docker-compose up
```

The `docker-compose.yml` defines two services: `backend` (Python/FastAPI) and `frontend` (Node/Next.js). The frontend is configured with `NEXT_PUBLIC_API_URL` pointing to the backend container.

---

## Tools and Services Used

| Tool | Purpose |
|---|---|
| PyTorch + CUDA | GPU model training and inference |
| FastAPI + Uvicorn | API server |
| NumPy / Pandas | Feature engineering and data generation |
| scikit-learn | Train/val/test split, StandardScaler |
| Next.js 16 | Frontend framework |
| Mapbox GL JS | WebGL route map with layered rendering |
| Chart.js | Signal strength bar charts |
| pnpm | Node package manager (workspace-aware) |
| VS Code | Primary IDE |
| ngrok | External tunnel for demo |
| Docker Compose | Containerised deployment |
| TomTom Routing API | Road-snapped multi-alternative routing |
| OpenCelliD | Real cell tower lat/lng data |
| Nominatim | Forward/reverse geocoding |
| OpenWeather API | Real-time weather conditions for signal adjustment |
| httpx | Async HTTP client for external API calls |

---

## Results / Impact

### Model Metrics & Accuracy

#### ResidualSignalNet -- Primary Signal Prediction (Regression)

| Metric | Value | Notes |
|---|---|---|
| Mean Absolute Error (MAE) | 7.42% | On 0-100 signal scale |
| Root Mean Squared Error (RMSE) | 10.50% | |
| R-squared (R2) | 0.8978 | Explains ~90% of signal variance |
| Final validation loss | 0.41212 | Best checkpoint at epoch 66 |
| Early stopping | Epoch 101 / 300 | Patience = 35 epochs |

#### Drop Probability (Binary Classification)

| Metric | Value |
|---|---|
| Accuracy | 91.1% |
| Precision | 87.6% |
| Recall | 85.9% |
| F1 Score | 86.8% |
| Calibration ECE | 0.0141 |

#### Handoff Risk (Binary Classification)

| Metric | Value |
|---|---|
| Accuracy | 96.8% |
| Precision | 97.1% |
| Recall | 96.8% |
| F1 Score | 96.9% |

#### Dead Zone Detection (Derived Task)

| Metric | Value |
|---|---|
| F1 Score | 89.7% |

#### Per-Bucket Signal Accuracy (Stratified Evaluation)

| Signal Bucket | Samples | MAE | RMSE |
|---|---|---|---|
| Dead (0-15%) | 3,465 | 5.44% | 8.82% |
| Poor (15-35%) | 2,717 | 9.36% | 13.30% |
| Fair (35-55%) | 2,276 | 9.19% | 11.73% |
| Good (55-75%) | 1,351 | 8.94% | 10.96% |
| Great (75-100%) | 2,332 | 5.49% | 6.97% |

Model performs best at the extremes (dead zones and strong signal areas) where the physics-based propagation loss is most predictable. Mid-range buckets have higher error due to multipath interference and urban canyon effects.

#### Edge Zone Performance

| Metric | Value |
|---|---|
| Samples | 1,161 |
| MAE | 17.46% |
| RMSE | 22.06% |
| Mean actual signal | 49.3% |
| Mean predicted signal | 64.0% |

The model overestimates signal in edge zones (tunnels, underpasses, urban canyons) where extreme attenuation is hard to predict from tower geometry alone.

#### MC Dropout Uncertainty Quantification

8 forward passes with dropout active (p=0.12), BatchNorm in eval mode.

| Confidence Level | Criteria |
|---|---|
| High | avg uncertainty < 3.0 and > 80% of segments have low uncertainty |
| Medium | avg uncertainty < 8.0 and > 50% of segments have low uncertainty |
| Low | Otherwise |

#### RL Contextual Bandit (Thompson Sampling)

| Metric | Value |
|---|---|
| Convergence speed | 3-5 trips to confident prediction |
| Dominant intent confidence | 0.857 after 5 trips |
| Thompson sample confidence range | 0.919-0.975 |
| Action space | 10 intents |
| Multi-user isolation | Independent Beta distributions per (user, time, day, origin, dest) pattern |

#### Training Configuration Summary

| Parameter | Value |
|---|---|
| Architecture | Residual MLP (22 -> 256 -> 4x ResBlock -> 64 -> 3 heads) |
| Total parameters | 560,259 |
| Checkpoint size | 2.2 MB |
| Training samples | 100,000 |
| Optimizer | AdamW (lr=3e-4, weight_decay=1e-5) |
| Scheduler | Cosine warmup (10 warmup + cosine decay) |
| Batch size | 1024 |
| Mixed precision | float16 forward / float32 loss |
| Gradient clipping | max_norm=1.0 |
| Label smoothing | eps=0.02 |
| Spatial CV | Tile-based (2.2 km tiles), 471 tiles split 70/15/15 |
| Loss weights | Signal=1.0, Drop=0.6, Handoff=0.4 |
| GPU | RTX 5050 (CUDA 13.0) |

#### Quality Gates (Automated Tests)

| Metric | Minimum Threshold | Actual |
|---|---|---|
| Signal R2 | > 0.80 | 0.8978 |
| Drop accuracy | > 85% | 91.1% |
| Handoff accuracy | > 90% | 96.8% |

73 unit tests + 4 integration tests pass. All quality gates enforced in `test_models.py`.

### Application Metrics

| Metric | Value |
|---|---|
| Signal prediction R2 | 0.8978 |
| Signal MAE | 7.42% |
| Signal RMSE | 10.50% |
| Drop probability accuracy | 91.1% |
| Handoff risk accuracy | 96.8% |
| Bad-zone detection F1 | 89.7% |
| Drop calibration ECE | 0.0141 |
| Model parameters | 560,259 |
| Training samples | 100,000 |
| Synthetic towers | 500 (25 Bangalore zones + 12 edge zones) |
| API endpoints | 39 (20 backend + 8 model + 6 auth + 5 service) |
| RL convergence | 3-5 trips to confident prediction |
| Final training val_loss | 0.41212 (best at epoch 66, early stop at 101) |

The RL system correctly differentiates two users driving the same route at different times of day after 5 demonstration trips each, with 0.857 confidence for the dominant intent and 0.919-0.975 confidence on live Thompson samples.

---

## What You'd Improve Next

1. ~~**Real tower data**: Integrate TRAI tower registry or OpenCelliD for actual Bangalore cell tower coordinates, operators, and frequencies.~~ (Done -- OpenCelliD integrated)
2. ~~**Road-snapped routing**: Replace interpolated paths with OSRM or Valhalla to get actual road-following paths and realistic ETAs.~~ (Done -- TomTom Routing API)
3. **Live signal crowdsourcing**: Vehicles report observed signal at each GPS point; retrain the model online with streaming updates.
4. **Distributed RL state**: Move bandit distributions from JSON files to Redis for multi-instance deployment.
5. **Session-aware multi-user**: Instead of client-supplied user_id, use vehicle VIN + driving pattern clustering to automatically identify distinct drivers.
6. **Heatmap caching**: Cache `GET /api/heatmap` with a 5-minute TTL since zone signal scores are quasi-static.
7. ~~**Weather API integration**: Replace the static `weather_factor` parameter with a live weather API call keyed on the route bounding box.~~ (Done -- OpenWeather API)
8. **Real-time carrier data**: Integrate carrier-specific APIs or crowdsourced signal maps (e.g., OpenSignal) for actual per-carrier signal measurements instead of synthetic predictions.

---

## Key Learnings

**BCE loss is numerically unstable in float16**: Mixed-precision training silently corrupts gradients when BCE runs inside `autocast`. The fix (compute loss outside autocast context) is documented but non-obvious in multi-head architectures. Always validate that losses are non-NaN and non-zero in the first few batches.

**Thompson Sampling is underrated for small action spaces**: The hackathon instinct is to reach for deep RL. Thompson Sampling required zero training infrastructure, converged in single-digit observations, and the Beta distribution parameters are directly interpretable (alpha=successes, beta=failures). For problems with fewer than ~20 discrete actions and sparse rewards, it outperforms DQN on both speed and sample efficiency.

**Synthetic data generation requires domain physics**: The first version generated random signal scores. The model trained to R2=0.3. Switching to physics-based ground truth (COST-231 Hata + Ericsson 9999 propagation models) immediately pushed R2 to 0.90. The model learns real signal-distance relationships instead of noise.

**Scaffolded files cause subtle build failures**: Running `create-next-app` or a shadcn initialiser inside an existing project creates conflicting `app/` directories. Next.js will silently prefer the root-level `app/` over `src/app/`, breaking the build with cryptic CSS import errors (`tw-animate-css not found`). Always audit for duplicate app directory roots after running any scaffolding tool.

**All-PUT API design is valid for specific deployment constraints**: REST purists would object, but all-PUT worked seamlessly with ngrok free tier, and FastAPI + Pydantic handles PUT bodies identically to POST. Pragmatic engineering sometimes requires breaking conventions for operational reasons.
