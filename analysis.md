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
- REST API server with 11 endpoints
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
| Maps | Leaflet + react-leaflet |
| Charts | Chart.js + react-chartjs-2 |
| Styling | Tailwind CSS v4 |
| HTTP Client | Axios |
| Animation | Framer Motion |
| Language | Python 3.11 (backend), TypeScript 5 (frontend) |

---

## Reason for Choosing the Tech Stack

**PyTorch**: Native CUDA support enabled GPU-accelerated training on the RTX 5050. Mixed-precision (torch.amp) halved training memory with no accuracy loss. The dynamic computation graph simplified rapid architecture iteration.

**FastAPI**: Automatic Pydantic validation, async-capable, OpenAPI docs generated for free. All-PUT endpoint design was required for ngrok tunnel compatibility (ngrok free tier blocks non-PUT HTTP methods inconsistently on some NAT setups).

**Next.js / React 19**: The frontend teammate's choice. The `src/app` directory structure and server/client component split made it straightforward to keep map rendering client-only (Leaflet requires `window`).

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
     a. For each path segment, extract_features() builds a 17-dim feature vector:
        [dist_to_nearest, signal_quality, towers_in_2km, time_cos, time_sin,
         weather_factor, speed_kmh, height_diff, zone_penalty, freq_mhz,
         tx_power, load_factor, terrain_code, rain_attenuation, ...]
     b. ResidualSignalNet forward pass -> (signal_score, drop_prob, handoff_risk)
     c. Physics validation: received_signal_dbm() using COST-231 Hata +
        Ericsson 9999 ensemble (55/45 weight) + ITU-R P.1238 structure loss

5. Routes ranked by weighted_score = signal_w * sig_norm + time_w * eta_norm
   with penalties for dead zones, single-tower dependency, low continuity

6. Response returns route list + recommended_route name

7. Frontend renders paths on Leaflet map, colored by segment signal strength
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

The ResidualSignalNet (558,979 parameters) learns residuals on top of these physics priors, achieving R2=0.9243 on held-out test data.

### 2. Dead Zone Detection and Task Feasibility

`detect_bad_zones()` identifies contiguous route segments where signal drops below 40 (configurable threshold). For each zone it reports: GPS coordinates, duration in minutes, distance in km, and proximity to the zone. `assess_task_feasibility()` then asks: "Can I complete a 30-minute Zoom call on this route?" and answers with the longest stable connectivity window vs. required duration.

### 3. RL-Powered Intent Learning per User

The contextual bandit maintains independent Beta(alpha, beta) distributions per `(user_id, time_bucket, day_type, origin_zone, dest_zone)` pattern. This naturally handles the multi-user scenario: son drives 7:30 AM Jayanagar->Koramangala daily (learns "meeting", preference=85), dad drives 10:00 AM same route (learns "navigation", preference=10). Same origin/destination, different time = different patterns = independent learning with no interference.

---

## APIs Created

### Frontend Endpoints (GET/POST /api/*)

| Method | Path | Description |
|---|---|---|
| GET | /api/routes | Score 3 route options between named locations |
| GET | /api/heatmap | Signal strength for all 20 Bangalore zones |
| GET | /api/predict | Short-horizon signal forecast for a zone |
| POST | /api/reroute | Reroute request with signal bias |

### Model Endpoints (PUT /model/*)

| Method | Path | Description |
|---|---|---|
| PUT | /model/score-routes | Score arbitrary routes with custom towers |
| PUT | /model/predict-signal | Point signal prediction at (lat,lng) |
| PUT | /model/analyze-route | Full route analysis with bad zones |
| PUT | /model/detect-zones | Dead zone detection only |
| PUT | /model/health | Model status and training metadata |
| PUT | /model/smart-route | Intent-driven routing (rule-based preference) |
| PUT | /model/record-choice | Record user choice for preference learning |
| PUT | /model/resolve-intent | Preview intent -> preference mapping |
| PUT | /model/auto-route | RL-powered routing (pattern recognition) |
| PUT | /model/record-trip | Update RL distributions after trip |
| PUT | /model/user-patterns | View learned RL patterns for a user |

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

