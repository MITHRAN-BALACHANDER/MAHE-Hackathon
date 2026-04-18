from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.db.session import get_database


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency: yields the active MongoDB database."""
    return get_database()
