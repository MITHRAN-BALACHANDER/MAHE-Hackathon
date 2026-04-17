# System Design Review -- Connectivity-Aware Routing

## 1. Problem Statement vs Your Design -- Alignment Check

### What the problem actually asks for

| Requirement | Source |
|---|---|
| Prototype that **scores and visualizes connectivity** along candidate routes | Problem statement |
| Let users compare **fastest vs most-connected** paths with a **simple weighting control** (slider) | Problem statement |
| Map UI with **connectivity heat overlays** and a **route Connectivity Score** | Expected outcome |
| **Side-by-side comparison** of two routes with a connectivity-vs-ETA trade-off slider | Expected outcome |
| Brief **write-up of assumptions/heuristics** and data sources | Expected outcome |

### Where your design goes beyond (or diverges from) the problem

| Your Feature | Verdict | Reason |
|---|---|---|
| L4 autonomous vehicle framing | **Remove** | Problem says nothing about autonomous vehicles. It is about general routing for navigation/ride-hailing. Framing it as L4 adds complexity with no scoring benefit. |
| Multi-SIM / multi-carrier aggregation with beta weighting | **Simplify** | Problem mentions coverage varies with tower density. Per-carrier filtering (like your frontend already does with Jio/Airtel/Vi toggle) is fine. The multi-SIM aggregation formula is over-engineered. |
| ML supervised model for connectivity prediction | **Replace with heuristic** | You have no labeled training data. Mock data has 15 towers. A supervised model cannot be trained or validated meaningfully. Heuristic scoring is honest and sufficient. |
| User intent modes (CALL, MEETING, DOWNLOAD) | **Remove or demo-only** | Problem asks for a single connectivity-vs-ETA slider, not 4 task modes. If you want to impress, keep it as a dropdown but it should not be core. |
| Vehicle SIM vs User SIM priority | **Remove** | Not in scope. This is an L4-specific concept the problem does not address. |
| Bad zone prediction with time estimates | **Keep (simplified)** | This is a strong differentiator. "Network drop expected in 3 min for 2 min" is impressive and aligns with reducing drop-outs. But implement it as a heuristic, not ML. |
| Confidence score / explainability layer | **Defer** | Nice on a slide, but low ROI for hackathon demo. Focus on core scoring first. |
| Pre-buffer suggestion | **Defer** | Edge case feature. Not worth implementation time. |

### Bottom line

Your design is **~60% aligned** with the problem statement but **~3x over-scoped**. In a hackathon, judges reward a **working demo that nails the core ask** over an ambitious slide deck with a broken or incomplete prototype. Your frontend is already strong -- the gap is the backend, which does not exist yet.

---

## 2. Flaws and Unrealistic Assumptions

### Flaw 1 -- ML without data

You propose a supervised model that outputs `connectivity_score` and `drop_probability` per segment. This requires:
- Ground-truth labeled data (real signal measurements along routes)
- Sufficient volume for train/val/test split
- Feature engineering that maps to real-world signal behavior

You have 15 mock tower entries and 5 zones. A supervised model here is theater -- it will memorize the mock data and generalize to nothing. **Use a deterministic heuristic instead.**

### Flaw 2 -- Segment granularity is undefined

"Each route is split into small segments" -- how small? 100m? 500m? Per-GPS-point? This matters because:
- Too fine = slow computation, noisy scores
- Too coarse = miss dead zones
- Your mock routes have ~10-15 coordinate points each, which is already coarse

**Recommendation**: Use the coordinate points from the routing API directly. Each polyline segment between two consecutive points is one segment.

### Flaw 3 -- Tower data assumptions

You assume tower location = coverage. Real-world signal depends on:
- Antenna height, tilt, power
- Frequency band (700MHz vs 2100MHz vs 3500MHz have vastly different propagation)
- Building obstruction, terrain

Since you are using mock data anyway, acknowledge this in your write-up and use **distance-to-tower as a proxy with decay function**. That is honest and defensible.

### Flaw 4 -- Multi-SIM formula is not grounded

```
multi_sim_score = beta * min(connectivity_per_sim) + (1 - beta) * avg(connectivity_per_sim)
```

Why min? If one SIM has great signal, the device uses that one. The correct model for multi-SIM is **max** (best available), not min. Min penalizes having a weak secondary SIM, which makes no practical sense.

### Flaw 5 -- Constraint thresholds are arbitrary

```
ETA <= k * shortest_route_time
```

