# SignalRoute API Reference

Base URL: `http://localhost:8000`

---

## Frontend API Surface (`/api/*`)

These endpoints serve the Next.js frontend.

### GET /api/routes

Generate scored route recommendations between two Bangalore locations.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | string | Yes | - | Start location name (e.g., "Koramangala") |
| `destination` | string | Yes | - | End location name (e.g., "Whitefield") |
| `preference` | int | No | 50 | 0 = pure speed, 100 = pure signal quality |
| `telecom` | string | No | "all" | Carrier filter: "all", "jio", "airtel", "vi" |

**Response:**

```json
{
  "source": "Koramangala",
  "destination": "Whitefield",
  "preference": 50,
  "routes": [
    {
      "name": "Fastest Route",
      "eta": 28.1,
      "distance": 18.7,
      "signal_score": 48,
      "weighted_score": 62.5,
      "zones": ["Hosur Road", "Sarjapur Road"],
      "path": [
        {"lat": 12.9279, "lng": 77.6271},
        {"lat": 12.9698, "lng": 77.7499}
      ]
    },
    {
      "name": "Balanced Route",
      "eta": 36.5,
      "distance": 21.3,
      "signal_score": 50,
      "weighted_score": 58.0,
      "zones": ["Hosur Road", "Sarjapur Road", "HSR Layout", "Silk Board"]
    },
    {
      "name": "Best Signal Route",
      "eta": 47.6,
      "distance": 23.8,
      "signal_score": 45,
      "weighted_score": 55.2,
      "zones": ["HSR Layout", "BTM Layout", "Koramangala", "Jayanagar", "Indiranagar"]
    }
  ],
  "recommended_route": "Fastest Route"
}
```

---

### GET /api/heatmap

Returns signal quality data for all 20 Bangalore zones.

**Response:**

```json
{
  "zones": [
    {
      "name": "MG Road",
      "lat": 12.9716,
      "lng": 77.5946,
      "score": 78,
      "signal_strength": "strong",
      "color": "#22c55e"
    },
    {
      "name": "Electronic City",
      "lat": 12.8399,
      "lng": 77.667,
      "score": 32,
      "signal_strength": "weak",
      "color": "#ef4444"
    }
  ]
}
```

Signal strength levels:
- **strong** (score >= 60): Green `#22c55e`
- **medium** (score 40-59): Yellow/amber `#f59e0b`
- **weak** (score < 40): Red `#ef4444`

---

### GET /api/predict

Predict signal quality for a zone at a future time.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `zone` | string | "Electronic City" | Zone name |
| `minutes` | int | 15 | Prediction horizon |

**Response:**

```json
{
  "zone": "Electronic City",
  "horizon_minutes": 15,
  "expected_signal_score": 28,
  "message": "Weak signal expected near Electronic City in 15 mins"
}
```

---

### POST /api/reroute

Request a reroute when signal degrades during navigation.

**Request Body:**

```json
{
  "source": "MG Road",
  "destination": "Electronic City",
  "current_zone": "Hosur Road",
  "preference": 70,
  "telecom": "jio"
}
```

**Response:**

```json
{
  "message": "Rerouted to avoid weak signal zones",
  "selected_route": { ... },
  "advisory": "New route avoids Electronic City dead zone. ETA increased by 8 minutes."
}
```

---

### GET /api/towers

Returns tower infrastructure summary.

**Response:**

```json
{
  "source": "opencellid",
  "count": 847,
  "operators": {"Jio": 312, "Airtel": 285, "Vi": 150, "BSNL": 100},
  "zones": {"MG Road": 89, "Koramangala": 76, ...},
  "radio_types": {"LTE": 620, "UMTS": 180, "GSM": 47},
  "towers_with_signal": 723
}
```

---

## ML Model API Surface (`/model/*`)

These endpoints expose the ML model for direct access, RL training, and tower management.

### PUT /model/auto-route

RL-powered automatic route selection using Thompson Sampling.

**Request Body:**

```json
{
  "user_id": "user_123",
  "source": "Koramangala",
  "destination": "Whitefield",
  "hour": 8.5,
  "purpose": "commute",
  "telecom": "jio"
}
```

### PUT /model/record-trip

Record trip outcome for RL profile updates.

```json
{
  "user_id": "user_123",
  "chosen_route": "Balanced Route",
  "signal_satisfaction": 4,
  "time_satisfaction": 3,
  "hour": 8.5,
  "purpose": "commute"
}
```

### PUT /model/user-patterns

Retrieve learned patterns for a user.

```json
{
  "user_id": "user_123"
}
```

### GET /model/refresh-towers

Refresh tower data from OpenCelliD API.

---

## Clean Architecture API (`/api/v1/*`)

Production-grade endpoints using the clean architecture backend (separate from the frontend-serving monolith).

### POST /api/v1/route

```json
{
  "origin": {"lat": 12.84, "lon": 77.67},
  "destination": {"lat": 12.97, "lon": 77.75},
  "weight": 0.5,
  "user_id": "optional_user_id"
}
```

**Response:**

```json
{
  "routes": [
    {
      "eta": 28.1,
      "signal_score": 72.5,
      "drop_prob": 0.08,
      "final_score": 0.7234,
      "geometry": [{"lat": 12.84, "lon": 77.67}, ...]
    }
  ]
}
```

### POST /api/v1/rl/update

```json
{
  "user_id": "user_123",
  "success": true
}
```

### GET /api/v1/health

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Error Responses

All endpoints return structured errors:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad request (invalid parameters) |
| 422 | Validation error (invalid coordinates, user_id, weight) |
| 500 | Internal server error (never exposes stack traces) |
