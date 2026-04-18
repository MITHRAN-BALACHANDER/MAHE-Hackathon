from pydantic import BaseModel, Field


class RLProfileResponse(BaseModel):
    user_id: str
    alpha: float
    beta: float


class RLUpdateRequest(BaseModel):
    user_id: str = Field(..., max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    success: bool = Field(..., description="Whether the route outcome was successful")


class RLUpdateResponse(BaseModel):
    user_id: str
    alpha: float
    beta: float
    message: str
