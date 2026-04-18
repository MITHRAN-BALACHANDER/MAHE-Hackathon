from pydantic import BaseModel, Field
from typing import Optional


class Coordinates(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class RouteRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates
    weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Signal vs speed preference: 1 = pure signal, 0 = pure speed")
    user_id: Optional[str] = Field(default=None, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")


class RouteGeometryPoint(BaseModel):
    lat: float
    lon: float


class RouteResult(BaseModel):
    eta: float = Field(..., description="Estimated travel time in minutes")
    signal_score: float = Field(..., ge=0.0, le=100.0)
    drop_prob: float = Field(..., ge=0.0, le=1.0)
    final_score: float
    geometry: list[RouteGeometryPoint]


class RouteResponse(BaseModel):
    routes: list[RouteResult]

