"""Thompson Sampling RL service for personalized route scoring."""

import numpy as np

from backend.core.logging import logger
from backend.db.models.rl_profile import RLProfile
from backend.db.repository.rl_repo import RLRepository


class RLService:
    """Reinforcement learning via Thompson Sampling (Beta-Bernoulli bandit)."""

    def __init__(self, repo: RLRepository) -> None:
        self._repo = repo

    async def sample(self, user_id: str) -> float:
        """Sample from the user's Beta(alpha, beta) distribution.

        Returns a value in [0, 1] representing the user's latent
        preference for signal quality vs speed.
        """
        profile = await self._repo.get_or_create(user_id)
        sampled = float(np.random.beta(profile.alpha, profile.beta))
        logger.info(
            f"RL sample user={user_id} alpha={profile.alpha:.2f} "
            f"beta={profile.beta:.2f} -> {sampled:.4f}"
        )
        return sampled

    async def update(self, user_id: str, success: bool) -> RLProfile:
        """Update the user's RL profile based on route outcome.

        success=True  -> user was happy with signal-heavy route -> alpha++
        success=False -> user preferred faster route -> beta++
        """
        profile = await self._repo.get_or_create(user_id)
        if success:
            profile.alpha += 1.0
        else:
            profile.beta += 1.0
        await self._repo.upsert_profile(profile)
        logger.info(
            f"RL update user={user_id} success={success} "
            f"alpha={profile.alpha:.2f} beta={profile.beta:.2f}"
        )
        return profile

    async def get_profile(self, user_id: str) -> RLProfile:
        return await self._repo.get_or_create(user_id)
