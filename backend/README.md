# SignalRoute Backend

Cellular network-aware routing backend with reinforcement learning personalization.

## Architecture

```
API (FastAPI) -> Services -> External Clients (ML / OSRM)
                    |
                    v
               Repository -> MongoDB (Motor)
```

**Layers:**
- `api/` - HTTP endpoints (no business logic)
- `services/` - Business logic orchestration
- `routing/` - OSRM client + polyline codec
- `db/` - MongoDB models and repository (Motor async)
- `schemas/` - Pydantic request/response models
- `core/` - Config, logging, security validation
- `dependencies/` - FastAPI dependency injection

## API

### POST /api/v1/route

```json
{
  "origin": { "lat": 12.84, "lon": 77.67 },
  "destination": { "lat": 12.97, "lon": 77.75 },
  "weight": 0.5,
  "user_id": "optional_user_id"
}
```

Returns ranked routes with ETA, signal score, drop probability, and geometry.

### POST /api/v1/rl/update

```json
{
  "user_id": "user_123",
  "success": true
}
```

Updates the user's RL profile (Thompson Sampling).

### GET /api/v1/health

Returns service health status.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run (standalone clean-arch backend)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Run tests
pytest backend/tests/test_routes.py -v
```

## Docker

```bash
cd backend
docker-compose up --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| MODEL_URL | http://localhost:8001 | ML signal prediction service |
| OSRM_URL | http://router.project-osrm.org | OSRM routing service |
| MONGO_URI | mongodb://localhost:27017 | MongoDB connection string |
| DB_NAME | signalroute | Database name |

## Testing

39 tests covering scoring, signal client (with fallback), RL service (Thompson Sampling), route service (orchestration), API endpoints, and utilities. All tests run without external services.
