# Cellular Maze -- Enterprise Architecture Overview

## System Context

Cellular Maze is a cellular network-aware routing system that scores candidate routes based on predicted signal quality, ETA, and distance. It uses a physics-based ML model, real cell tower data, and Thompson Sampling RL for per-user personalization.

```mermaid
graph TB
    subgraph Users
        A[Mobile User]
        B[Desktop User]
    end

    subgraph Frontend
        C[Next.js 16 App]
    end

    subgraph Backend["API Gateway - FastAPI"]
        D[Route Service]
        E[Signal Service]
        F[Scoring Service]
        G[RL Service]
        H[Auth Service]
        I[Network Detection]
    end

    subgraph External
        J[TomTom Routing API]
        K[OpenCelliD Towers]
        L[Nominatim Geocoding]
        M[ipapi.co ISP Lookup]
    end

    subgraph Data
        N[MongoDB]
        O[PyTorch Model]
        P[Tower Registry]
    end

    A --> C
    B --> C
    C --> D
    C --> H
    C --> I
    D --> E
    D --> F
    D --> G
    D --> J
    E --> K
    E --> O
    E --> P
    F --> O
    G --> N
    I --> M
    H --> N
    D --> L
```

## Container Architecture

```mermaid
graph LR
    subgraph "Frontend Container"
        FE["Next.js 16<br/>React 19<br/>Leaflet Maps"]
    end

    subgraph "API Gateway Container"
        GW["FastAPI<br/>Uvicorn<br/>CORS + Middleware"]
    end

    subgraph "Service Bus"
        SB["gRPC-like<br/>Internal Bus<br/>Circuit Breaker"]
    end

    subgraph "Services"
        RS["Route Service"]
        SS["Signal Service"]
        SC["Scoring Service"]
        RL["RL Service"]
    end

    subgraph "ML Container"
        ML["ResidualSignalNet<br/>PyTorch<br/>COST-231 Hata"]
    end

    subgraph "Data Layer"
        DB["MongoDB<br/>Motor Async"]
        TD["Tower Data<br/>JSON/CSV"]
    end

    FE -->|HTTP/REST| GW
    GW -->|ServiceBus.call| SB
    SB --> RS
    SB --> SS
    SB --> SC
    SB --> RL
    RS --> ML
    SS --> ML
    RL --> DB
    SS --> TD
```

## Internal Service Bus (gRPC-like)

```mermaid
sequenceDiagram
    participant Client as Next.js Frontend
    participant GW as API Gateway
    participant Bus as Service Bus
    participant RS as Route Service
    participant SS as Signal Service
    participant SC as Scoring Service

    Client->>GW: GET /api/routes?source=A&dest=B
    GW->>Bus: call("route_service", "get_routes", {})
    Bus->>RS: ServiceRequest(method="get_routes")
    RS->>Bus: call("signal_service", "predict_batch")
    Bus->>SS: ServiceRequest(method="predict_batch")
    SS-->>Bus: SignalPredictions[]
    Bus-->>RS: ServiceResponse(data=predictions)
    RS->>Bus: call("scoring_service", "rank")
    Bus->>SC: ServiceRequest(method="rank")
    SC-->>Bus: RankedRoutes[]
    Bus-->>RS: ServiceResponse(data=ranked)
    RS-->>Bus: ServiceResponse(data=routes)
    Bus-->>GW: ServiceResponse(success=true)
    GW-->>Client: RoutesResponse JSON
```

## Route Request Flow (Complete)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant TT as TomTom API
    participant OC as OpenCelliD
    participant ML as ML Model
    participant RL as RL Engine

    U->>FE: Enter source + destination
    FE->>API: GET /api/routes
    API->>API: Resolve locations (geocode)

    alt Has TomTom API key
        API->>TT: Calculate routes
        TT-->>API: Route geometries + ETAs
    else Fallback
        API->>API: Generate synthetic routes
    end

    API->>OC: Fetch towers along route path
    OC-->>API: Tower locations + metadata

    loop For each route segment
        API->>ML: Extract features → Predict signal
        ML-->>API: Signal strength prediction
    end

    API->>API: Score routes (weighted signal + ETA)
    API->>API: Detect bad zones
    API->>API: Assess task feasibility

    opt User has RL profile
        API->>RL: Thompson Sampling predict
        RL-->>API: Learned preference weight
        API->>API: Re-score with RL weight
    end

    API-->>FE: Ranked routes + metadata
    FE->>FE: Render on map with tooltips
    FE-->>U: Interactive route visualization
```

## ISP/Carrier Detection Flow

```mermaid
sequenceDiagram
    participant U as User Device
    participant FE as Next.js Frontend
    participant API as FastAPI Backend
    participant IP as ipapi.co

    Note over U,FE: Phase 1: Browser API (instant)
    U->>FE: Page load
    FE->>FE: navigator.connection API
    FE->>FE: Detect: wifi/cellular, effectiveType, downlink

    Note over FE,IP: Phase 2: Backend IP Lookup
    FE->>API: GET /api/detect-network
    API->>API: Extract IP (X-Forwarded-For → X-Real-IP → client.host)
    API->>IP: GET /json/ (IP geolocation)
    IP-->>API: ISP, org, ASN, country, city

    API->>API: Map ISP to carrier (Jio/Airtel/Vi)
    API->>API: Detect VPN (ASN keywords)
    API->>API: Guess connection type (cellular vs wifi)
    API-->>FE: NetworkDetectResponse

    FE->>FE: Set detected provider
    FE->>FE: Auto-select telecom filter
    FE-->>U: "Detected: Airtel" in filter panel

    Note over U,FE: Limitations
    Note right of U: Wi-Fi → ISP shown, not SIM carrier
    Note right of U: VPN → VPN provider shown
    Note right of U: eSIM → Cannot detect active SIM
