from pydantic import BaseModel, Field
from typing import List, Optional

class Coordinates(BaseModel):
    lat: float
    lng: float

class RouteRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates
    preference: str = Field(default="balanced", description="Either 'fastest', 'best_signal', or 'balanced'")
    time_of_day: Optional[str] = None # For temporal ML predictions

class SignalSegment(BaseModel):
    start_point: Coordinates
    end_point: Coordinates
    expected_signal_dbm: float
    network_type: str = "4G"

class RouteResponse(BaseModel):
    route_id: str
    geometry: str # Encoded polyline
    distance_meters: float
    duration_seconds: int
    signal_score: float
    segments: List[SignalSegment]
