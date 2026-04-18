import math
from datetime import datetime, timezone


def encode_time(dt: datetime | None = None) -> float:
    """Encode a datetime as a cyclic hour value in [0, 24).

    Used as input feature for the ML signal model to capture
    time-of-day patterns in network congestion.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.hour + dt.minute / 60.0


def cyclic_hour(hour: float) -> tuple[float, float]:
    """Return (sin, cos) encoding for an hour value.

    Useful as ML features -- captures that 23:00 is close to 01:00.
    """
    rad = 2 * math.pi * hour / 24.0
    return (math.sin(rad), math.cos(rad))
