"""Translate calibrated football intelligence into selective shadow calls.

The policy is deliberately downstream. It cannot alter Player Alpha, Club
Form, the 60/30/10 foundation, contextual xG, or a frozen prediction. Its only
job is to decide whether the available evidence is strong enough to promote a
probability leader from a research lean to a shadow call.
"""

from __future__ import annotations

from typing import Any


POLICY_VERSION = "clubalpha_decision_policy_v1"
OUTCOMES = ("home_win", "draw", "away_win")


def validate_policy(config: dict[str, Any]) -> None:
    if config.get("version") != POLICY_VERSION:
        raise ValueError("decision-policy version is not supported")
    side = config["side"]
    if not 0.0 <= float(side["aligned_probability_minimum"]) < float(
        side["strong_probability_minimum"]
    ) <= 1.0:
        raise ValueError("side probability thresholds are invalid")
    if float(side["aligned_probability_maximum"]) != float(
        side["strong_probability_minimum"]
    ):
        raise ValueError("aligned and strong side tiers must meet exactly")
    totals = config["totals"]
    if float(totals["under_2_5_maximum_over_probability"]) >= float(
        totals["over_2_5_minimum"]
    ):
        raise ValueError("totals pass band must be positive")
    boundaries = config.get("locked_boundaries") or {}
    if any(value is not False for value in boundaries.values()):
        raise ValueError("decision policy weakens a locked boundary")


def _leader(probabilities: dict[str, Any]) -> tuple[str, float, float]:
    ordered = sorted(
        ((key, float(probabilities[key])) for key in OUTCOMES),
        key=lambda row: row[1],
        reverse=True,
    )
    return ordered[0][0], ordered[0][1], ordered[0][1] - ordered[1][1]


def _lineup_reliability(contextual: dict[str, Any]) -> float:
    directions = contextual["directional_context"]
    return min(
        float(directions["home_attack"]["projected_xi_reliability"]),
        float(directions["away_attack"]["projected_xi_reliability"]),
    )


def _foundation_support(
    baseline: dict[str, Any], leader: str, required: list[str]
) -> dict[str, bool]:
    if leader == "draw":
        return {key: False for key in required}
    selected_key = "home" if leader == "home_win" else "away"
    opponent_key = "away" if selected_key == "home" else "home"
    selected = baseline["fixture_intelligence"][selected_key][
        "normalized_components_z"
    ]
    opponent = baseline["fixture_intelligence"][opponent_key][
        "normalized_components_z"
    ]
    return {
        key: float(selected[key]) > float(opponent[key]) for key in required
    }


