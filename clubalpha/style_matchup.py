"""Research-only style matchup signals for the Clubalpha website.

The module turns Club Dynamics' descriptive axes into attacking routes and
opponent exposures.  It does not modify the locked 60/30/10 Fixture State
composite.  Every route remains a challenger until walk-forward validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


ARCHETYPE_LABELS = {
    "territorial_controller": "Territorial controller",
    "developing_possession": "Developing possession",
    "high_intensity_direct": "High-intensity direct",
    "direct_wide_set_piece": "Direct / wide / set-piece",
    "adaptive_hybrid": "Adaptive hybrid",
    "promoted_forming": "Promoted / forming",
}

CHANNELS = [
    {
        "key": "box_pressure",
        "label": "Box pressure",
        "evidence_tier": "measured",
        "exposure_type": "defensive_exposure",
        "xi_execution": "chance creation plus scoring threat versus defensive prevention",
    },
    {
        "key": "set_pieces",
        "label": "Set pieces",
        "evidence_tier": "measured",
        "exposure_type": "defensive_exposure",
        "xi_execution": "scoring threat versus defensive prevention",
    },
    {
        "key": "wide_delivery",
        "label": "Wide delivery",
        "evidence_tier": "partial",
        "exposure_type": "defensive_exposure",
        "xi_execution": "chance creation versus defensive prevention",
    },
    {
        "key": "high_press",
        "label": "High press",
        "evidence_tier": "hypothesis",
        "exposure_type": "style_invitation",
        "xi_execution": "defensive prevention versus opponent chance creation",
    },
    {
        "key": "direct_transition",
        "label": "Direct transition",
        "evidence_tier": "hypothesis",
        "exposure_type": "style_invitation",
        "xi_execution": "scoring threat versus defensive prevention",
    },
]

MATCHUP_DECISION_BOUNDARIES = {
    "strong_route": 0.25,
    "leans_favorable": 0.08,
    "likely_resisted": -0.12,
}


def _value(section: dict[str, Any], key: str) -> float:
    value = (section.get(key) or {}).get("z")
    return float(value) if value is not None else 0.0


def _optional_value(section: dict[str, Any], key: str) -> float | None:
    value = (section.get(key) or {}).get("z")
    return float(value) if value is not None else None


def route_and_exposure(profile: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    """Create transparent route and exposure signals from one club profile."""

    style = profile["style"]["axes"]
    strength = profile["strengths_weaknesses"]["axes"]
    routes = {
        "box_pressure": (
            0.35 * _value(style, "territory")
            + 0.35 * _value(strength, "box_access")
            + 0.30 * _value(strength, "chance_creation")
        ),
        "set_pieces": (
            0.80 * _value(strength, "set_piece_attack")
            + 0.20 * max(0.0, _value(style, "set_piece_reliance"))
        ),
        "wide_delivery": (
            0.45 * _value(style, "crossing")
            + 0.35 * _value(strength, "box_access")
            + 0.20 * _value(strength, "chance_creation")
        ),
        "high_press": _value(style, "high_pressing"),
        "direct_transition": (
            0.45 * _value(style, "directness")
            + 0.30 * _value(strength, "shot_quality")
            + 0.25 * _value(strength, "chance_creation")
        ),
    }
    exposures = {
        "box_pressure": -(
            0.35 * _value(strength, "chance_prevention")
            + 0.35 * _value(strength, "box_defense")
            + 0.30 * _value(strength, "shot_suppression")
        ),
        "set_pieces": -_value(strength, "set_piece_defense"),
        "wide_delivery": -(
            0.65 * _value(strength, "box_defense")
            + 0.35 * _value(strength, "chance_prevention")
        ),
        # These two are invitations created by style, not observed failures.
        "high_press": (
            0.55 * _value(style, "control")
            + 0.45 * -_value(style, "directness")
        ),
        "direct_transition": (
            0.55 * _value(style, "territory")
            + 0.45 * _value(style, "control")
        ),
    }
    return (
        {key: round(value, 3) for key, value in routes.items()},
        {key: round(value, 3) for key, value in exposures.items()},
    )


def classify_archetype(profile: dict[str, Any]) -> str:
    """Classify current style with deterministic, reviewable boundaries."""

    style = profile["style"]["axes"]
    control = _value(style, "control")
    territory = _value(style, "territory")
    directness = _value(style, "directness")
    crossing = _value(style, "crossing")
    set_piece = _value(style, "set_piece_reliance")
    pressing = _optional_value(style, "high_pressing")

    if control >= 0.25 and (territory >= 0.35 or (pressing or 0.0) >= 0.50):
        return "territorial_controller"
    if control >= 0.10 and directness <= -0.15 and pressing is not None and pressing > -1.0:
        return "developing_possession"
    if (pressing or 0.0) >= 0.50 and directness >= 0.05:
        return "high_intensity_direct"
    if directness >= 0.15 and (crossing >= 0.10 or set_piece >= 0.08):
        return "direct_wide_set_piece"
    if pressing is None:
        return "promoted_forming"
    return "adaptive_hybrid"


def _alpha_value(alpha: dict[str, Any], key: str) -> float | None:
    value = (alpha.get(key) or {}).get("z")
    return round(float(value), 3) if value is not None else None


def evaluate_style_matchup(
    attacker: dict[str, Any], defender: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate one directional style matchup without changing probabilities."""

    attack_xi = attacker.get("projected_xi") or {}
    defense_xi = defender.get("projected_xi") or {}

    def xi(key: str) -> float:
        value = attack_xi.get(key)
        return float(value) if value is not None else 0.0

    opponent_prevention = float(defense_xi.get("defensive_prevention") or 0.0)
    routes = []
    for channel in CHANNELS:
        key = channel["key"]
        route_expression = float((attacker.get("route_expression") or {}).get(key) or 0.0)
        exposure = float((defender.get("opponent_exposure") or {}).get(key) or 0.0)
        if key == "box_pressure":
            execution = (xi("chance_creation") + xi("scoring_threat")) / 2.0 - opponent_prevention
        elif key == "wide_delivery":
            execution = xi("chance_creation") - opponent_prevention
        elif key == "high_press":
            execution = xi("defensive_prevention") - float(
                defense_xi.get("chance_creation") or 0.0
            )
        else:
            execution = xi("scoring_threat") - opponent_prevention
        route_fit = (route_expression + exposure) / 2.0
        score = 0.70 * route_fit + 0.30 * execution
        verdict = (
            "strong_route"
            if score >= MATCHUP_DECISION_BOUNDARIES["strong_route"]
            else "leans_favorable"
            if score >= MATCHUP_DECISION_BOUNDARIES["leans_favorable"]
            else "likely_resisted"
            if score <= MATCHUP_DECISION_BOUNDARIES["likely_resisted"]
            else "no_clear_edge"
        )
        routes.append(
            {
                "key": key,
                "label": channel["label"],
                "evidence_tier": channel["evidence_tier"],
                "route_expression_z": round(route_expression, 3),
                "opponent_exposure_z": round(exposure, 3),
                "xi_execution_edge_z": round(execution, 3),
                "challenger_signal_z": round(score, 3),
                "verdict": verdict,
            }
        )
    routes.sort(key=lambda row: row["challenger_signal_z"], reverse=True)
    return {
        "attacker": attacker.get("team"),
        "defender": defender.get("team"),
        "best_route": routes[0],
        "routes": routes,
        "probability_modifier": None,
        "composite_weight": 0,
    }


