from typing import Literal

from pydantic import BaseModel, Field


class CoordinateSchema(BaseModel):
    lat: float
    lng: float


class RouteSchema(BaseModel):
    name: str
    eta: int = Field(..., description="Estimated travel time in minutes")
    distance: float = Field(..., description="Distance in kilometers")
    signal_score: int = Field(..., ge=0, le=100)
    weighted_score: float
    zones: list[str]
    path: list[CoordinateSchema]


class RoutesListSchema(BaseModel):
    source: str
    destination: str
    preference: int = Field(..., ge=0, le=100)
    routes: list[RouteSchema]
    recommended_route: str


class HeatmapZoneSchema(BaseModel):
    name: str
    lat: float
    lng: float
    score: int = Field(..., ge=0, le=100)
    signal_strength: Literal["strong", "medium", "weak"]
    color: str


class HeatmapSchema(BaseModel):
    zones: list[HeatmapZoneSchema]


class PredictionSchema(BaseModel):
    zone: str
    horizon_minutes: int
    expected_signal_score: float
    message: str


class RerouteRequestSchema(BaseModel):
    source: str
    destination: str
    current_zone: str | None = None
    preference: int = Field(default=50, ge=0, le=100)
    telecom: Literal["all", "jio", "airtel", "vi"] = "all"


class RerouteResponseSchema(BaseModel):
    message: str
    selected_route: RouteSchema
    advisory: str
