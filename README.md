# SignalRoute AI -- Cellular Network-Aware Routing System

A smart navigation platform that recommends routes based on **cellular network reliability** alongside ETA and distance. Traditional map apps ignore mobile connectivity -- SignalRoute fixes that.

**Problems solved:**
- Calls dropping mid-route
- Ride-hailing apps disconnecting
- Fleet tracking going offline
- Emergency SOS failing to send
- Navigation updates stopping in dead zones
- Video/music buffering on highways

## How It Works

```
User enters source + destination
         |
   3 candidate routes generated (OSRM / mock)
         |
   Each route sampled every 500m
         |
   ML model predicts signal strength + drop probability per point
         |
   Routes scored: final_score = weight * signal + (1 - weight) * speed
         |
   RL (Thompson Sampling) personalizes weights per user over time
         |
   Ranked results displayed on map with signal heatmap overlay
```

## Demo

**Bangalore Demo Route: MG Road to Electronic City**

| Route | ETA | Signal | Behavior |
|-------|-----|--------|----------|
| Fastest Route | 28 min | Medium (48) | Direct via Hosur Road -- enters weak signal zone |
| Balanced Route | 36 min | Medium (50) | Via HSR Layout -- avoids worst dead zones |
| Best Signal Route | 47 min | Medium (45) | Detours through Koramangala, Jayanagar -- strong coverage |

The user adjusts a preference slider (0 = pure speed, 100 = pure signal) and the ranking updates in real-time.

## Features

### Core Navigation
- **Multi-route comparison** -- Fastest, Balanced, Best Signal with ETA/distance/signal scores
- **Preference slider** -- Dynamic weight adjustment between speed and connectivity
- **Carrier filter** -- Route scoring per telecom provider (Jio, Airtel, Vi, All)
- **Signal heatmap** -- Color-coded zone markers on the map (green/yellow/red)
- **Dead zone alerts** -- Toast notifications when approaching weak signal areas
- **Live rerouting** -- Smart reroute button triggers re-scoring from current position

### AI / ML
- **Signal prediction model** -- ResidualSignalNet (PyTorch) with 17-feature input, trained on Bangalore tower data
- **Thompson Sampling RL** -- Per-user Beta-Bernoulli bandit learns signal vs speed preference over time
- **Batch prediction** -- All route points scored in a single ML call (no N+1)
- **Graceful fallback** -- Neutral predictions returned if ML service is unavailable

### Map Intelligence
- **20 Bangalore zones** -- Each with terrain type, building density, tower coverage
- **12 edge-case zones** -- Tunnels (45dB penalty), underpasses (20-25dB), urban canyons (10-12dB)
- **Cell tower overlay** -- SVG tower icons with signal score and color-coded borders
- **Route polylines** -- Interactive multi-route display with hover effects

### UX
- **Conversational route finder** -- 5-step chatbot (source, destination, network priority, road quality, ISP)
- **Geolocation** -- "Use my location" with browser GPS + reverse geocoding
- **Network auto-detect** -- Detects carrier via Navigator.connection API
- **Map loading skeleton** -- Spinner overlay until tiles fully render
- **Simulated tracking** -- Live position animation along selected route

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.2.4 | React framework (App Router, Turbopack) |
| React | 19 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | 4 | Utility-first styling |
| Leaflet | 1.9.4 | Interactive map |
| React Query | 5.99 | Async data fetching |
| Framer Motion | 12.38 | Animations |
| Lucide React | - | Icon library |
| Chart.js | - | Signal charts |
| Axios | 1.15 | HTTP client |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.115 | Async Python API framework |
| Uvicorn | 0.30 | ASGI server |
| Motor | 3.6 | Async MongoDB driver |
| httpx | 0.26 | Async HTTP client (ML + OSRM calls) |
| NumPy | 1.26 | RL sampling (Beta distribution) |
| PyTorch | 2.x | Signal prediction model |
| Pydantic | 2.5 | Schema validation |
| pandas | - | Data processing |
| scikit-learn | - | Feature preprocessing |

