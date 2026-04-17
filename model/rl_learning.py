"""Contextual Bandit with Thompson Sampling for user route preference learning.

Each trip creates a context from temporal and spatial features. The bandit
maintains Beta distributions for each (context, intent) pair and uses Thompson
Sampling to select the most likely user intent for a given context.

Pattern key: time_bucket | day_type | origin_zone | dest_zone

Scenario:
  Son drives 7:30 AM weekday, Jayanagar -> Koramangala: learns "meeting"
  Dad drives 10:00 AM weekday, Jayanagar -> Koramangala: learns "navigation"
  Same origin/destination, different time = different patterns = independent learning.
"""

import json
import numpy as np
from pathlib import Path

from model.config import DATA_DIR, ZONES
from model.utils import haversine
from model.smart_preference import INTENT_PROFILES

INTENTS = list(INTENT_PROFILES.keys())
RL_DATA_DIR = DATA_DIR / "rl_profiles"


# -----------------------------------------------------------------------
# Context encoding
# -----------------------------------------------------------------------

TIME_BUCKETS = {
    "early_morning":    (5, 7),
    "morning_commute":  (7, 9),
    "late_morning":     (9, 11),
    "midday":           (11, 14),
    "afternoon":        (14, 17),
    "evening_commute":  (17, 19),
    "evening":          (19, 22),
    "night":            (22, 29),   # wraps: 22-24 + 0-5
}


def time_to_bucket(hour: float) -> str:
    """Map hour of day (0-24) to a named time bucket."""
    for name, (start, end) in TIME_BUCKETS.items():
        if start <= hour < end:
            return name
    return "night"


def day_to_type(day_of_week: int) -> str:
    """0=Monday..6=Sunday -> 'weekday' | 'weekend'."""
    return "weekend" if day_of_week >= 5 else "weekday"


def coord_to_zone(lat: float, lng: float) -> str:
    """Map a coordinate to the nearest known Bangalore zone."""
    best_zone = "unknown"
    best_dist = float("inf")
    for name, info in ZONES.items():
        d = haversine(lat, lng, info["center"][0], info["center"][1])
        if d < best_dist:
            best_dist = d
            best_zone = name
    return best_zone


# -----------------------------------------------------------------------
# Contextual Bandit
# -----------------------------------------------------------------------

