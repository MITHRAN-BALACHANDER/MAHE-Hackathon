from datetime import datetime, timezone
from pydantic import BaseModel, Field


class User(BaseModel):
    """User record in MongoDB."""

    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