### Infrastructure
| Component | Technology |
|-----------|------------|
| Database | MongoDB (Motor async driver) |
| Routing Engine | OSRM (OpenStreetMap) with mock fallback |
| ML Model | PyTorch ResidualSignalNet |
| Tower Data | OpenCelliD (real) + synthetic fallback |
| Containerization | Docker + Docker Compose |

## Project Structure

```
signalroute-ai/
|-- README.md
|-- .env.example
|-- docker-compose.yml
|-- requirements.txt
|
|-- backend/                    # FastAPI backend
|   |-- main.py                 # Monolithic server (serves frontend)
|   |-- requirements.txt
|   |-- Dockerfile
|   |-- docker-compose.yml      # Backend + MongoDB
|   |-- .env.example
|   |-- api/                    # HTTP endpoints (no business logic)
|   |   |-- health.py
|   |   |-- routes.py
|   |-- app/                    # Application factory
|   |   |-- main.py             # Clean architecture entry point
|   |   |-- lifecycle.py        # Startup/shutdown hooks (Mongo connect)
|   |-- core/                   # Cross-cutting concerns
|   |   |-- config.py           # Pydantic settings (env-based)
|   |   |-- logging.py          # Structured logging
|   |   |-- security.py         # Input validation (user_id, coords, weight)
|   |-- db/                     # Database layer (MongoDB + Motor)
|   |   |-- base.py             # Async client singleton + index creation
|   |   |-- session.py          # Database accessor
|   |   |-- models/
|   |   |   |-- rl_profile.py   # RL profile document model
|   |   |   |-- user.py         # User document model
|   |   |-- repository/
|   |       |-- rl_repo.py      # Repository pattern for rl_profiles
|   |-- dependencies/           # FastAPI dependency injection
|   |   |-- auth.py             # Service factories (Depends)
|   |   |-- db.py               # Database dependency
|   |-- routing/                # External routing integration
|   |   |-- osrm_client.py      # OSRM HTTP client + mock fallback
|   |   |-- polyline.py         # Google polyline encode/decode
|   |   |-- route_generator.py  # Convenience wrapper
|   |-- schemas/                # Pydantic request/response models
|   |   |-- route_schema.py     # RouteRequest, RouteResult, RouteResponse
|   |   |-- signal_schema.py    # SignalPoint, SignalPrediction
|   |   |-- rl_schema.py        # RLUpdateRequest, RLUpdateResponse
|   |-- services/               # Business logic (no HTTP concerns)
|   |   |-- route_service.py    # Main orchestrator: OSRM -> ML -> score -> rank
|   |   |-- signal_client.py    # Async ML client with retry + cache + fallback
|   |   |-- scoring_service.py  # Normalize ETA, compute signal/final scores
|   |   |-- rl_service.py       # Thompson Sampling (Beta-Bernoulli bandit)
|   |-- utils/
|   |   |-- geo.py              # Haversine, route point sampling
|   |   |-- time_encoding.py    # Cyclic hour encoding for ML features
|   |-- scripts/
|   |   |-- seed_db.py          # Database seeding script
|   |-- tests/
|       |-- test_routes.py      # 39 tests (scoring, signal, RL, API, utils)
|
|-- model/                      # ML signal prediction model
|   |-- main.py                 # FastAPI app with /model/* endpoints
|   |-- config.py               # 20 zones, 12 edge zones, model hyperparams
|   |-- architecture.py         # ResidualSignalNet (PyTorch)
|   |-- inference.py            # Signal prediction on route segments
|   |-- scoring.py              # Route scoring logic
|   |-- propagation.py          # Path loss propagation model
|   |-- rl_learning.py          # Thompson Sampling bandit implementation
|   |-- bad_zones.py            # Dead zone detection + task feasibility
|   |-- explainability.py       # Route comparison summaries
|   |-- smart_preference.py     # Context-aware preference learning
|   |-- opencellid.py           # Real tower data from OpenCelliD API
|   |-- utils.py                # Haversine, feature extraction
|   |-- generate_data.py        # Training data generation
|   |-- train.py                # Model training pipeline
|   |-- evaluate.py             # Model evaluation
|   |-- data/                   # Training data + tower CSVs
|   |-- weights/                # Saved model checkpoints (.pt)
|
|-- frontend/                   # Next.js 16 frontend
|   |-- package.json
|   |-- next.config.ts
|   |-- tsconfig.json
|   |-- src/
|   |   |-- app/
|   |   |   |-- page.tsx        # Main SPA page (state management)
|   |   |   |-- layout.tsx      # Root layout (fonts, QueryProvider)
|   |   |   |-- globals.css     # Tailwind + custom styles
|   |   |-- components/
|   |   |   |-- search/
|   |   |   |   |-- SearchBar.tsx       # Location autocomplete (20 areas)
|   |   |   |-- map/
|   |   |   |   |-- MapView.tsx         # Leaflet map, routes, zone markers
|   |   |   |   |-- MapContainer.tsx    # Dynamic import wrapper
|   |   |   |-- sidebar/
|   |   |   |   |-- RouteSidebar.tsx    # Route list with signal badges
|   |   |   |-- filters/
|   |   |   |   |-- FilterPanel.tsx     # Preset filters + telecom grid
|   |   |   |-- chat/
|   |   |   |   |-- ChatBot.tsx         # 5-step conversational route finder
|   |   |   |-- actions/
|   |   |   |   |-- ActionButtons.tsx   # Locate, track, reroute buttons
|   |   |   |-- common/
|   |   |       |-- RouteBottomCard.tsx # Selected route detail card
|   |   |       |-- Toast.tsx           # Alert notifications
|   |   |-- hooks/
|   |   |   |-- useMapData.ts           # React Query hooks (routes, heatmap, towers)
|   |   |   |-- useGeolocation.ts       # Browser GPS integration
|   |   |   |-- useNetworkDetect.ts     # Carrier auto-detection
|   |   |   |-- useTracking.ts          # Simulated live position tracking
|   |   |-- services/
|   |   |   |-- api.ts                  # Axios API client
|   |   |-- types/
|   |       |-- route.ts                # TypeScript type definitions
|
|-- datasets/                   # Seed data
|   |-- bangalore_signal_mock.json    # Zone signal strengths
|   |-- routes_seed.json              # Sample routes
|   |-- towers_mock.csv               # Mock cell tower data
|
|-- database/                   # Database setup
|   |-- SCHEMA.md               # MongoDB collection schemas
|   |-- init_db.py              # Database initialization + seed script
|
|-- docs/                       # Documentation
|   |-- API.md                  # Full API reference
|   |-- ARCHITECTURE.md         # System design + data flow
|   |-- DEPLOYMENT.md           # Deployment guide (Vercel, Railway, Atlas)
```

