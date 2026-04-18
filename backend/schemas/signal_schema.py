from pydantic import BaseModel, Field


class SignalPoint(BaseModel):
    lat: float
    lon: float
    time: float = Field(default=0.0, description="Unix timestamp or hour-of-day")


class SignalPredictionRequest(BaseModel):
    points: list[SignalPoint]


class SignalPrediction(BaseModel):
    signal_strength: float = Field(..., description="Predicted signal strength 0-100")
    drop_probability: float = Field(..., ge=0.0, le=1.0)


class SignalPredictionResponse(BaseModel):
    predictions: list[SignalPrediction]
