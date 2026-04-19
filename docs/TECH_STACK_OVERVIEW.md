# Cellular Maze: Complete Tech Stack Overview
### Architecture, Frameworks, and Cloud Infrastructure

This document breaks down the entire technology stack utilized across the Cellular Maze platform, categorizing each tool and explaining the engineering justification for why it was selected.

---

## 1. Frontend Architecture (Web Client & UI)

The frontend is built to be a highly reactive, glassmorphic Single Page Application (SPA) prioritizing fluid map animations and rapid data re-rendering.

| Technology | Version | Role in Project | Engineering Justification |
| :--- | :--- | :--- | :--- |
| **Next.js** | 16.2.4 | Meta-framework | Chosen for its robust App Router (`src/app`), Turbopack compiler speeds, and seamless API routing. Allows strict separation of Server and Client components which is vital for heavy GIS map rendering. |
| **React** | 19.0.0 | Core UI Library | Powers the component lifecycle. Utilizes React 19's native hooks (`use` API, action limits) for state concurrency during heavy data parsing. |
| **TypeScript** | 5.x | Language / Types | Enforces rigid request/response interfaces mapping exactly to the Pydantic schemas on the backend, preventing undefined runtime crashes when reading complex GeoJSON data. |
| **Tailwind CSS** | 4.0 | Styling Engine | Utility-first CSS framework. Used to construct the complex glassmorphism effects (backdrop-blurs, ring offsets) and responsive layouts without bloated CSS files. |
| **Leaflet & React-Leaflet** | 1.9.4 | GIS / Map Engine | We chose Leaflet over Google Maps API or Mapbox GL because it is entirely open-source, lightweight, and supports native SVG injection for cell towers and custom multi-colored polyline rendering. |
| **React Query (@tanstack)** | 5.99 | Async State Management | Handles the caching, deduping, and background-refreshing of HTTP requests (polling route updates, heatmap tiles) seamlessly outside of native React state. |
| **Framer Motion** | 12.38 | Animation Library | Drives the layout transitions, sidebar sliding mechanics, and toaster popups. Essential for hitting the "premium UX" metric required in the hackathon pitch. |
| **Axios** | 1.15 | HTTP Client | Promise-based client used to construct backend HTTP requests with strict timeout policies and header injections. |
| **Chart.js** | 4.x | Data Visualization | Used for plotting signal variations over route segment charts in the route breakdown modals. |

---

## 2. Backend Architecture (API Gateway & Services)

The backend acts as an Enterprise Modular Monolith. It serves the frontend, handles real-time spatial physics, and acts as the bridge to the PyTorch inference core.

| Technology | Version | Role in Project | Engineering Justification |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11 | Core Language | Selected because Machine Learning and Spatial Mathematics natively live in the Python ecosystem. |
| **FastAPI** | 0.115 | Web Framework | A massive upgrade over Flask/Django. Natively asynchronous, incredibly fast (built on Starlette), and provides free OpenAPI 3.1 (Swagger) documentation automatically. |
| **Uvicorn** | 0.30 | ASGI Server | The lightning-fast Async Server Gateway Interface running the FastAPI loops under the hood, easily containerized. |
| **Pydantic** | 2.5 | Data Validation | Intercepts HTTP JSON requests, parsing them strictly into Python primitives. Immediately rejects malformed coordinates with HTTP 422 before hitting the ML models. |
| **NumPy** | 1.26 | Mathematics Matrix | Vectorizes heavy spatial mathematics (Haversine distances over arrays of 500 points) utilizing C-backend acceleration instead of slow Python loops. |
| **HTTPX** | 0.26 | Async HTTP Calls | Replaces the standard `requests` library to prevent asynchronous event-loop blocking when calling out to external APIs (TomTom, Geocoders). |
| **Motor (pymongo)** | 3.6 | Database Driver | The official asynchronous driver for MongoDB. Allows concurrent background DB writes for Reinforcement Learning state storage without stalling the API responses. |

