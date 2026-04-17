"""Generate human-readable explanations for route recommendations."""


def explain_recommendation(
    routes: list[dict],
    recommended_idx: int,
    preference: float,
) -> str:
    """Produce a one/two-line explanation of why a route was recommended."""
    if not routes:
        return "No routes available to compare."

    rec = routes[recommended_idx]
    conn = rec.get("connectivity", {})
    avg_sig = conn.get("avg_connectivity", 0)
    drop_segs = conn.get("drop_segments", 0)
    eta = rec.get("eta", 0)
    name = rec.get("name", f"Route {recommended_idx + 1}")

    parts = []

    if preference >= 70:
        parts.append(f"'{name}' selected for best connectivity (avg {avg_sig:.0f}/100)")
        if drop_segs == 0:
            parts.append("with zero dead-zone segments")
        else:
            # Find worse alternative
            others = [r for i, r in enumerate(routes) if i != recommended_idx]
            if others:
                worst = max(others, key=lambda r: r.get("connectivity", {}).get("drop_segments", 0))
                worst_drops = worst.get("connectivity", {}).get("drop_segments", 0)
                if worst_drops > drop_segs:
                    parts.append(
                        f"avoiding {worst_drops - drop_segs} extra weak-signal segments "
                        f"compared to '{worst.get('name', 'alternative')}'"
                    )
    elif preference <= 30:
        parts.append(f"'{name}' selected as fastest route ({eta} min)")
        if avg_sig >= 60:
            parts.append(f"with acceptable connectivity ({avg_sig:.0f}/100)")
        else:
            parts.append(f"note: connectivity is limited ({avg_sig:.0f}/100)")
    else:
        parts.append(f"'{name}' balances travel time ({eta} min) and connectivity ({avg_sig:.0f}/100)")

    # Add bad-zone warning if present
    if drop_segs > 0:
        parts.append(f"({drop_segs} weak-signal segment{'s' if drop_segs > 1 else ''} detected)")

    # Continuity note
    cont = conn.get("continuity_score", 100)
    if cont < 60:
        parts.append("signal stability is low along this route")

    return " -- ".join(parts) + "."


def explain_bad_zones(bad_zones: list[dict]) -> list[str]:
    """Convert bad-zone dicts to user-friendly warning strings."""
    warnings = []
    for z in bad_zones:
        w = z.get("warning", "")
        if w:
            warnings.append(w)
    return warnings


def compare_routes_summary(routes: list[dict]) -> list[dict]:
    """Produce a compact comparison table for the frontend."""
    summary = []
    for r in routes:
        conn = r.get("connectivity", {})
        summary.append({
            "name": r.get("name", "?"),
            "eta_min": r.get("eta", 0),
            "distance_km": r.get("distance", 0),
            "signal_score": conn.get("avg_connectivity", 0),
            "drop_segments": conn.get("drop_segments", 0),
            "continuity": conn.get("continuity_score", 0),
            "weighted_score": r.get("weighted_score", 0),
            "rejected": r.get("rejected", False),
        })
    return summary
