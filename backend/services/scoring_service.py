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
) -> float:
    """Weighted combination of signal quality and travel time.

    weight=1 -> pure signal preference
    weight=0 -> pure speed preference
    """
    # Normalize signal_score from 0-100 to 0-1 for fair weighting
    sig_norm = signal_score / 100.0
    return weight * sig_norm + (1.0 - weight) * eta_score
