from typing import Literal

from app.services.data_loader import load_routes_seed

TelecomType = Literal["all", "jio", "airtel", "vi"]

TELECOM_SIGNAL_BOOST = {
    "all": 1.0,
    "jio": 1.02,
    "airtel": 1.0,
    "vi": 0.96,
}


def compute_weights(preference: int) -> tuple[float, float]:
    signal_weight = max(0.0, min(1.0, preference / 100.0))
    time_weight = 1.0 - signal_weight
    return signal_weight, time_weight


def weighted_route_score(eta: int, signal_score: float, preference: int) -> float:
    signal_weight, time_weight = compute_weights(preference)
    return (signal_weight * signal_score) - (time_weight * eta)


def build_scored_routes(preference: int, telecom: TelecomType = "all") -> list[dict]:
    boost = TELECOM_SIGNAL_BOOST.get(telecom, 1.0)
    routes = []

    for route in load_routes_seed():
        adjusted_signal = min(100, round(route["signal_score"] * boost))
        weighted_score = weighted_route_score(
            eta=route["eta"],
            signal_score=adjusted_signal,
            preference=preference,
        )
        routes.append(
            {
                **route,
                "signal_score": adjusted_signal,
                "weighted_score": round(weighted_score, 2),
            }
        )

    routes.sort(key=lambda route: route["weighted_score"], reverse=True)
    return routes