What is k? 1.2? 1.5? 2.0? This needs to be defined and justified. For a hackathon, use `k = 1.5` (allow up to 50% longer travel time) and state the assumption.

---

## 3. What You Should Actually Build (Hackathon-Feasible Approach)

### Architecture (simplified, buildable)

```
Frontend (Next.js) -- already built
    |
    v
FastAPI Backend
    |
    +-- GET /api/routes?source=...&destination=...&preference=...&telecom=...
    |       1. Load candidate routes from routes_seed.json (or generate via OSRM)
    |       2. For each route, score connectivity using tower data
    |       3. Compute combined score using preference slider weight
    |       4. Return ranked routes with metrics
    |
    +-- GET /api/heatmap
    |       1. Load tower data from towers_mock.csv
    |       2. Return zone-level signal strengths for map overlay
    |
    +-- GET /api/predict?zone=...&minutes=...
    |       1. Simple lookup/interpolation from time-series mock data
    |       2. Return predicted signal quality
    |
    +-- POST /api/reroute
            1. Re-score routes with updated signal data
            2. Return new recommendation
```

### Scoring Algorithm (heuristic, no ML needed)

```python
def score_route_connectivity(route_coords, towers_df, telecom_filter=None):
    """Score a route's connectivity based on tower proximity and density."""
    
    if telecom_filter and telecom_filter != "All":
        towers_df = towers_df[towers_df["operator"] == telecom_filter]
    
    segment_scores = []
    for lat, lon in route_coords:
        # Distance to nearest tower (Haversine)
        distances = haversine_vectorized(lat, lon, towers_df)
        nearest_distance_km = distances.min()
        towers_within_2km = (distances < 2.0).sum()
        
        # Signal decay model: score drops with distance
        # Assume usable range ~5km, strong within 1km
        if nearest_distance_km < 0.5:
            signal = 95
        elif nearest_distance_km < 1.0:
            signal = 80
        elif nearest_distance_km < 2.0:
            signal = 60
        elif nearest_distance_km < 3.5:
            signal = 35
        else:
            signal = 10  # dead zone
        
        # Density bonus: more towers = more reliable
        density_bonus = min(towers_within_2km * 3, 15)
        segment_scores.append(min(signal + density_bonus, 100))
    
    return {
        "avg_connectivity": mean(segment_scores),
        "min_connectivity": min(segment_scores),
        "drop_segments": sum(1 for s in segment_scores if s < 30),
        "continuity": std_dev_penalty(segment_scores),
        "segments": segment_scores  # for heatmap coloring
    }


def rank_routes(routes, preference, telecom):
    """
    preference: 0 = fastest, 100 = best signal
    """
    signal_weight = preference / 100
    time_weight = 1 - signal_weight
    
    for route in routes:
        conn = score_route_connectivity(route["path"], towers, telecom)
        
        # Normalize ETA (lower is better, invert to 0-100 scale)
        eta_score = 100 * (1 - route["eta"] / max_eta)
        
        route["combined_score"] = (
            signal_weight * conn["avg_connectivity"] +
            time_weight * eta_score
        )
        route["connectivity"] = conn
    
    return sorted(routes, key=lambda r: r["combined_score"], reverse=True)
```

### Bad Zone Warning (heuristic, not ML)

```python
def detect_bad_zones(route_coords, segment_scores, avg_speed_kmh):
    """Find contiguous low-signal segments and estimate time-to-zone."""
    bad_zones = []
    current_zone = None
    
    for i, (coord, score) in enumerate(zip(route_coords, segment_scores)):
        if score < 30:  # threshold for "bad"
            if current_zone is None:
                current_zone = {"start_idx": i, "segments": []}
            current_zone["segments"].append(i)
        else:
            if current_zone:
                current_zone["end_idx"] = i - 1
                bad_zones.append(current_zone)
                current_zone = None
    
    # For each zone, estimate time-to-arrival and duration
    for zone in bad_zones:
        distance_to_zone = sum_segment_distances(route_coords[:zone["start_idx"]])
        zone_length = sum_segment_distances(
            route_coords[zone["start_idx"]:zone["end_idx"]+1]
        )
        zone["eta_minutes"] = (distance_to_zone / avg_speed_kmh) * 60
        zone["duration_minutes"] = (zone_length / avg_speed_kmh) * 60
    
    return bad_zones
```

---

## 4. What to Add That Will Impress Judges

