from fastapi import APIRouter, Depends, HTTPException
from typing import List
from backend.schemas.route_schema import RouteRequest, RouteResponse
from backend.services.route_service import generate_optimized_routes

router = APIRouter()

@router.post("/routes", response_model=List[RouteResponse])
async def get_routes(request: RouteRequest):
    """
    Generate multple routing options including expected cellular signal quality.
    Calls OSRM to get base paths, then passes to ML model for signal prediction and scoring.
    """
    try:
        routes = await generate_optimized_routes(request)
        return routes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
