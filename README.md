# SignalRoute AI

SignalRoute AI is a hackathon-ready smart navigation platform that compares route options using travel time and cellular network quality. It helps users choose between speed and connectivity with a real-time preference slider.

## Core Capabilities

- Route comparison for:
  - Fastest Route
  - Balanced Route
  - Best Signal Route
- Adjustable routing strategy:
  - 0 means prioritize ETA
  - 100 means prioritize connectivity
- Bangalore signal intelligence:
  - MG Road strong
  - Electronic City weak
  - Whitefield medium
  - Airport Road medium
  - Koramangala strong
- Predictive warning support:
  - Example: Weak signal expected near Electronic City in 15 mins

## Monorepo Structure

```text
signalroute-ai/
|-- README.md
|-- .gitignore
|-- docker-compose.yml
|-- backend/
|   |-- requirements.txt
|   `-- app/
|       |-- main.py
|       |-- models/
|       |-- routes/
|       |-- schemas/
|       |-- services/
|       `-- utils/
|-- frontend/
|   |-- package.json
|   `-- src/
|       |-- app/
|       |-- components/
|       |-- hooks/
|       |-- lib/
|       `-- types/
`-- datasets/
    |-- bangalore_signal_mock.json
    |-- routes_seed.json
    `-- towers_mock.csv
```

## Tech Stack

### Frontend

- Next.js (App Router)
- TypeScript
- Tailwind CSS
- Leaflet (interactive route map)
- Axios
- Chart.js (route signal charts)

### Backend

- FastAPI
- Python 3.11
- Uvicorn
- Pandas
- NumPy
- scikit-learn

## Local Development

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL: http://localhost:8000

Swagger Docs: http://localhost:8000/docs

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: http://localhost:3000

### 3) Run Both with Docker Compose

```bash
docker compose up
```

## API Endpoints

### `GET /`

Returns API welcome payload.

### `GET /health`

Returns health status.

### `GET /api/routes?source=MIT&destination=Airport&preference=50&telecom=all`

Returns scored route recommendations.

Sample route entry:

```json
{
  "name": "Fastest Route",
  "eta": 32,
  "distance": 18,
  "signal_score": 62
}
```

### `GET /api/heatmap`

Returns zone signal strengths with color coding.

### `GET /api/predict`

Returns predicted signal quality in upcoming minutes.

### `POST /api/reroute`

Recommends a reroute toward stronger connectivity.

## Scoring Logic

Route score uses preference-controlled weights:

```text
score = (signal_weight * signal_score) - (time_weight * eta)
```

Where:

- `signal_weight = preference / 100`
- `time_weight = 1 - signal_weight`

## Deployment Notes

### Frontend (Vercel)

- Project root: frontend
- Build command: npm run build
- Output: .next
- Environment variable: NEXT_PUBLIC_API_URL=<backend_url>

### Backend (Render or Railway)

- Project root: backend
- Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
- Runtime: Python 3.11

## Bonus Features Included in UI

- Telecom mode selector (All, Jio, Airtel, Vi)
- Emergency route mode toggle
- Offline map advisory alert