None implemented -- hackathon scope. In production:
- JWT bearer tokens per vehicle VIN
- user_id derived from authenticated session, not client-supplied
- Rate limiting on /model/auto-route (heavy inference endpoint)
- HTTPS required; current CORS is `allow_origins=["*"]`

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
| Route generation via interpolation | Avoids Google Maps API dependency/cost; generated paths are approximate, not road-snapped |

---

## Limitations of the Project

- ~~**No real tower data**: Uses 500 synthetic towers.~~ **Resolved**: OpenCelliD integration fetches real tower lat/lng for Bangalore zones. Individual tower positions are rendered on the map at their actual coordinates.
- **Static route generation**: Routes are interpolated between zone centroids, not road-snapped. Real routing requires OSRM or Valhalla. **Partially resolved**: TomTom routing API provides road-snapped geometry with up to 5 alternative routes.
- **Single-server RL**: Bandit state is per-process; a load-balanced deployment would require Redis or a shared store.
- ~~**No live signal data**: The model uses static tower parameters.~~ **Resolved**: Real-time tower data fetched from OpenCelliD along each route path during route generation.
- **Urban Bangalore only**: Zone definitions and tower placement cover 12.78-13.15N, 77.45-77.82E. Outside this bounding box, predictions degrade to physics defaults.
- **Weather is a static parameter**: The user passes weather_factor; there is no integration with a weather API.

---

## Performance Considerations

- **GPU inference**: ResidualSignalNet forward pass is ~0.8ms on RTX 5050. A full route score (20-30 segments) completes in under 30ms including feature extraction.
- **Heatmap endpoint latency**: `GET /api/heatmap` runs inference for all 20 zones sequentially (~600ms total). Should be cached with a TTL.
- **Model loading**: Lazy singleton ensures the 2.2MB checkpoint is loaded once at first request, not at server start.
- **Feature extraction is CPU-bound**: `extract_features()` iterates over all towers in the DataFrame per segment point. With 500 towers, this is ~50,000 distance calculations per segment. Vectorised with NumPy haversine (`haversine_vec()`).
- **RL update cost**: Beta distribution update is O(1). File write is the only latency; JSON with 10 intents per pattern writes in under 1ms.

---

## Recent Enhancements

### Real Tower Positioning (OpenCelliD Integration)

The map now renders individual cell towers at their real geographic coordinates from OpenCelliD data. A dedicated `GET /api/towers/geo` endpoint returns up to 500 tower positions with lat/lng, operator (Jio, Airtel, Vi, BSNL), signal score, and zone. Each tower is rendered as a color-coded dot on the Leaflet map (Jio=blue, Airtel=red, Vi=yellow, BSNL=green) replacing the earlier static zone-center badges.

### TomTom Road-Snapped Routing

Routes now use the TomTom Routing API for road-snapped geometry with up to 5 alternative paths. If TomTom returns fewer than 5 routes, synthetic alternatives are generated and appended to ensure visual variety on the map.

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

### Crowd/Traffic Congestion Persistence Tracking

Beyond static signal scoring, the system tracks crowd/congestion patterns that affect tower load and signal quality:

- **Module**: `backend/crowd_tracker.py` implements a grid-based congestion memory
- **Grid resolution**: ~500m cells (coordinates rounded to `lat*200, lng*200`)
- **Persistence**: Running average of congestion scores per cell. A cell becomes an "active alert" after the average exceeds a threshold for 5+ minutes
- **Staleness**: Cells with no updates for 30 minutes are evicted automatically
- **Seeding**: When routes are scored, their congestion data is recorded into the tracker
- **Alert endpoint**: `GET /api/alerts` returns active congestion alerts near the user's position or along a specified path

