"""Seed script: inserts default RL profiles for testing."""

import asyncio

from backend.db.base import MongoClient
from backend.db.models.rl_profile import RLProfile
from backend.db.repository.rl_repo import RLRepository
from backend.core.logging import logger


SEED_USERS = [
    RLProfile(user_id="test_user_1", alpha=1.0, beta=1.0),
    RLProfile(user_id="test_user_2", alpha=3.0, beta=1.0),  # prefers signal
    RLProfile(user_id="test_user_3", alpha=1.0, beta=3.0),  # prefers speed
]


async def seed() -> None:
    await MongoClient.connect()
    db = MongoClient.get_db()
    repo = RLRepository(db)

    for profile in SEED_USERS:
        await repo.upsert_profile(profile)
        logger.info(f"Seeded RL profile: {profile.user_id}")

    logger.info(f"Seeded {len(SEED_USERS)} profiles")
    await MongoClient.disconnect()


if __name__ == "__main__":
    asyncio.run(seed())