## API Endpoints

### Frontend API (`/api/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/routes` | Generate scored route options |
| GET | `/api/heatmap` | Signal quality for all 20 zones |
| GET | `/api/predict` | Predict future signal for a zone |
| POST | `/api/reroute` | Smart reroute from current position |
| GET | `/api/towers` | Cell tower infrastructure summary |

### ML Model API (`/model/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/model/auto-route` | RL-powered automatic route selection |
| PUT | `/model/record-trip` | Record trip outcome for RL training |
| PUT | `/model/user-patterns` | Get learned user preferences |
| GET | `/model/refresh-towers` | Refresh tower data from OpenCelliD |

### Clean Architecture API (`/api/v1/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/route` | Coordinate-based route ranking |
| POST | `/api/v1/rl/update` | Update RL profile (success/failure) |
| GET | `/api/v1/health` | Service health check |

Full API documentation: [docs/API.md](docs/API.md)

## Scoring Engine

### Route Ranking Formula

```
final_score = weight * (signal_score / 100) + (1 - weight) * eta_score
```

| Variable | Range | Description |
|----------|-------|-------------|
| `weight` | 0.0 - 1.0 | User preference (slider: 0 = speed, 1 = signal) |
| `signal_score` | 0 - 100 | Average predicted signal strength along route |
| `eta_score` | 0.0 - 1.0 | Normalized ETA (1 = fastest candidate, 0 = slowest) |

### RL Personalization (Thompson Sampling)

Each user has a Beta(alpha, beta) distribution learned over time:

