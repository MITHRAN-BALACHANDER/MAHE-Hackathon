# Deployment Guide

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- MongoDB (local or Atlas)
- pnpm (or npm)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

pip install -r requirements.txt
cp .env.example .env  # Edit with your values

uvicorn main:app --reload --port 8000
```

Backend: http://localhost:8000
API Docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
pnpm install  # or: npm install
pnpm dev      # or: npm run dev
```

Frontend: http://localhost:3000

### 3. Docker Compose (Both Services)

```bash
docker compose up --build
```

This starts backend (port 8000) and frontend (port 3000).

---

## Production Deployment

### Frontend (Vercel)

1. Connect GitHub repo to Vercel
2. Set root directory: `frontend`
3. Framework: Next.js (auto-detected)
4. Environment variables:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.railway.app
   ```
5. Build command: `pnpm build`
6. Output: `.next`

### Backend (Railway / Render)

#### Railway

1. Connect GitHub repo
2. Set root directory: `backend`
3. Start command:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. Environment variables:
   ```
   MONGO_URI=mongodb+srv://...
   DB_NAME=cellularmaze
   MODEL_URL=http://ml-service:8001
   OSRM_URL=http://router.project-osrm.org
   ```

#### Render

1. Create Web Service from GitHub
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add same environment variables as above

### Database (MongoDB Atlas / Supabase)

#### MongoDB Atlas (Recommended)

1. Create free M0 cluster at https://cloud.mongodb.com
2. Create database user
3. Whitelist IP (or allow all: 0.0.0.0/0)
4. Get connection string:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxx.mongodb.net/cellularmaze
   ```
5. Set as `MONGO_URI` in backend environment

---

## Docker Production Build

### Backend

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Full Stack

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - MONGO_URI=mongodb://mongo:27017
      - DB_NAME=cellularmaze
    depends_on: [mongo]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on: [backend]

  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

volumes:
  mongo_data:
```

---

## Environment Variables Reference

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Frontend | `http://localhost:8000` | Backend API base URL |
| `MONGO_URI` | Backend | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | Backend | `cellularmaze` | Database name |
| `MODEL_URL` | Backend | `http://localhost:8001` | ML prediction service URL |
| `OSRM_URL` | Backend | `http://router.project-osrm.org` | OSRM routing engine URL |
| `ML_TIMEOUT_S` | Backend | `5.0` | ML call timeout (seconds) |
| `OSRM_TIMEOUT_S` | Backend | `10.0` | OSRM call timeout (seconds) |
