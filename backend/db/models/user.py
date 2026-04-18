from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User record in MongoDB."""

    user_id: str
    username: str
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

