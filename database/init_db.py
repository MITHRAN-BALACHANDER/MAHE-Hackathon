"""Initialize MongoDB indexes and seed default data.

Run from repo root:
    python -m database.init_db
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.base import MongoClient
from backend.db.repository.rl_repo import RLRepository
from backend.db.models.rl_profile import RLProfile
from backend.core.logging import logger


SEED_PROFILES = [
    RLProfile(user_id="demo_commuter", alpha=2.0, beta=3.0),
    RLProfile(user_id="demo_emergency", alpha=5.0, beta=1.0),
    RLProfile(user_id="demo_fleet", alpha=1.0, beta=1.0),
    RLProfile(user_id="demo_videocall", alpha=4.0, beta=1.0),
    RLProfile(user_id="demo_delivery", alpha=1.0, beta=4.0),
]


async def init() -> None:
    await MongoClient.connect()
    db = MongoClient.get_db()
    repo = RLRepository(db)

    for profile in SEED_PROFILES:
        await repo.upsert_profile(profile)
        logger.info(f"Seeded: {profile.user_id} (alpha={profile.alpha}, beta={profile.beta})")

    count = await db["rl_profiles"].count_documents({})
    logger.info(f"Database initialized with {count} RL profiles")

    await MongoClient.disconnect()


if __name__ == "__main__":
    asyncio.run(init())
