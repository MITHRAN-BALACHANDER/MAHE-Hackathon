"""Scoring service: normalizes and combines ETA + signal into a final score."""

from backend.schemas.signal_schema import SignalPrediction


def compute_signal_score(predictions: list[SignalPrediction]) -> float:
    """Average signal strength across all sampled points (0-100)."""
    if not predictions:
        return 50.0
    return sum(p.signal_strength for p in predictions) / len(predictions)


def compute_drop_probability(predictions: list[SignalPrediction]) -> float:
    """Average drop probability across all sampled points (0-1)."""
    if not predictions:
        return 0.1
    return sum(p.drop_probability for p in predictions) / len(predictions)


def compute_signal_variance(predictions: list[SignalPrediction]) -> float:
    """Variance of signal strength (lower = more stable connection)."""
    if len(predictions) < 2:
        return 0.0
    values = [p.signal_strength for p in predictions]
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def compute_continuity_score(predictions: list[SignalPrediction]) -> float:
    """Continuity score: 100 - std * 2.5, clamped to [0, 100]."""
    if not predictions:
        return 50.0
    variance = compute_signal_variance(predictions)
    std = variance ** 0.5
    return max(0.0, min(100.0, 100.0 - std * 2.5))


def compute_longest_stable_window(
    predictions: list[SignalPrediction], threshold: float = 50.0
) -> int:
    """Longest consecutive stretch of segments with signal >= threshold."""
    longest = 0
    current = 0
    for p in predictions:
        if p.signal_strength >= threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def compute_stability_score(predictions: list[SignalPrediction]) -> float:
    """Combined stability: 50% continuity + 50% longest-stable-fraction."""
    continuity = compute_continuity_score(predictions)
    n = max(len(predictions), 1)
    stable_fraction = compute_longest_stable_window(predictions) / n
    return 0.5 * continuity + 0.5 * (stable_fraction * 100.0)


def normalize_eta(eta_seconds: float, all_etas: list[float]) -> float:
    """Normalize ETA to [0, 1] where 1 = fastest, 0 = slowest.

    Uses min-max normalization across all candidate routes.
    """
    if len(all_etas) <= 1:
        return 1.0
    min_eta = min(all_etas)
    max_eta = max(all_etas)
    if max_eta == min_eta:
        return 1.0
    # Invert so shorter ETA = higher score
    return 1.0 - (eta_seconds - min_eta) / (max_eta - min_eta)


def compute_final_score(
    weight: float,
    signal_score: float,
    eta_score: float,
    stability_score: float = 50.0,
) -> float:
    """Weighted combination of signal quality, travel time, and stability.

    weight=1 -> pure signal preference
    weight=0 -> pure speed preference
    Stability bonus: up to +0.1 scaled by weight (signal-focused users care more).
    """
    sig_norm = signal_score / 100.0
    stability_bonus = (stability_score / 100.0) * 0.1 * weight
    return weight * sig_norm + (1.0 - weight) * eta_score + stability_bonus