def evaluate_side(
    baseline: dict[str, Any],
    contextual: dict[str, Any],
    calibrated: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Return a selective 1X2 call with an auditable refusal reason."""

    validate_policy(config)
    side = config["side"]
    probabilities = calibrated["probabilities"]
    leader, probability, gap = _leader(probabilities)
    base_leader, _, _ = _leader(baseline["probabilities"])
    contextual_leader, _, _ = _leader(
        contextual["contextual"]["probabilities"]
    )
    context_verdict = contextual["context_read"]["verdict"]
    lineup_reliability = _lineup_reliability(contextual)
    required = list(side["required_foundation_components"])
    foundation = _foundation_support(baseline, leader, required)
    foundation_aligned = all(foundation.values())
    leader_aligned = leader == base_leader == contextual_leader
    draw_zone = bool(calibrated["calibration_read"]["draw_zone"])

    call = "pass"
    tier = "pass"
    reason = "insufficient_probability_or_separation"
    if leader == "draw":
        reason = "draw_is_review_only"
    elif draw_zone:
        reason = "calibrated_draw_zone"
    elif not leader_aligned:
        reason = "base_context_calibration_disagree"
    elif not foundation_aligned:
        reason = "club_form_and_player_alpha_do_not_both_support_side"
    elif context_verdict in set(side["blocked_context_verdicts"]):
        reason = "context_marks_baseline_fragile"
    elif (
        probability >= float(side["strong_probability_minimum"])
        and gap >= float(side["strong_gap_minimum"])
        and lineup_reliability
        >= float(side["strong_lineup_reliability_minimum"])
    ):
        call = leader
        tier = "strong"
        reason = "strong_probability_with_foundation_alignment"
    elif (
        float(side["aligned_probability_minimum"])
        <= probability
        < float(side["aligned_probability_maximum"])
        and gap >= float(side["aligned_gap_minimum"])
        and lineup_reliability
        >= float(side["aligned_lineup_reliability_minimum"])
        and context_verdict in set(side["aligned_context_verdicts"])
    ):
        call = leader
        tier = "aligned"
        reason = "medium_probability_with_full_evidence_alignment"
    elif probability < float(side["aligned_probability_minimum"]):
        reason = "leader_below_45_percent"
    elif lineup_reliability < float(
        side["aligned_lineup_reliability_minimum"]
    ):
        reason = "projected_xi_reliability_below_gate"
    elif context_verdict not in set(side["aligned_context_verdicts"]):
        reason = "context_does_not_reinforce_medium_probability_side"

    return {
        "market": "one_x_two",
        "leader": leader,
        "leader_probability": round(probability, 6),
        "leader_gap": round(gap, 6),
        "call": call,
        "tier": tier,
        "reason": reason,
        "evidence": {
            "base_leader": base_leader,
            "contextual_leader": contextual_leader,
            "calibrated_leader": leader,
            "leaders_aligned": leader_aligned,
            "foundation_support": foundation,
            "foundation_aligned": foundation_aligned,
            "context_verdict": context_verdict,
            "lineup_reliability": round(lineup_reliability, 6),
            "draw_zone": draw_zone,
        },
        "decision_boundaries": {
            "player_alpha_changed": False,
            "base_60_30_10_changed": False,
            "capital_deployment_ready": False,
        },
    }


def evaluate_total(
    calibrated: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Apply the explicit O/U 2.5 pass band to calibrated probabilities."""

    validate_policy(config)
    over = float(calibrated["probabilities"]["over"]["2.5"])
    totals = config["totals"]
    if over >= float(totals["over_2_5_minimum"]):
        call = "over_2_5"
        probability = over
        reason = "over_probability_clears_gate"
    elif over <= float(totals["under_2_5_maximum_over_probability"]):
        call = "under_2_5"
        probability = 1.0 - over
        reason = "under_probability_clears_gate"
    else:
        call = "pass"
        probability = max(over, 1.0 - over)
        reason = "inside_totals_pass_band"
    return {
        "market": "over_under_2_5",
        "over_probability": round(over, 6),
        "call": call,
        "call_probability": round(probability, 6),
        "reason": reason,
        "decision_boundaries": {
            "goal_environment_calibration_applied": bool(
                calibrated["calibration_read"].get(
                    "goal_environment_log_correction"
                )
            ),
            "capital_deployment_ready": False,
        },
    }


def price_eligible(call: str, probability: float, best_ask: float | None, config: dict[str, Any]) -> bool:
    validate_policy(config)
    if call == "pass" or best_ask is None:
        return False
    return probability - float(best_ask) >= float(config["price"]["minimum_edge"])


def refresh_gate(
    prematch_load: dict[str, Any],
    fixture_teams: set[str],
    *,
    stage: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Prevent a provisional pre-midweek packet from masquerading as final."""

    validate_policy(config)
    if stage not in {"provisional", "final"}:
        raise ValueError("decision stage must be provisional or final")
    pending = sorted(
        row["team"]
        for row in prematch_load.get("teams") or []
        if row.get("team") in fixture_teams
        and row.get("pending_preleague_fixture") is not None
    )
    required = bool(config["refresh"]["final_post_midweek_refresh_required"])
    if stage == "final" and required and pending:
        raise ValueError(
            "final matchweek freeze blocked by pending preleague fixtures: "
            + ", ".join(pending)
        )
    return {
        "stage": stage,
        "pending_preleague_teams": pending,
        "final_refresh_required": required,
        "final_refresh_complete": stage == "final" and not pending,
        "final_call_eligible": stage == "final" and not pending,
    }
