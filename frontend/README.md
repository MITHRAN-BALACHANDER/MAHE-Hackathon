# Cellular Maze Frontend

Dashboard client for Cellular Maze built with Next.js, TypeScript, Tailwind CSS, Leaflet, Axios, and Chart.js.

## Run Locally

```bash
npm install
npm run dev
```

App runs at http://localhost:3000.

## Environment

Create .env.local if needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Features

- Source and destination search
- ETA vs signal preference slider
- Route comparison cards for Fastest, Balanced, and Best Signal
- Interactive map with route overlays and signal zones
- Heatmap legend and signal chart
- Predictive alert banner and reroute action
