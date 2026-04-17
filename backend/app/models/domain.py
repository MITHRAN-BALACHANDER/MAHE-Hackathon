from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Coordinates:
    lat: float
    lng: float


@dataclass(frozen=True)
class SignalZone:
    name: str
    signal_strength: str
    score: int
    lat: float
    lng: float


@dataclass(frozen=True)
class RouteTemplate:
    name: str
    eta: int
    distance: float
    signal_score: int
    path: List[Coordinates]
    zones: List[str]
