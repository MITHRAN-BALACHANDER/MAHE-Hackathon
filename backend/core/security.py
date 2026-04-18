import re

from fastapi import HTTPException, status


_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def validate_user_id(user_id: str) -> str:
    """Validate and sanitize user_id. Raises 422 on invalid input."""
    if not user_id or not _USER_ID_PATTERN.match(user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user_id: must be 1-64 alphanumeric/underscore/hyphen characters.",
        )
    return user_id


def validate_coordinate(lat: float, lon: float) -> None:
    """Validate geographic coordinates."""
    if not (-90.0 <= lat <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Latitude {lat} out of range [-90, 90].",
        )
    if not (-180.0 <= lon <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Longitude {lon} out of range [-180, 180].",
        )


def validate_weight(weight: float) -> float:
    """Clamp weight to [0, 1]."""
    return max(0.0, min(1.0, weight))
