# Architecture Overview

## System Design

```
                    +------------------+
                    |   Next.js 16     |
                    |   Frontend       |
                    |   (Port 3000)    |
                    +--------+---------+
                             |
                    HTTP (axios, 12s timeout)
                             |
                    +--------v---------+
                    |   FastAPI        |
                    |   Backend        |
                    |   (Port 8000)    |
                    +--+-----+-----+--+
                       |     |     |
              +--------+  +--+--+  +--------+
              |           |     |           |
     +--------v--+  +-----v-+  +v---------+
     |  Signal   |  | OSRM  |  | MongoDB  |
     |  Model    |  | Router|  | (Motor)  |
     |  (PyTorch)|  | (HTTP)|  |          |
     +-----------+  +-------+  +----------+
```

## Backend Layers

### 1. API Layer (`backend/api/`)
- HTTP endpoints only
- No business logic
- Input validation via Pydantic schemas
- Dependency injection via FastAPI `Depends()`

### 2. Service Layer (`backend/services/`)

| Service | Responsibility |
|---------|---------------|
| `RouteService` | Orchestrates route fetching, signal prediction, scoring, ranking |
| `SignalClient` | Async HTTP client for ML predictions with retry + cache + fallback |
| `ScoringService` | Pure functions: normalize ETA, compute signal scores, weighted combination |
| `RLService` | Thompson Sampling (Beta-Bernoulli bandit) for preference personalization |

### 3. Data Layer (`backend/db/`)
- Motor async MongoDB driver (no blocking calls)
- Repository pattern (`RLRepository`)
- Auto-created indexes on startup

### 4. External Clients (`backend/routing/`)
- `OSRMClient` with real HTTP + mock fallback
- Polyline encoding/decoding

## ML Model Architecture

The signal prediction model uses a **ResidualSignalNet** (PyTorch):

```
Input (17 features) -> Linear(17, 256)
    -> 4x ResidualBlock(256, dropout=0.12)
    -> Bottleneck(256, 64)
    -> Signal Head (64 -> 32 -> 1)
    -> Drop Head   (64 -> 32 -> 1, sigmoid)
```

**Input Features (17 dimensions):**
- Latitude, Longitude (normalized)
- Distance to nearest tower
- Tower signal strength (dBm)
- Terrain type (one-hot: highway, urban, suburban, residential, tunnel, underpass, canyon)
- Hour of day (cyclic sin/cos encoding)
- Area density score
- Building height
- Operator encoding

## Scoring Formula

```
final_score = weight * (signal_score / 100) + (1 - weight) * eta_score
```

Where:
- `weight` is 0-1 (user preference slider: 0 = pure speed, 1 = pure signal)
- `signal_score` = average predicted signal strength across sampled route points (0-100)
- `eta_score` = min-max normalized ETA (1 = fastest, 0 = slowest)

## RL Personalization (Thompson Sampling)

Each user has a Beta(alpha, beta) distribution:
- Sample from Beta(alpha, beta) to get RL preference
- Blend with explicit weight: `effective_weight = 0.6 * user_weight + 0.4 * rl_sample`
- After trip: success (happy with signal route) -> alpha += 1, failure -> beta += 1

## Data Flow: Route Request

```
1. User enters source + destination in frontend
2. Frontend calls GET /api/routes?source=X&destination=Y&preference=50
3. Backend resolves location names to coordinates
4. OSRM client fetches 3 candidate routes (or generates mock routes)
5. For each route:
   a. Sample points every 500m along polyline
   b. Batch predict signal quality via ML model
   c. Compute: signal_score, drop_prob, eta_score
   d. Calculate final_score with user weight
6. Rank routes by final_score descending
7. Return 3 routes: Fastest, Balanced, Best Signal
8. Frontend renders route cards + map polylines + signal zone markers
```

## Edge Case Handling

| Scenario | Solution |
|----------|----------|
| ML service down | Graceful fallback: neutral predictions (signal=50, drop=0.1) |
| OSRM unavailable | Mock route generator with 3 synthetic routes |
| No alternate routes | Return best available with advisory |
| Tunnel/underpass | 45dB signal penalty applied to predictions |
| User changes carrier | Re-fetch routes with new telecom filter |
| GPS drift | Geolocation API with watchPosition for continuous updates |
