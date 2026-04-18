from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import timedelta

from backend.core.logging import log_request, log_error
from backend.core.security import validate_user_id, validate_coordinate, validate_weight, get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.dependencies.auth import get_route_service, get_rl_service, get_current_user
from backend.dependencies.db import get_db
from backend.db.models.user import UserCreate, Token, User
from backend.schemas.route_schema import RouteRequest, RouteResponse
from backend.schemas.rl_schema import RLUpdateRequest, RLUpdateResponse
from backend.services.route_service import RouteService
from backend.services.rl_service import RLService

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    if await db.users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already registered")
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    user_doc = User(
        user_id=user_id,
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    await db.users.insert_one(user_doc.model_dump())
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncIOMotorDatabase = Depends(get_db)):
    user_doc = await db.users.find_one({"username": form_data.username})
    if not user_doc or not verify_password(form_data.password, user_doc["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_doc["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

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

