from datetime import datetime, timezone
from pydantic import BaseModel, Field


class RLProfile(BaseModel):
    """Reinforcement learning profile stored in MongoDB."""

    user_id: str
    alpha: float = Field(default=1.0, ge=0.0)
    beta: float = Field(default=1.0, ge=0.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
