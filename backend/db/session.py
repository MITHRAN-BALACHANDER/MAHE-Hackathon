from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.db.base import MongoClient


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database instance."""
    return MongoClient.get_db()
