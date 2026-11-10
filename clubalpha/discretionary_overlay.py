"""Bounded, auditable human judgment downstream of systematic forecasts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


VERSION = "clubalpha_discretionary_overlay_v1"


def validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != VERSION:
        raise ValueError("discretionary-overlay version is not supported")
    category_total = sum(
        float(row["maximum_adjustment"])
        for row in config["categories"].values()
    )
    if category_total > float(config["maximum_total_adjustment"]) + 1e-12:
        raise ValueError("category adjustments exceed the overlay ceiling")
    if any(value is not False for value in config["locked_boundaries"].values()):
        raise ValueError("discretionary overlay weakens a locked boundary")


def _side_reviewability(
    decision: dict[str, Any], config: dict[str, Any]
) -> tuple[bool, list[str]]:
    side = decision["side_decision"]
    if side["call"] != "pass":
        return True, []
    evidence = side["evidence"]
    near = config["near_miss"]
    blockers = []
    if side["leader"] == "draw":
        blockers.append("draw_review_only")
    probability_gap = float(near["side_probability_minimum"]) - float(
        side["leader_probability"]
    )
    if probability_gap > float(near["side_probability_distance"]) + 1e-12:
        blockers.append("probability_outside_near_miss_zone")
    if not bool(evidence["leaders_aligned"]):
        blockers.append("systematic_layers_disagree")
    if not bool(evidence["foundation_aligned"]):
        blockers.append("club_form_and_player_alpha_disagree")
    if evidence["context_verdict"] not in set(near["allowed_context_verdicts"]):
        blockers.append("context_not_supportive")
    if float(evidence["lineup_reliability"]) < float(
        near["lineup_reliability_minimum"]
    ):
        blockers.append("lineup_reliability_below_discretionary_gate")
    return not blockers, blockers


def _total_reviewability(
    decision: dict[str, Any], config: dict[str, Any]
) -> tuple[bool, list[str], str, float]:
    total = decision["total_decision"]
    over = float(total["over_probability"])
    outcome = "over_2_5" if over >= 0.5 else "under_2_5"
    probability = max(over, 1.0 - over)
    if total["call"] != "pass":
        return True, [], str(total["call"]), float(total["call_probability"])
    threshold = float(config["near_miss"]["total_probability_minimum"])
    distance = threshold - probability
    blockers = []
    if distance > float(config["near_miss"]["total_probability_distance"]) + 1e-12:
        blockers.append("probability_outside_near_miss_zone")
    return not blockers, blockers, outcome, probability


def _blank_review(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "unreviewed",
        "analyst": None,
        "reviewed_at_utc": None,
        "market_price_used_as_rationale": False,
        "thesis": None,
        "signals": {
            key: {
                "direction": 0,
                "confidence": 0.0,
                "note": None,
                "already_modeled": False,
            }
            for key in config["categories"]
        },
    }


def build_review_queue(
    decisions: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    validate_config(config)
    fixtures = []
    for decision in decisions["fixtures"]:
        side_reviewable, side_blockers = _side_reviewability(decision, config)
        total_reviewable, total_blockers, total_outcome, total_probability = (
            _total_reviewability(decision, config)
        )
        fixtures.append(
            {
                "match_id": decision["match_id"],
                "fixture": decision["fixture"],
                "kickoff_utc": decision["kickoff_utc"],
                "selections": [
                    {
                        "market": "one_x_two",
                        "outcome": decision["side_decision"]["leader"],
                        "systematic_probability": decision["side_decision"][
                            "leader_probability"
                        ],
                        "systematic_call": decision["side_decision"]["call"],
                        "systematic_reason": decision["side_decision"]["reason"],
                        "structurally_reviewable": side_reviewable,
                        "review_blockers": side_blockers,
                        "review": _blank_review(config),
                    },
                    {
                        "market": "over_under_2_5",
                        "outcome": total_outcome,
                        "systematic_probability": round(total_probability, 6),
                        "systematic_call": decision["total_decision"]["call"],
                        "systematic_reason": decision["total_decision"]["reason"],
                        "structurally_reviewable": total_reviewable,
                        "review_blockers": total_blockers,
                        "review": _blank_review(config),
                    },
                ],
            }
        )
    return {
        "version": VERSION,
        "status": "discretionary_review_queue",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": decisions["as_of"],
        "round": decisions["round"],
        "systematic_stage": decisions["refresh_gate"]["stage"],
        "final_refresh_complete": decisions["refresh_gate"][
            "final_refresh_complete"
        ],
        "instructions": {
            "review_football_before_reopening_market_prices": True,
            "record_only_residual_evidence_not_already_in_the_model": True,
            "nonzero_signals_require_specific_prematch_notes": True,
            "maximum_probability_adjustment": config["maximum_total_adjustment"],
        },
        "fixtures": fixtures,
        "decision_boundaries": deepcopy(config["locked_boundaries"]),
    }


def score_selection(
    selection: dict[str, Any],
    *,
    final_refresh_complete: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Score one completed review without mutating its systematic fields."""

    validate_config(config)
    review = selection["review"]
    if review["status"] not in {"unreviewed", "draft", "approved", "rejected"}:
        raise ValueError("unsupported discretionary review status")
    if set(review["signals"]) != set(config["categories"]):
        raise ValueError("discretionary signal categories do not reconcile")
    contributions = {}
    for key, category in config["categories"].items():
        signal = review["signals"][key]
        direction = int(signal["direction"])
        confidence = float(signal["confidence"])
        if direction not in {-1, 0, 1} or not 0.0 <= confidence <= 1.0:
            raise ValueError(f"invalid discretionary signal: {key}")
        if direction and not str(signal.get("note") or "").strip():
            raise ValueError(f"nonzero discretionary signal requires note: {key}")
        if direction and bool(signal.get("already_modeled")):
            raise ValueError(f"modeled evidence cannot be counted twice: {key}")
        contributions[key] = round(
            direction
            * confidence
            * float(category["maximum_adjustment"]),
            6,
        )
    raw_adjustment = sum(contributions.values())
    ceiling = float(config["maximum_total_adjustment"])
    adjustment = max(-ceiling, min(ceiling, raw_adjustment))
    base = float(selection["systematic_probability"])
    adjusted = max(0.0, min(1.0, base + adjustment))
    approved = review["status"] == "approved"
    activation = {
        "structurally_reviewable": bool(selection["structurally_reviewable"]),
        "approved": approved,
        "final_refresh_complete": bool(final_refresh_complete),
        "rationale_is_price_independent": not bool(
            review["market_price_used_as_rationale"]
        ),
        "analyst_recorded": bool(str(review.get("analyst") or "").strip()),
        "timestamp_recorded": bool(
            str(review.get("reviewed_at_utc") or "").strip()
        ),
    }
    active = all(activation.values())
    threshold = float(
        config["near_miss"][
            "side_probability_minimum"
            if selection["market"] == "one_x_two"
            else "total_probability_minimum"
        ]
    )
    overlay_call = str(selection["systematic_call"])
    if active:
        overlay_call = str(selection["outcome"]) if adjusted >= threshold else "pass"
    if not active:
        call_origin = "systematic"
    elif overlay_call == "pass" and selection["systematic_call"] != "pass":
        call_origin = "discretionary_veto"
    elif selection["systematic_call"] == "pass" and overlay_call != "pass":
        call_origin = "discretionary_near_miss"
    else:
        call_origin = "discretionary_reviewed_systematic_call"
    return {
        **selection,
        "systematic_probability": round(base, 6),
        "discretionary_contributions": contributions,
        "discretionary_adjustment": round(adjustment, 6),
        "adjusted_probability": round(adjusted, 6),
        "activation_gates": activation,
        "overlay_active": active,
        "effective_probability": round(adjusted if active else base, 6),
        "effective_call": overlay_call,
        "call_origin": call_origin,
        "decision_boundaries": {
            "systematic_probability_changed": False,
            "systematic_decision_changed": False,
            "hard_execution_gates_overridden": False,
            "real_capital_eligible": False,
        },
    }


def score_review_queue(
    queue: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    validate_config(config)
    output = deepcopy(queue)
    active = 0
    for fixture in output["fixtures"]:
        fixture["selections"] = [
            score_selection(
                selection,
                final_refresh_complete=bool(output["final_refresh_complete"]),
                config=config,
            )
            for selection in fixture["selections"]
        ]
        active += sum(row["overlay_active"] for row in fixture["selections"])
    output["status"] = "discretionary_overlay_scored"
    output["summary"] = {
        "fixtures": len(output["fixtures"]),
        "structurally_reviewable": sum(
            selection["structurally_reviewable"]
            for fixture in output["fixtures"]
            for selection in fixture["selections"]
        ),
        "approved_active_overlays": active,
        "real_capital_positions": 0,
    }
    return output