```

## RL Personalization Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant RL as Thompson Sampling
    participant DB as MongoDB

    Note over U,DB: Trip 1-2: Exploration Phase
    U->>FE: Request route
    FE->>API: PUT /model/auto-route
    API->>RL: Sample from prior (Beta(1,1))
    RL-->>API: Random intent prediction
    API-->>FE: Route with default preference

    U->>FE: Complete trip (chose "signal" route)
    FE->>API: PUT /model/record-trip
    API->>RL: Update Beta distributions
    RL->>DB: Save updated profile

    Note over U,DB: Trip 3-5: Convergence Phase
    U->>FE: Request route (same pattern)
    FE->>API: PUT /model/auto-route
    API->>RL: Sample from learned posterior
    RL-->>API: "signal" intent (85% confidence)
    API->>API: Blend: 0.6×user_pref + 0.4×RL_pref
    API-->>FE: Personalized route ranking
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Next.js
    participant API as FastAPI
    participant JWT as JWT Module

    alt New User
        U->>FE: Fill register form
        FE->>API: POST /api/v1/register
        API->>API: Validate + store user
        API->>JWT: Create access token
        JWT-->>API: JWT token (24h expiry)
        API-->>FE: TokenResponse
        FE->>FE: Store in localStorage
        FE->>FE: Set cellularmaze_first_visit flag
        FE->>U: Redirect to map + onboarding tour
    else Returning User
        U->>FE: Fill login form
        FE->>API: POST /api/v1/login
        API->>API: Verify credentials
        API->>JWT: Create access token
        JWT-->>API: JWT token
        API-->>FE: TokenResponse
        FE->>FE: Store in localStorage
        FE->>U: Redirect to map
    end
```

## Scoring Formula

The weighted score combines signal quality and travel time:

```
weighted_score = (signal_weight × signal_score) + ((1 - signal_weight) × eta_score)
```

Where:
- `signal_weight` = user preference (0-100) / 100, optionally adjusted by RL
- `signal_score` = ML-predicted average signal strength along route (0-100)
- `eta_score` = normalized ETA score (100 = fastest, scaled inversely)

### Signal Score Computation

```
signal_at_point = predict(
    distance_to_nearest_tower,
    tower_frequency,
    tower_type (4G/3G/2G),
    time_of_day,
    weather_factor,
    vehicle_speed
)

route_signal_score = mean(signal_at_point for each sampled point)
```

### Physics Model (COST-231 Hata + Residual ML)

```
path_loss(dB) = 46.3 + 33.9·log10(f) - 13.82·log10(hb)
                - a(hm) + (44.9 - 6.55·log10(hb))·log10(d) + C

signal_strength = ResidualSignalNet(
    physics_features=[path_loss, distance, frequency, height],
    context_features=[time, weather, speed, tower_density]
)
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 16, React 19 | SSR + client-side rendering |
| Styling | Tailwind CSS 4 | Utility-first CSS |
| Maps | Leaflet + react-leaflet | Interactive map rendering |
| Animation | Framer Motion | UI micro-animations |
| Icons | Lucide React | Consistent icon system |
| API Client | Axios + React Query | Data fetching + caching |
| Backend | FastAPI + Uvicorn | Async API server |
| ML | PyTorch | Signal prediction model |
| RL | Thompson Sampling (custom) | User preference learning |
| Database | MongoDB + Motor | Async document store |
| Routing | TomTom API / OSRM | Road-network routing |
| Towers | OpenCelliD API | Cell tower registry |
| Geocoding | Nominatim (OSM) | Location search |
| ISP Detection | ipapi.co | IP-based carrier lookup |
| Auth | JWT (PyJWT) | Token-based authentication |

## Data Flow Summary

```mermaid
flowchart LR
    A[User Input] --> B[Geocode]
    B --> C[Generate Routes]
    C --> D[Fetch Towers]
    D --> E[ML Predict Signals]
    E --> F[Score & Rank]
    F --> G[RL Personalize]
    G --> H[Return to UI]
    H --> I[Render on Map]

    style A fill:#3b82f6,color:white
    style H fill:#3b82f6,color:white
    style I fill:#22c55e,color:white
```

## Scaling Considerations

| Concern | Current Solution | Production Path |
|---------|-----------------|-----------------|
| ML Inference | In-process PyTorch | TorchServe / Triton on GPU |
| Tower Data | JSON file + API | Redis cache + periodic refresh |
| User Profiles | In-memory / MongoDB | MongoDB sharded cluster |
| Routing | TomTom API (external) | Self-hosted OSRM for cost |
| Geocoding | Nominatim (external) | Self-hosted Nominatim |
| ISP Detection | ipapi.co (1000/day) | MaxMind GeoLite2 (local DB) |
| Auth | In-memory JWT | OAuth2 + Redis session store |
| Monitoring | Structured logging | Prometheus + Grafana |
