# Database Schema

SignalRoute uses MongoDB (via Motor async driver) for persistent storage and file-based datasets for signal/tower data.

## MongoDB Collections

### `rl_profiles`

Stores per-user reinforcement learning parameters for Thompson Sampling personalization.

```json
{
  "user_id": "user_123",
  "alpha": 3.0,
  "beta": 1.5,
  "updated_at": "2026-04-18T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string (unique index) | Alphanumeric identifier, 1-64 chars |
| `alpha` | float | Beta distribution alpha parameter (signal preference successes + 1) |
| `beta` | float | Beta distribution beta parameter (speed preference successes + 1) |
| `updated_at` | datetime | Last profile update timestamp (UTC) |

**Index:** `user_id` (unique)

**RL Logic:** Higher alpha/beta ratio means user historically preferred signal-optimized routes. System samples from Beta(alpha, beta) to personalize the weight parameter.

### `users`

```json
{
  "user_id": "user_123",
  "created_at": "2026-04-18T08:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string (unique index) | User identifier |
| `created_at` | datetime | Account creation timestamp |

**Index:** `user_id` (unique)

## File-Based Data

### Signal Zones (`datasets/bangalore_signal_mock.json`)

```json
{
  "zones": [
    {
      "name": "MG Road",
      "signal_strength": "strong",
      "score": 95,
      "lat": 12.9716,
      "lng": 77.5946
    }
  ]
}
```

### Cell Towers (`model/data/towers.csv`, `datasets/towers_mock.csv`)

CSV with columns: `lat`, `lon`, `operator`, `radio`, `signal_dbm`, `zone`

Real tower data sourced from OpenCelliD when available, falls back to synthetic data.

### Zone Configuration (`model/config.py`)

20 Bangalore zones with properties:

| Zone | Terrain | Density | Building Height |
|------|---------|---------|-----------------|
| MG Road | urban_main | high | 35m |
| Electronic City | suburban | medium | 20m |
| Whitefield | suburban | medium | 22m |
| Hebbal | highway | medium | 10m |
| Bannerghatta | suburban | low | 10m |
| ... | ... | ... | ... |

### Edge-Case Zones (`model/config.py`)

12 special zones with signal penalties:

| Zone | Type | Penalty (dB) |
|------|------|-------------|
| Namma Metro Tunnel MG Road | tunnel | 45 |
| Hebbal Flyover Underpass | underpass | 25 |
| Commercial Street Canyon | urban_canyon | 12 |
| ... | ... | ... |

## Indexes Created at Startup

```python
await db["rl_profiles"].create_index("user_id", unique=True)
await db["users"].create_index("user_id", unique=True)
```

Indexes are created automatically when the application starts via `MongoClient.connect()` in `backend/db/base.py`.
