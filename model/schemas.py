"""Pydantic request / response schemas for the model API."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class Coordinate(BaseModel):
    lat: float
    lng: float


class TowerInput(BaseModel):
    tower_id: str = ""
    lat: float
    lng: float
    operator: str = "Unknown"
    signal_score: float = 70.0
    frequency_mhz: int = 1800
    tx_power_dbm: float = 43.0
    height_m: float = 30.0
    range_km: float = 2.5
    zone: str = ""


class RouteInput(BaseModel):
    name: str = "Route"
    eta: float  # minutes
    distance: float  # km
    path: list[Coordinate]
    zones: list[str] = []


# ---------------------------------------------------------------------------
# PUT /model/score-routes
# ---------------------------------------------------------------------------

class ScoreRoutesRequest(BaseModel):
    routes: list[RouteInput]
    towers: list[TowerInput]
    preference: float = Field(50.0, ge=0, le=100, description="0=fastest, 100=best signal")
    telecom: str = "all"
    time_hour: float = Field(12.0, ge=0, lt=24)
    weather_factor: float = Field(1.0, ge=0, le=1, description="1=clear, 0.5=heavy rain")
    speed_kmh: float = Field(40.0, ge=0, le=200)


class SegmentDetail(BaseModel):
    signal_strength: float
    drop_probability: float
    handoff_risk: float
    color: str  # "strong" | "medium" | "weak"


class BadZone(BaseModel):
    start_index: int
    end_index: int
    start_coord: Coordinate
    end_coord: Coordinate
    length_km: float
    min_signal: float
    avg_signal: float
    time_to_zone_min: float
    zone_duration_min: float
    edge_zone_name: str | None
    reason: str
    warning: str


class TaskFeasibility(BaseModel):
    feasible: bool
    task_type: str
    reason: str
    required_duration_min: float = 0
    longest_stable_window_min: float = 0
    required_signal: float = 0
    avg_signal: float = 0


class RouteResult(BaseModel):
    name: str
    eta: float
    distance: float
    signal_score: float
    weighted_score: float
    zones: list[str]
    path: list[Coordinate]
    rejected: bool = False
    connectivity: dict  # full metrics
    bad_zones: list[BadZone]
    segments: list[SegmentDetail]
    task_feasibility: TaskFeasibility | None = None
    explanation: str = ""


class ScoreRoutesResponse(BaseModel):
    preference: float
    telecom: str
    recommended_route: str
    explanation: str
    routes: list[RouteResult]
    comparison: list[dict]
    edge_cases_detected: list[str]


# ---------------------------------------------------------------------------
# PUT /model/predict-signal
# ---------------------------------------------------------------------------

class PredictSignalRequest(BaseModel):
    lat: float
    lng: float
    towers: list[TowerInput]
    telecom: str = "all"
    time_hour: float = 12.0
    weather_factor: float = 1.0
    speed_kmh: float = 40.0


class PredictSignalResponse(BaseModel):
    lat: float
    lng: float
    signal_strength: float
    drop_probability: float
    handoff_risk: float
    edge_zone: str | None
    nearby_towers: int
    confidence: str  # "high" | "medium" | "low"


# ---------------------------------------------------------------------------
# PUT /model/analyze-route
# ---------------------------------------------------------------------------

class AnalyzeRouteRequest(BaseModel):
    route: RouteInput
    towers: list[TowerInput]
    telecom: str = "all"
    time_hour: float = 12.0
    weather_factor: float = 1.0
    speed_kmh: float = 40.0
    task_type: str = "call"
    task_duration_min: float = 10.0


class AnalyzeRouteResponse(BaseModel):
    name: str
    connectivity: dict
    bad_zones: list[BadZone]
    segments: list[SegmentDetail]
    task_feasibility: TaskFeasibility
    edge_cases_detected: list[str]


# ---------------------------------------------------------------------------
# PUT /model/detect-zones
# ---------------------------------------------------------------------------

class DetectZonesRequest(BaseModel):
    route: RouteInput
    towers: list[TowerInput]
    telecom: str = "all"
    time_hour: float = 12.0
    weather_factor: float = 1.0
    speed_kmh: float = 40.0


class DetectZonesResponse(BaseModel):
    bad_zones: list[BadZone]
    total_bad_zone_km: float
    total_bad_zone_min: float
    warnings: list[str]


# ---------------------------------------------------------------------------
# PUT /model/health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    towers_in_training: int
    samples_in_training: int


# ---------------------------------------------------------------------------
# PUT /model/smart-route  (intent-driven routing)
# ---------------------------------------------------------------------------

class SmartRouteRequest(BaseModel):
    user_id: str = "default"
    intent: str = Field("balanced", description="User intent: meeting, call, navigation, fastest, download, streaming, emergency, work, idle, best_signal")
    routes: list[RouteInput]
    towers: list[TowerInput]
    telecom: str = "all"
    time_hour: float = Field(12.0, ge=0, lt=24)
    weather_factor: float = Field(1.0, ge=0, le=1)
    speed_kmh: float = Field(40.0, ge=0, le=200)


class SmartRouteResponse(BaseModel):
    user_id: str
    intent: str
    resolved_preference: float
    preference_source: str
    task_type: str
    task_duration_min: float
    intent_description: str
    recommended_route: str
    explanation: str
    routes: list[RouteResult]
    comparison: list[dict]
    edge_cases_detected: list[str]
    task_feasibility: TaskFeasibility | None = None


# ---------------------------------------------------------------------------
# PUT /model/record-choice  (learn from user's selection)
# ---------------------------------------------------------------------------

class RecordChoiceRequest(BaseModel):
    user_id: str
    intent: str
    preference_used: float
    time_hour: float = 12.0
    chosen_route_name: str
    chosen_signal_score: float
    chosen_eta: float


class RecordChoiceResponse(BaseModel):
    recorded: bool
    user_id: str
    total_choices: int


# ---------------------------------------------------------------------------
# PUT /model/resolve-intent  (preview what preference an intent maps to)
# ---------------------------------------------------------------------------

class ResolveIntentRequest(BaseModel):
    user_id: str = "default"
    intent: str
    time_hour: float = 12.0


class ResolveIntentResponse(BaseModel):
    intent: str
    preference: float
    task_type: str
    task_duration_min: float
    description: str
    source: str
    total_choices: int = 0


# ---------------------------------------------------------------------------
# PUT /model/auto-route  (RL-powered automatic routing)
# ---------------------------------------------------------------------------

class AutoRouteRequest(BaseModel):
    user_id: str = "default"
    origin: Coordinate
    destination: Coordinate
    time_hour: float = Field(12.0, ge=0, lt=24)
    day_of_week: int = Field(2, ge=0, le=6, description="0=Monday, 6=Sunday")
    intent: str = Field("", description="Override intent; leave empty for RL auto-detect")
    routes: list[RouteInput]
    towers: list[TowerInput]
    telecom: str = "all"
    weather_factor: float = Field(1.0, ge=0, le=1)
    speed_kmh: float = Field(40.0, ge=0, le=200)


class RLInfo(BaseModel):
    pattern_key: str
    context: dict
    confidence: float
    exploration_needed: bool
    rl_selected_intent: str | None
    all_scores: dict


class AutoRouteResponse(BaseModel):
    user_id: str
    intent: str
    resolved_preference: float
    preference_source: str
    task_type: str
    task_duration_min: float
    intent_description: str
    recommended_route: str
    explanation: str
    routes: list[RouteResult]
    comparison: list[dict]
    edge_cases_detected: list[str]
    task_feasibility: TaskFeasibility | None = None
    rl_info: RLInfo


# ---------------------------------------------------------------------------
# PUT /model/record-trip  (RL learning from completed trip)
# ---------------------------------------------------------------------------

class RecordTripRequest(BaseModel):
    user_id: str
    origin: Coordinate
    destination: Coordinate
    time_hour: float = Field(12.0, ge=0, lt=24)
    day_of_week: int = Field(2, ge=0, le=6)
    chosen_intent: str
    recommended_intent: str = ""


class RecordTripResponse(BaseModel):
    recorded: bool
    user_id: str
    pattern_key: str
    trip_count: int
    context: dict


# ---------------------------------------------------------------------------
# PUT /model/user-patterns  (view learned RL patterns)
# ---------------------------------------------------------------------------

class UserPatternsRequest(BaseModel):
    user_id: str


class PatternInfo(BaseModel):
    pattern_key: str
    time_bucket: str
    day_type: str
    origin_zone: str
    dest_zone: str
    predicted_intent: str
    confidence: float
    total_observations: int
    intent_scores: dict


class UserPatternsResponse(BaseModel):
    user_id: str
    trip_count: int
    patterns: list[PatternInfo]
