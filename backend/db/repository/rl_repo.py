from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.db.models.rl_profile import RLProfile


class RLRepository:
    """Repository for rl_profiles collection."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["rl_profiles"]

    async def get_profile(self, user_id: str) -> RLProfile | None:
        doc = await self._collection.find_one({"user_id": user_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return RLProfile(**doc)

    async def upsert_profile(self, profile: RLProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc)
        await self._collection.update_one(
            {"user_id": profile.user_id},
            {"$set": profile.model_dump()},
            upsert=True,
        )

    async def get_or_create(self, user_id: str) -> RLProfile:
        profile = await self.get_profile(user_id)
        if profile is None:
            profile = RLProfile(user_id=user_id)
            await self.upsert_profile(profile)
        return profile
