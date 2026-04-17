"""Smart preference engine: auto-map user intent to preference + learn from history.

Two capabilities:
1. Intent mapping  -- "meeting" / "call" / "navigation" / "download" / "emergency"
                      -> auto-set preference value + task type
2. User profiling  -- track past choices, learn user's typical preference per context
                      (time of day, weekday/weekend, task type)
"""

import json
import time
from pathlib import Path
from collections import defaultdict

from model.config import DATA_DIR


# ---------------------------------------------------------------------------
# Intent -> preference mapping (rule-based, instant)
# ---------------------------------------------------------------------------

INTENT_PROFILES = {
    # intent_name: (preference, task_type, task_duration_min, description)
    "meeting": (85, "meeting", 30.0, "Video/audio meeting -- needs strong, continuous signal"),
    "call": (60, "call", 10.0, "Phone call -- needs moderate continuous signal"),
    "navigation": (10, "call", 0.0, "Just navigating -- speed priority, minimal network"),
    "fastest": (0, "call", 0.0, "Fastest route -- no network consideration"),
    "download": (70, "download", 5.0, "Large file download -- needs good average signal"),
    "streaming": (75, "download", 15.0, "Music/video streaming -- needs sustained good signal"),
    "emergency": (0, "call", 0.0, "Emergency -- fastest route, network irrelevant"),
    "work": (65, "call", 10.0, "General work -- emails, messages, occasional calls"),
    "idle": (30, "call", 0.0, "No active task -- slight speed preference"),
    "best_signal": (100, "meeting", 0.0, "Maximum network priority"),
}

# Keywords that map to intents (for fuzzy matching from frontend)
INTENT_KEYWORDS = {
    "meeting": ["meeting", "video call", "zoom", "teams", "conference", "webinar"],
    "call": ["call", "phone", "ring", "dial", "voice"],
    "navigation": ["navigate", "directions", "go to", "drive", "travel"],
    "fastest": ["fast", "fastest", "quick", "hurry", "rush", "urgent"],
    "download": ["download", "upload", "file", "update", "sync"],
    "streaming": ["stream", "music", "video", "youtube", "spotify", "podcast"],
    "emergency": ["emergency", "hospital", "accident", "sos", "help"],
    "work": ["work", "office", "email", "slack", "messages"],
    "idle": ["idle", "no task", "nothing", "free", "relax", "casual"],
    "best_signal": ["best signal", "max signal", "full signal", "strong network"],
}


def resolve_intent(intent: str) -> dict:
    """Map an intent string to preference, task_type, duration.

    Accepts exact intent names ("meeting") or fuzzy keywords ("I have a zoom call").
    Falls back to balanced preference if unrecognised.
    """
    intent_lower = intent.lower().strip()

    # Exact match
    if intent_lower in INTENT_PROFILES:
        pref, task, dur, desc = INTENT_PROFILES[intent_lower]
        return {
            "intent": intent_lower,
            "preference": pref,
            "task_type": task,
            "task_duration_min": dur,
            "description": desc,
            "source": "exact_match",
        }

    # Keyword search
    for intent_name, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in intent_lower:
                pref, task, dur, desc = INTENT_PROFILES[intent_name]
                return {
                    "intent": intent_name,
                    "preference": pref,
                    "task_type": task,
                    "task_duration_min": dur,
                    "description": desc,
                    "source": "keyword_match",
                    "matched_keyword": kw,
                }

    # Fallback: balanced
    return {
        "intent": "balanced",
        "preference": 50,
        "task_type": "call",
        "task_duration_min": 5.0,
        "description": "Balanced speed and signal",
        "source": "fallback",
    }


# ---------------------------------------------------------------------------
# User profile learning (file-backed, lightweight)
# ---------------------------------------------------------------------------

PROFILE_PATH = DATA_DIR / "user_profiles.json"


def _load_profiles() -> dict:
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {}


def _save_profiles(profiles: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profiles, f, indent=2)


def _time_bucket(hour: float) -> str:
    """Bucket hour into time-of-day category."""
    if 6 <= hour < 10:
        return "morning_commute"
    if 10 <= hour < 16:
        return "midday"
    if 16 <= hour < 20:
        return "evening_commute"
    return "night"


def record_choice(
    user_id: str,
    intent: str,
    preference_used: float,
    time_hour: float,
    chosen_route_name: str,
    chosen_signal_score: float,
    chosen_eta: float,
):
    """Record a user's routing choice for future learning."""
    profiles = _load_profiles()
    if user_id not in profiles:
        profiles[user_id] = {"choices": [], "learned_preferences": {}}

    profiles[user_id]["choices"].append({
        "timestamp": time.time(),
        "intent": intent,
        "preference": preference_used,
        "time_bucket": _time_bucket(time_hour),
        "time_hour": time_hour,
        "route": chosen_route_name,
        "signal": chosen_signal_score,
        "eta": chosen_eta,
    })

    # Keep last 100 choices per user
    profiles[user_id]["choices"] = profiles[user_id]["choices"][-100:]

    # Re-learn preferences from history
    profiles[user_id]["learned_preferences"] = _learn_preferences(
        profiles[user_id]["choices"]
    )
    _save_profiles(profiles)


def _learn_preferences(choices: list[dict]) -> dict:
    """Compute average preference per (intent, time_bucket) from history."""
    groups = defaultdict(list)
    for c in choices:
        key = f"{c['intent']}_{c['time_bucket']}"
        groups[key].append(c["preference"])
        # Also learn per-intent regardless of time
        groups[c["intent"]].append(c["preference"])

    learned = {}
    for key, prefs in groups.items():
        if len(prefs) >= 3:  # need at least 3 data points
            learned[key] = round(sum(prefs) / len(prefs), 1)
    return learned


def get_smart_preference(
    user_id: str,
    intent: str,
    time_hour: float = 12.0,
) -> dict:
    """Get preference for a user, combining intent rules + learned history.

    Priority:
    1. User's learned preference for this (intent, time_bucket) if enough data
    2. User's learned preference for this intent (any time)
    3. Default intent mapping
    """
    # Start with rule-based intent resolution
    result = resolve_intent(intent)

    # Try to override with learned preference
    profiles = _load_profiles()
    if user_id in profiles:
        learned = profiles[user_id].get("learned_preferences", {})
        time_bucket = _time_bucket(time_hour)
        specific_key = f"{result['intent']}_{time_bucket}"

        if specific_key in learned:
            result["preference"] = learned[specific_key]
            result["source"] = "learned_specific"
            result["learned_from"] = specific_key
        elif result["intent"] in learned:
            result["preference"] = learned[result["intent"]]
            result["source"] = "learned_general"
            result["learned_from"] = result["intent"]

        result["total_choices"] = len(profiles[user_id].get("choices", []))

    return result