---

## 3. Artificial Intelligence & Machine Learning

The ML pipeline merges empirical physics mapping with Deep Learning and Reinforcement parameter scaling.

| Technology | Role in Project | Engineering Justification |
| :--- | :--- | :--- |
| **PyTorch (2.x) + CUDA** | Neural Network Backbone | Used to build `ResidualSignalNet`. Preferred over TensorFlow for its dynamic computation graphing (`autograd`), which made building our 3-head multi-task learning array significantly easier. Ran locally with Nvidia CUDA acceleration for rapid training loops. |
| **Scikit-Learn** | Feature Engineering | Handles data preprocessing: Standardization (`StandardScaler`), train/test splitting, and evaluating $R^2$ regression metrics post-training. |
| **Pandas** | Tabular Data Parsing | Reads and manipulates the OpenCelliD tower CSVs and structures the synthetic training sets. |
| **Thompson Sampling (Custom)** | Reinforcement Learning | A Bayesian statistical approach to Contextual Bandits. We wrote standard Beta-Bernoulli distributions mathematically instead of using a heavy framework like OpenAI Gym, because it solves sparse-reward optimization rapidly. |

---

## 4. Cloud Infrastructure & DevOps

The deployment stack ensures that multiple users can access the application remotely without tearing down the internal services.

| Technology | Role in Project | Engineering Justification |
| :--- | :--- | :--- |
| **Docker & Docker Compose** | Containerization | Packages the API and Frontend into portable linux images ensuring that "it works on my machine" translates flawlessly to cloud deployments. |
| **MongoDB Atlas (M0 Tier)** | Persistence / Cloud DB | A free-tier NoSQL cloud database chosen for its JSON document nature. User Reinforcement Learning patterns naturally fit inside JSON documents instead of strict SQL tables. |
| **Vercel** | Frontend Edge Hosting | The premier hosting platform for Next.js. Deploys the frontend React application automatically onto global Edge CDNs whenever the `main` branch updates. |
| **Railway / Render** | Backend API Hosting | Cloud PaaS (Platform as a Service) providers capable of mapping Docker images and running python `uvicorn` web servers attached to public IP addresses with zero configuration. |
| **NGROK** | Tunneling Endpoint | Used during live demonstration phases to securely port-forward local machine connections (localhost:8000) directly to external judge devices via a secure HTTPS tunnel. |

---

## 5. External APIs / Data Providers

Because real geographic and physical mapping is required to generate accurate routes, we integrated 4 distinct external data streams.

| Provider | Data Scope | Engineering Justification |
| :--- | :--- | :--- |
| **TomTom Routing API** | Geographic Navigation | Replaced standard string-distance APIs. Provides true road-snapped geometries, precise ETA metrics, traffic congestion delays, and multiple parallel route generation endpoints essential for map plotting. |
| **OpenStreetMap (Nominatim)** | Geocoding | Reverse and Forward geocoding. Converts strings ("Electronic City") into hard `(lat, lng)` tuples needed for mathematical routing, without requiring payment configurations or bounds limits like Google's Geocoding API. |
| **OpenCelliD** | Telecommunications Infrastructure | The world's largest open database of cell towers. We stream actual Base Station locations (Latitude, Longitude), Radio Types (UMTS/LTE), Carrier IDs (MCC/MNC), and Signal Radios to feed the physics priors. |
| **OpenWeather API** | Signal Decay Modification | Integrated into the backend to query active Rain/Atmospheric states across the route's bounding box. Rain explicitly creates high-frequency signal attenuation (loss of signal), adjusting our predictive models in real-time. |
| **IPAPI.co** | Carrier / ISP Detection | Scans connected user IP addresses determining network ASNs, letting the browser auto-calculate whether the user is on Airtel, Jio, or a masked VPN tunnel before generating map states. |
