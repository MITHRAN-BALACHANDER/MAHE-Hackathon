from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.core.security import SECRET_KEY, ALGORITHM
from backend.db.models.user import User

from backend.db.repository.rl_repo import RLRepository
from backend.dependencies.db import get_db
from backend.routing.osrm_client import OSRMClient
from backend.services.rl_service import RLService
from backend.services.route_service import RouteService
from backend.services.signal_client import SignalClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user_doc = await db.users.find_one({"username": username})
    if user_doc is None:
        raise credentials_exception
    return User(**user_doc)

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