### Multi-Carrier Dead Zone Prediction

The system predicts signal quality for all major carriers (Jio, Airtel, Vi, BSNL) independently at each point along a route, at any specified time of day. This is critical for users who can switch SIMs or have dual-SIM/eSIM devices.

- **Module**: `backend/dead_zone_predictor.py`
- **Function**: `predict_carrier_zones(path, towers_df, time_hour, weather_factor, speed_kmh)`
- **Per-carrier scoring**: Each carrier's towers are filtered from the tower database. For each path point, distance-based signal strength is computed with the ResidualSignalNet model, weighted by time-of-day and weather factor
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

## Updated API Surface

### New Endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/geocode | Forward geocode via Nominatim (location name to lat/lng) |
| GET | /api/reverse-geocode | Reverse geocode via Nominatim (lat/lng to place name) |
| GET | /api/towers/geo | Individual tower positions for map rendering |
| GET | /api/detect-network | ISP detection via external IP lookup |
| GET | /api/weather | Live weather + signal impact for a lat/lng |
| GET | /api/alerts | Congestion/crowd persistence alerts along a path |
| GET | /api/dead-zones | Multi-carrier dead zone prediction at a specific time of day |

### Updated Endpoints

| Method | Path | Change |
|---|---|---|
| GET | /api/routes | Added 30s request clustering cache, `cache_hit` field, TomTom integration, up to 7 routes. Now includes `weather`, `call_drop_stats`, per-route `carrier_dead_zones`, `carrier_summary`, and `offline_alerts` |
| GET | /api/heatmap | Now uses OpenCelliD-enriched tower data for zone scoring |

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
- `model/test_api.py`: Tests all 5 core PUT model endpoints (score-routes, predict-signal, analyze-route, detect-zones, health). Validates response schema and non-null recommended_route.
- `model/test_smart.py`: Tests 5 smart-route intent scenarios (meeting, fastest, call, navigation, free-text fuzzy match), intent resolution preview, and the preference learning loop (record 5 choices, verify learned preference).
- `backend/test_rl.py`: Full RL scenario test -- trains son (5 morning trips) and dad (5 mid-morning trips), verifies independent pattern learning (different pattern keys), auto-route returns `rl_learned` source with correct intent, guest user correctly returns `exploration_needed=True`. Also validates all 4 frontend endpoints.

**Manual:**
- Opened the Next.js frontend in Chrome, verified Leaflet map renders 3 routes with colour-coded signal segments.
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
| Leaflet | Interactive route map |
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

| Metric | Value |
|---|---|
| Signal prediction R2 | 0.9243 |
| Drop probability accuracy | 93.4% |
| Handoff risk accuracy | 96.9% |
| Model parameters | 558,979 |
| Training samples | 100,000 |
| Synthetic towers | 500 (20 Bangalore zones) |
| API endpoints | 14 (7 frontend + 7 model) |
| RL convergence | 3-5 trips to confident prediction |
| Final training val_loss | 0.41014 (epoch 90 of 300, early stop) |

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

**Synthetic data generation requires domain physics**: The first version generated random signal scores. The model trained to R2=0.3. Switching to physics-based ground truth (COST-231 Hata + Ericsson 9999 propagation models) immediately pushed R2 to 0.92. The model learns real signal-distance relationships instead of noise.

**Scaffolded files cause subtle build failures**: Running `create-next-app` or a shadcn initialiser inside an existing project creates conflicting `app/` directories. Next.js will silently prefer the root-level `app/` over `src/app/`, breaking the build with cryptic CSS import errors (`tw-animate-css not found`). Always audit for duplicate app directory roots after running any scaffolding tool.

**All-PUT API design is valid for specific deployment constraints**: REST purists would object, but all-PUT worked seamlessly with ngrok free tier, and FastAPI + Pydantic handles PUT bodies identically to POST. Pragmatic engineering sometimes requires breaking conventions for operational reasons.