def build_style_matchup_snapshot(
    profiles: Iterable[dict[str, Any]],
    alpha_clubs: Iterable[dict[str, Any]],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Join current PL club style with projected-XI execution quality."""

    alpha_by_team = {str(row["team"]): row for row in alpha_clubs}
    teams = []
    for profile in profiles:
        if not profile.get("premier_league_2026_27"):
            continue
        team = str(profile["team"])
        alpha_row = alpha_by_team.get(team)
        routes, exposures = route_and_exposure(profile)
        alpha = (alpha_row or {}).get("alpha") or {}
        archetype_key = classify_archetype(profile)
        pressing_available = _optional_value(profile["style"]["axes"], "high_pressing") is not None
        quality_flags = []
        if not pressing_available:
            quality_flags.append("pressing_evidence_missing")
        if alpha_row is None:
            quality_flags.append("projected_xi_alpha_missing")
        elif alpha_row.get("grade_provisional"):
            quality_flags.append("projected_xi_alpha_provisional")
        teams.append(
            {
                "team_id": int(profile["team_id"]),
                "team": team,
                "archetype_key": archetype_key,
                "archetype": ARCHETYPE_LABELS[archetype_key],
                "route_expression": routes,
                "opponent_exposure": exposures,
                "projected_xi": {
                    "attacking_unit": _alpha_value(alpha, "attacking_unit_alpha_ability"),
                    "scoring_threat": _alpha_value(alpha, "scoring_threat"),
                    "chance_creation": _alpha_value(alpha, "chance_creation"),
                    "defensive_prevention": _alpha_value(alpha, "defensive_prevention"),
                    "grade_confidence": (alpha_row or {}).get("grade_confidence"),
                },
                "quality_flags": quality_flags,
            }
        )
    teams.sort(key=lambda row: row["team"])
    return {
        "snapshot_version": "clubalpha_style_matchup_v0",
        "as_of": as_of,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "research_challenger",
        "composite_weight": 0,
        "question": "By which route can one team make the next opponent vulnerable?",
        "method": {
            "matchup_read": "70% route fit plus 30% projected-XI execution edge",
            "route_fit": "mean of attacking route expression and opponent exposure",
            "decision_boundaries": MATCHUP_DECISION_BOUNDARIES,
            "safeguards": [
                "No signal modifies the locked 60/30/10 composite.",
                "High-press and direct-transition exposures are style invitations, not observed defensive failures.",
                "Wide delivery is partial until aerial and cross-defending player evidence is joined.",
                "Every route must pass chronological walk-forward validation before receiving model weight.",
            ],
        },
        "channels": CHANNELS,
        "teams": teams,
    }