class ContextualBandit:
    """Thompson Sampling bandit for per-user route preference learning.

    Each user has a separate file-backed instance. The bandit learns which
    intent a user typically needs for a given (time, day, origin, dest).

    Attributes:
        MIN_OBS: minimum observations before auto-selecting an intent.
        MIN_CONFIDENCE: minimum Thompson sample value to auto-assign.
    """

    MIN_OBS = 3
    MIN_CONFIDENCE = 0.55

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.data_path = RL_DATA_DIR / f"{user_id}.json"
        self.distributions: dict[str, dict[str, list[float]]] = {}
        self.trip_count: int = 0
        self._load()

    # -- persistence -------------------------------------------------------

    def _load(self):
        if self.data_path.exists():
            with open(self.data_path) as f:
                data = json.load(f)
            self.distributions = data.get("distributions", {})
            self.trip_count = data.get("trip_count", 0)

    def _save(self):
        RL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w") as f:
            json.dump({
                "user_id": self.user_id,
                "trip_count": self.trip_count,
                "distributions": self.distributions,
            }, f, indent=2)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _make_key(tb: str, dt: str, oz: str, dz: str) -> str:
        return f"{tb}|{dt}|{oz}|{dz}"

    def _get_params(self, pk: str, intent: str) -> list[float]:
        """Get [alpha, beta] for a (pattern, intent) pair."""
        if pk not in self.distributions:
            self.distributions[pk] = {}
        if intent not in self.distributions[pk]:
            self.distributions[pk][intent] = [1.0, 1.0]  # Beta(1,1) = uniform
        return self.distributions[pk][intent]

    # -- core RL methods ---------------------------------------------------

    def select(
        self,
        time_hour: float,
        day_of_week: int,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Select best intent for the context using Thompson Sampling.

        Returns a dict with:
          intent:             str or None (None = not enough data)
          pattern_key:        str
          context:            dict with time_bucket, day_type, origin_zone, dest_zone
          confidence:         float 0-1
          exploration_needed: bool
          all_scores:         dict top-5 intent -> sampled score
        """
        tb = time_to_bucket(time_hour)
        dt = day_to_type(day_of_week)
        oz = coord_to_zone(origin_lat, origin_lng)
        dz = coord_to_zone(dest_lat, dest_lng)
        pk = self._make_key(tb, dt, oz, dz)

        context = {
            "time_bucket": tb,
            "day_type": dt,
            "origin_zone": oz,
            "dest_zone": dz,
        }

        # Not enough data yet
        if pk not in self.distributions:
            return self._no_data(pk, context)

        total_obs = sum(
            a + b - 2 for a, b in [self._get_params(pk, i) for i in INTENTS]
        )
        if total_obs < self.MIN_OBS:
            return self._no_data(pk, context, int(total_obs))

        # Thompson Sampling: sample from Beta(alpha, beta) for each intent
        samples = {}
        for intent in INTENTS:
            alpha, beta = self._get_params(pk, intent)
            samples[intent] = float(np.random.beta(alpha, beta))

        best = max(samples, key=samples.get)
        conf = samples[best]
        top_scores = {
            k: round(v, 3)
            for k, v in sorted(samples.items(), key=lambda x: -x[1])[:5]
        }

        if conf < self.MIN_CONFIDENCE:
            return {
                "intent": None,
                "pattern_key": pk,
                "context": context,
                "confidence": round(conf, 3),
                "exploration_needed": True,
                "all_scores": top_scores,
            }

        return {
            "intent": best,
            "pattern_key": pk,
            "context": context,
            "confidence": round(conf, 3),
            "exploration_needed": False,
            "all_scores": top_scores,
        }

    def update(
        self,
        time_hour: float,
        day_of_week: int,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        chosen_intent: str,
        recommended_intent: str | None = None,
    ) -> dict:
        """Update distributions after a completed trip.

        Rewards the chosen intent (alpha += 1). If the system recommended a
        different intent and the user overrode it, penalizes the recommendation
        (beta += 1).
        """
        tb = time_to_bucket(time_hour)
        dt = day_to_type(day_of_week)
        oz = coord_to_zone(origin_lat, origin_lng)
        dz = coord_to_zone(dest_lat, dest_lng)
        pk = self._make_key(tb, dt, oz, dz)

        # Positive reward for chosen intent
        params = self._get_params(pk, chosen_intent)
        params[0] += 1.0  # alpha += 1

        # Negative signal if recommendation was rejected
        if recommended_intent and recommended_intent != chosen_intent:
            rec = self._get_params(pk, recommended_intent)
            rec[1] += 1.0  # beta += 1

        self.trip_count += 1
        self._save()

        return {
            "pattern_key": pk,
            "trip_count": self.trip_count,
            "updated_intent": chosen_intent,
            "context": {
                "time_bucket": tb,
                "day_type": dt,
                "origin_zone": oz,
                "dest_zone": dz,
            },
        }

    def get_patterns(self) -> list[dict]:
        """Return all learned patterns sorted by confidence."""
        patterns = []
        for pk, intents in self.distributions.items():
            parts = pk.split("|")

            # Expected value = alpha / (alpha + beta) for each intent
            scores = {}
            for name, (a, b) in intents.items():
                scores[name] = a / (a + b)

            best = max(scores, key=scores.get)
            total = int(sum(a + b - 2 for a, b in intents.values()))

            patterns.append({
                "pattern_key": pk,
                "time_bucket": parts[0] if len(parts) > 0 else "",
                "day_type": parts[1] if len(parts) > 1 else "",
                "origin_zone": parts[2] if len(parts) > 2 else "",
                "dest_zone": parts[3] if len(parts) > 3 else "",
                "predicted_intent": best,
                "confidence": round(scores[best], 3),
                "total_observations": total,
                "intent_scores": {
                    k: round(v, 3)
                    for k, v in sorted(scores.items(), key=lambda x: -x[1])[:5]
                },
            })

        patterns.sort(key=lambda p: -p["confidence"])
        return patterns

    def reset(self):
        """Clear all learned patterns for this user."""
        self.distributions = {}
        self.trip_count = 0
        if self.data_path.exists():
            self.data_path.unlink()

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _no_data(pk, context, obs=0):
        return {
            "intent": None,
            "pattern_key": pk,
            "context": context,
            "confidence": 0.0,
            "exploration_needed": True,
            "all_scores": {},
            "observations": obs,
        }


# -----------------------------------------------------------------------
# Module-level cache
# -----------------------------------------------------------------------

_bandits: dict[str, ContextualBandit] = {}


def get_bandit(user_id: str) -> ContextualBandit:
    """Get or create a cached bandit instance for a user."""
    if user_id not in _bandits:
        _bandits[user_id] = ContextualBandit(user_id)
    return _bandits[user_id]
