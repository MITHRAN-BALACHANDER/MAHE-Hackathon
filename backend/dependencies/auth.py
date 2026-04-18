from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.db.repository.rl_repo import RLRepository
from backend.dependencies.db import get_db
from backend.routing.osrm_client import OSRMClient
from backend.services.rl_service import RLService
from backend.services.route_service import RouteService
from backend.services.signal_client import SignalClient


# Singleton instances (created once, reused across requests)
_signal_client: SignalClient | None = None
_osrm_client: OSRMClient | None = None


def get_signal_client() -> SignalClient:
    global _signal_client
    if _signal_client is None:
        _signal_client = SignalClient()
    return _signal_client


def get_osrm_client() -> OSRMClient:
    global _osrm_client
    if _osrm_client is None:
        _osrm_client = OSRMClient()
    return _osrm_client


def get_rl_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> RLService:
    repo = RLRepository(db)
    return RLService(repo)


def get_route_service(
    osrm: OSRMClient = Depends(get_osrm_client),
    signal_client: SignalClient = Depends(get_signal_client),
    rl_service: RLService = Depends(get_rl_service),
) -> RouteService:
    return RouteService(osrm=osrm, signal_client=signal_client, rl_service=rl_service)