```
rl_sample ~ Beta(alpha, beta)
effective_weight = 0.6 * user_weight + 0.4 * rl_sample
```

- User picks signal-heavy route and is satisfied -> alpha += 1
- User picks speed route and is satisfied -> beta += 1
- Over time, the system learns each user's true preference

### Signal Prediction

The ML model (ResidualSignalNet) predicts signal quality at each point:

**Input features (17 dims):** latitude, longitude, tower distance, tower signal dBm, terrain type (7 one-hot), hour (sin/cos), density, building height, operator

**Output:** signal_strength (0-100), drop_probability (0-1)

## Signal Zones

### Bangalore Coverage Map

| Zone | Terrain | Density | Typical Signal |
|------|---------|---------|----------------|
| MG Road | Urban main | High | Strong (78-95) |
| Koramangala | Urban main | High | Strong (70-85) |
| Indiranagar | Urban main | High | Strong (72-88) |
| Electronic City | Suburban | Medium | Weak (28-45) |
| Whitefield | Suburban | Medium | Medium (50-65) |
| Hebbal | Highway | Medium | Medium (45-60) |
| Bannerghatta | Suburban | Low | Weak (20-35) |
| Hosur Road | Highway | Medium | Medium (40-55) |
| Peenya | Suburban | Low | Weak (25-40) |

### Edge Case Zones

| Zone | Type | Signal Impact |
|------|------|--------------|
| Namma Metro Tunnels | Tunnel | -45 dB (near total loss) |
| Hebbal Flyover Underpass | Underpass | -25 dB |
| Silk Board Underpass | Underpass | -20 dB |
| Commercial Street | Urban canyon | -12 dB |
| Brigade Road | Urban canyon | -11 dB |

### Edge Cases Handled

| Scenario | Solution |
|----------|----------|
| Tunnel signal loss | 45dB penalty in predictions, dead zone alert |
| Rural low signal everywhere | Best available route with advisory warning |
| Sudden tower outage | Reroute button triggers re-scoring |
| Rain degradation | Time-of-day features capture weather patterns |
| User changes carrier | Re-fetch with new telecom filter |
| Fast route has dead zone | Highlighted in route card, user decides |
| No alternate route | Return single route with signal advisory |
| GPS drift | watchPosition for continuous location updates |
| ML service down | Fallback neutral predictions (signal=50, drop=0.1) |
| OSRM unavailable | Mock route generator with 3 synthetic routes |

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env

uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
pnpm install      # or: npm install
pnpm dev          # or: npm run dev
```

### 3. Docker (Both Services)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Testing

```bash
# Run all 39 backend tests (no external services needed)
cd <repo-root>
python -m pytest backend/tests/test_routes.py -v
```

**Test coverage:**

| Module | Tests | What's Tested |
|--------|-------|---------------|
| ScoringService | 12 | Signal score, drop prob, ETA normalization, weighted scoring |
| SignalClient | 3 | ML success, ML failure fallback, cache hits |
| RLService | 5 | Sampling range, alpha/beta updates, profile creation |
| RouteService | 5 | Ranking, field validation, RL integration, weight extremes |
| API | 6 | Health, root, valid route, invalid coords, invalid weight, missing fields |
| Utilities | 8 | Haversine, point sampling, polyline roundtrip, time encoding |

## Deployment

| Component | Platform | Config |
|-----------|----------|--------|
| Frontend | Vercel | Root: `frontend`, auto-detected Next.js |
| Backend | Railway / Render | Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Database | MongoDB Atlas | Free M0 tier, set `MONGO_URI` env var |

Full deployment guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for frontend |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `signalroute` | Database name |
| `MODEL_URL` | `http://localhost:8001` | ML prediction service |
| `OSRM_URL` | `http://router.project-osrm.org` | OSRM routing engine |

## Documentation

- [API Reference](docs/API.md) -- Full endpoint documentation with request/response examples
- [Architecture](docs/ARCHITECTURE.md) -- System design, data flow, ML model details
- [Deployment Guide](docs/DEPLOYMENT.md) -- Vercel, Railway, Atlas setup instructions
- [Database Schema](database/SCHEMA.md) -- MongoDB collections, indexes, seed data
