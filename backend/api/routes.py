from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.logging import log_request, log_error
from backend.core.security import validate_user_id, validate_coordinate, validate_weight
from backend.dependencies.auth import get_route_service, get_rl_service
from backend.schemas.route_schema import RouteRequest, RouteResponse
from backend.schemas.rl_schema import RLUpdateRequest, RLUpdateResponse
from backend.services.route_service import RouteService
from backend.services.rl_service import RLService

router = APIRouter()


@router.post("/route", response_model=RouteResponse)
async def get_routes(
    request: RouteRequest,
    route_service: RouteService = Depends(get_route_service),
) -> RouteResponse:
    """Generate ranked routing options with cellular signal quality predictions."""
    log_request("POST", "/route", {
        "origin": f"{request.origin.lat},{request.origin.lon}",
        "dest": f"{request.destination.lat},{request.destination.lon}",
        "weight": request.weight,
    })

    # Validate inputs
    validate_coordinate(request.origin.lat, request.origin.lon)
    validate_coordinate(request.destination.lat, request.destination.lon)
    weight = validate_weight(request.weight)

    user_id: str | None = None
    if request.user_id:
        user_id = validate_user_id(request.user_id)

    try:
        routes = await route_service.get_ranked_routes(
            origin_lat=request.origin.lat,
            origin_lon=request.origin.lon,
            dest_lat=request.destination.lat,
            dest_lon=request.destination.lon,
            weight=weight,
            user_id=user_id,
        )
        return RouteResponse(routes=routes)
    except Exception as exc:
        log_error("Route generation failed", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate routes. Please try again.",
        )


@router.post("/rl/update", response_model=RLUpdateResponse)
async def update_rl_profile(
    request: RLUpdateRequest,
    rl_service: RLService = Depends(get_rl_service),
) -> RLUpdateResponse:
    """Record route outcome to update RL personalization."""
    log_request("POST", "/rl/update", {"user_id": request.user_id, "success": request.success})

    user_id = validate_user_id(request.user_id)

    try:
        profile = await rl_service.update(user_id, request.success)
        return RLUpdateResponse(
            user_id=profile.user_id,
            alpha=profile.alpha,
            beta=profile.beta,
            message="Profile updated successfully",
        )
    except Exception as exc:
        log_error("RL update failed", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update RL profile.",
        )