These are **low-effort, high-impact** additions aligned with the problem:

### 4a. Per-segment heatmap coloring on routes

Instead of uniform route colors, color each segment of the polyline based on its signal score (green/yellow/red). Your frontend already has a `HeatmapLegend` component. Wire it to actual per-segment data.

**Implementation**: Return `segment_scores[]` from backend. In `RouteMapClient.tsx`, render each segment as a separate polyline with color mapped from score.

### 4b. "Why this route?" tooltip

When a route is recommended, show a one-line explanation:
- "Selected because it avoids a 2km dead zone on Electronic City flyover"
- "Fastest route with acceptable signal (avg 72%)"

This is the "explainability" from your design, but implemented as a simple string template, not an ML system.

### 4c. Connectivity timeline chart

Show signal score along the route as a line chart (x-axis = distance or segment index, y-axis = signal). This immediately visualizes where drops happen. Your `SignalChart.tsx` already exists -- extend it from bar chart to line chart per route.

### 4d. Emergency mode

Your frontend already has an emergency toggle. When enabled, set `preference = 100` (max connectivity) and filter to the strongest carrier. Simple, but tells a compelling story for the "Emergency Vehicles" significance point in the problem statement.

---

## 5. Recommended Implementation Priority

Given that your **backend does not exist yet**, here is the order:

| Priority | Task | Time Estimate | Impact |
|---|---|---|---|
| P0 | FastAPI backend with `/api/routes` scoring (heuristic) | Core | **Critical** -- nothing works without this |
| P0 | Wire existing frontend to backend responses | Core | **Critical** -- demo needs live data |
| P1 | Per-segment heatmap coloring on map | Medium | **High** -- visual wow factor |
| P1 | `/api/heatmap` endpoint returning zone data | Quick | **High** -- judges see the map |
| P2 | Bad zone warning with time estimate | Medium | **High** -- differentiator |
| P2 | "Why this route?" explanation string | Quick | **Medium** -- shows thoughtfulness |
| P3 | Connectivity timeline chart | Medium | **Medium** -- nice visualization |
| P3 | Emergency mode backend logic | Quick | **Low** -- frontend already handles it |
| P4 | Multi-carrier filtering | Quick | **Low** -- already in frontend state |

---

## 6. What to Remove / Not Mention

| Feature | Why |
|---|---|
| L4 autonomous vehicle | Not in problem statement. Judges may question why you are solving a different problem. |
| Supervised ML model | You have no real data. If asked, say "we use a distance-decay heuristic that could be replaced with ML given real signal measurement data." |
| Multi-SIM aggregation formula | Over-scoped. Just filter by carrier. |
| User intent modes (CALL/MEETING/DOWNLOAD) | Problem asks for one slider, not four modes. Keep the slider. |
| Vehicle SIM vs User SIM | Not relevant to the problem statement. |
| Pre-buffer suggestion | Cool but unimplementable in hackathon time. |

---

## 7. Assumptions to State in Your Write-Up

The problem statement asks for a "brief write-up of assumptions/heuristics and data sources." Include:

1. **Signal strength is approximated by distance to nearest tower** -- real signal depends on frequency, power, terrain, and interference, but tower proximity is a reasonable first-order proxy.
2. **Tower data is simulated** -- based on realistic Bangalore locations and operators. In production, this would use OpenCellID or carrier APIs.
3. **Routes are pre-computed** -- in production, these would come from OSRM, Google Maps, or Mapbox Directions API.
4. **Signal decay model uses step thresholds** -- a production system would use a log-distance path loss model calibrated to local measurements.
5. **Connectivity score is a weighted combination of signal strength and tower density** -- density provides redundancy and handoff reliability.
6. **The preference slider linearly interpolates between ETA-optimal and connectivity-optimal ranking** -- this is the simplest defensible trade-off model.

---

## 8. Final Verdict

**Your system design is well-thought-out for a production system, but it is not a hackathon design.** You are proposing to build what a telecom company would ship in 6 months. The hackathon asks for a prototype that demonstrates the concept.

**What will win**:
- A working demo where the slider actually changes the recommended route
- Routes colored by signal quality on a real map
- A clear explanation of the scoring logic
- The "network drop in 3 minutes" warning (if you have time)

**What will not win**:
- Slides describing ML models you did not train
- Multi-SIM formulas with no implementation
- Features that are not demonstrated live

**Focus all energy on making the backend work and the demo flow smoothly.**
