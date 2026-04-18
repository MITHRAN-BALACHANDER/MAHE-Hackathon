from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from backend.core.config import settings
from backend.core.logging import logger


class MongoClient:
    """Async MongoDB client singleton using Motor."""

    _client: AsyncIOMotorClient | None = None
    _db: AsyncIOMotorDatabase | None = None

    @classmethod
    async def connect(cls) -> None:
        if cls._client is not None:
            return
        logger.info(f"Connecting to MongoDB at {settings.MONGO_URI}")
        cls._client = AsyncIOMotorClient(
            settings.MONGO_URI,
            maxPoolSize=20,
            minPoolSize=2,
            serverSelectionTimeoutMS=5000,
        )
        cls._db = cls._client[settings.DB_NAME]
        await cls._ensure_indexes()
        logger.info(f"Connected to database '{settings.DB_NAME}'")

    @classmethod
    async def _ensure_indexes(cls) -> None:
        db = cls.get_db()
        await db["rl_profiles"].create_index("user_id", unique=True)
        await db["users"].create_index("user_id", unique=True)

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls._db is None:
            raise RuntimeError("Database not connected. Call MongoClient.connect() first.")
        return cls._db

    @classmethod
    async def disconnect(cls) -> None:
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("Disconnected from MongoDB")
