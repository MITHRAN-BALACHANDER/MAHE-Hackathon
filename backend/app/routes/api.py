from typing import Literal, cast

from fastapi import APIRouter, Query

from app.schemas.route import (
    HeatmapSchema,
    PredictionSchema,
    RerouteRequestSchema,
    RerouteResponseSchema,
    RoutesListSchema,
)
from app.services.data_loader import load_signal_zones
from app.services.prediction import predict_zone_signal
from app.services.scoring import build_scored_routes
from app.utils.constants import DEFAULT_DESTINATION, DEFAULT_SOURCE, SIGNAL_COLOR_BY_STRENGTH

router = APIRouter(tags=["routing"])
TelecomType = Literal["all", "jio", "airtel", "vi"]


def normalize_telecom(telecom: str) -> TelecomType:
    telecom_normalized = telecom.strip().lower()
    if telecom_normalized in {"all", "jio", "airtel", "vi"}:
        return cast(TelecomType, telecom_normalized)
    return "all"


@router.get("/routes", response_model=RoutesListSchema)
def get_routes(
    source: str = Query(default=DEFAULT_SOURCE),
    destination: str = Query(default=DEFAULT_DESTINATION),
    preference: int = Query(default=50, ge=0, le=100),
    telecom: str = Query(default="all"),
):
    telecom_mode = normalize_telecom(telecom)
    routes = build_scored_routes(preference=preference, telecom=telecom_mode)
    recommended_route = routes[0]["name"]

    return {
        "source": source,
        "destination": destination,
        "preference": preference,
        "recommended_route": recommended_route,
        "routes": routes,
    }


@router.get("/heatmap", response_model=HeatmapSchema)
def get_heatmap():
    zones = []
    for zone in load_signal_zones():
        zones.append(
            {
                "name": zone["name"],
                "lat": zone["lat"],
                "lng": zone["lng"],
                "score": zone["score"],
                "signal_strength": zone["signal_strength"],
                "color": SIGNAL_COLOR_BY_STRENGTH.get(zone["signal_strength"], "#facc15"),
            }
        )
    return {"zones": zones}


@router.get("/predict", response_model=PredictionSchema)
def predict_signal(zone: str = Query(default="Electronic City"), minutes: int = Query(default=15, ge=5, le=60)):
    return predict_zone_signal(zone_name=zone, horizon_minutes=minutes)


@router.post("/reroute", response_model=RerouteResponseSchema)
def reroute(request: RerouteRequestSchema):
    preference = request.preference
    if request.current_zone and request.current_zone.lower() == "electronic city":
        preference = max(preference, 80)

    routes = build_scored_routes(preference=preference, telecom=request.telecom)
    selected_route = routes[0]
    return {
        "message": "Rerouted to stronger network zone",
        "selected_route": selected_route,
        "advisory": "Switch to offline maps if entering low coverage area for over 10 mins.",
    }
