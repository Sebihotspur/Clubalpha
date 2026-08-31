"""Conservative, deterministic learning around Clubalpha's locked model.

The research loop never rewrites predictions or formulas. It learns from the
locked base forecast's residuals and produces a versioned research state that
can propose—not silently apply—future adjustments after evidence gates pass.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable

from clubalpha.contextual_backtest import (
    evaluate_contextual_backtest,
    evaluate_goal_coefficient_ablation,
)


RESEARCH_STATE_VERSION = "clubalpha_research_state_v1"


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _day(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _canonical_fingerprint(rows: Iterable[dict[str, Any]]) -> str:
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in sorted(rows, key=lambda item: int(item["match_id"]))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != "clubalpha_research_loop_v1":
        raise ValueError("research loop config version is not supported")
    if float(config["xg_floor"]) <= 0:
        raise ValueError("research loop xG floor must be positive")
    if float(config["recency_half_life_days"]) <= 0:
        raise ValueError("research loop recency half-life must be positive")
    if float(config["prior_match_equivalents"]) < 0:
        raise ValueError("research loop prior must be non-negative")
    boundaries = config.get("locked_boundaries") or {}
    forbidden = (
        "player_alpha_formulas_mutable",
        "base_60_30_10_weights_mutable",
        "historical_residual_cap_mutable",
        "frozen_predictions_mutable",
        "automatic_code_rewrite_allowed",
        "automatic_capital_authorization_allowed",
    )
    if any(boundaries.get(key) is not False for key in forbidden):
        raise ValueError("research loop config weakens a locked boundary")
    if boundaries.get("research_state_can_update_automatically") is not True:
        raise ValueError("research state must be the only automatically mutable layer")


def _recency_weight(kickoff_utc: str, as_of: str, half_life_days: float) -> float:
    age = max(0, (_day(as_of) - _day(kickoff_utc)).days)
    return 0.5 ** (age / half_life_days)


def _posterior_metric(
    observations: list[dict[str, Any]],
    *,
    config: dict[str, Any],
    minimum_observations: int,
) -> dict[str, Any]:
    prior = float(config["prior_match_equivalents"])
    total_weight = sum(float(row["weight"]) for row in observations)
    numerator = sum(
        float(row["weight"]) * float(row["value"]) for row in observations
    )
    raw_mean = numerator / total_weight if total_weight else 0.0
    posterior = numerator / (prior + total_weight) if prior + total_weight else 0.0
    positive_weight = sum(
        float(row["weight"]) for row in observations if float(row["value"]) > 0
    )
    negative_weight = sum(
        float(row["weight"]) for row in observations if float(row["value"]) < 0
    )
    direction_consistency = (
        max(positive_weight, negative_weight) / total_weight if total_weight else 0.0
    )
    threshold = float(config["neutral_log_residual"])
    direction = (
        "above_expected"
        if posterior >= threshold
        else "below_expected" if posterior <= -threshold else "within_noise"
    )
    gates = config["promotion_gates"]
    promotable = bool(
        len(observations) >= minimum_observations
        and total_weight >= float(gates["minimum_effective_evidence"])
        and abs(posterior)
        >= float(gates["minimum_absolute_posterior_log_residual"])
        and direction_consistency >= float(gates["minimum_direction_consistency"])
    )
    return {
        "observations": len(observations),
        "effective_evidence": _rounded(total_weight),
        "raw_weighted_mean_log_residual": _rounded(raw_mean),
        "posterior_log_residual": _rounded(posterior),
        "posterior_multiplier": _rounded(math.exp(posterior)),
        "evidence_confidence": _rounded(
            total_weight / (prior + total_weight) if prior + total_weight else 0.0
        ),
        "direction_consistency": _rounded(direction_consistency),
        "direction": direction,
        "promotion_candidate": promotable,
        "applied_to_forecast": False,
    }


def _weighted_mean(rows: list[dict[str, Any]], key: str) -> float:
    denominator = sum(float(row["weight"]) for row in rows)
    if denominator <= 0:
        return 0.0
    return sum(float(row["weight"]) * float(row[key]) for row in rows) / denominator


def _lineup_belief(
    observations: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    prior = float(config["prior_match_equivalents"])
    prior_rate = float(config["lineup_prior_hit_rate"])
    evidence = sum(float(row["weight"]) for row in observations)
    observed_rate = _weighted_mean(observations, "xi_hit_rate")
    posterior_rate = (
        (prior * prior_rate + evidence * observed_rate) / (prior + evidence)
        if prior + evidence
        else prior_rate
    )
    formation_accuracy = _weighted_mean(observations, "formation_correct")
    thresholds = config["review_thresholds"]
    hit_review = observed_rate < float(thresholds["lineup_hit_rate_below"])
    formation_review = formation_accuracy < float(
        thresholds["formation_accuracy_below"]
    )
    return {
        "team_lineups": len(observations),
        "mean_xi_hits_of_11": _rounded(observed_rate * 11.0, 3),
        "observed_xi_hit_rate": _rounded(observed_rate),
        "posterior_xi_reliability": _rounded(posterior_rate),
        "formation_accuracy": _rounded(formation_accuracy),
        "review_required": bool(hit_review or formation_review),
        "review_reasons": [
            reason
            for reason, active in (
                ("starting_xi_accuracy", hit_review),
                ("formation_accuracy", formation_review),
            )
            if active
        ],
    }


def _route_beliefs(
    observations: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[str(row["preferred_route"])].append(
            {"value": row["attack_log_residual"], "weight": row["route_weight"]}
        )
    minimum = int(config["promotion_gates"]["minimum_route_observations"])
    return [
        {
            "route": route,
            **_posterior_metric(rows, config=config, minimum_observations=minimum),
        }
        for route, rows in sorted(grouped.items())
    ]


def build_research_state(
    contextual_predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    lineup_snapshot: dict[str, Any],
    config: dict[str, Any],
    *,
    as_of: str,
    base_predictions: Iterable[dict[str, Any]] | None = None,
    goal_model_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fold all observed results into a deterministic research-only state."""

    _validate_config(config)
    prediction_rows = list(contextual_predictions)
    result_rows = list(results)
    if result_rows and max(_day(row["kickoff_utc"]) for row in result_rows) > _day(
        as_of
    ):
        raise ValueError("research loop as-of date precedes an observed match")
    evaluation = evaluate_contextual_backtest(
        prediction_rows,
        result_rows,
        lineup_snapshot=lineup_snapshot,
    )
    fixture_evaluation = {
        int(row["match_id"]): row for row in evaluation["fixtures"]
    }
    lineup_rows = {
        (int(row["match_id"]), int(row["team_id"])): row
        for row in (evaluation.get("lineup_projection") or {}).get("rows") or []
    }
    predictions_by_id = {
        int(row["fixture"]["match_id"]): row for row in prediction_rows
    }
    half_life = float(config["recency_half_life_days"])
    floor = float(config["xg_floor"])
    minimum_reliability = float(config["minimum_observation_reliability"])
    team_observations: dict[int, list[dict[str, Any]]] = defaultdict(list)
    all_route_observations: list[dict[str, Any]] = []

    for result in sorted(result_rows, key=lambda row: str(row["kickoff_utc"])):
        match_id = int(result["match_id"])
        prediction = predictions_by_id[match_id]
        diagnosis = fixture_evaluation[match_id]
        recency = _recency_weight(result["kickoff_utc"], as_of, half_life)
        base_total = float(prediction["baseline"]["predicted_xg"]["total"])
        observed_total = float(result["actual_xg"]["total"])
        tempo_residual = math.log((observed_total + 2 * floor) / (base_total + 2 * floor))
        for side, opponent_side in (("home", "away"), ("away", "home")):
            team_id = int(result[f"{side}_team_id"])
            lineup = lineup_rows[(match_id, team_id)]
            lineup_hit_rate = float(lineup["xi_hit_rate"])
            observation_reliability = max(
                minimum_reliability,
                min(1.0, 0.5 + 0.5 * lineup_hit_rate),
            )
            weight = recency * observation_reliability
            base_xg = float(prediction["baseline"]["predicted_xg"][side])
            observed_xg = float(result["actual_xg"][side])
            opponent_base_xg = float(
                prediction["baseline"]["predicted_xg"][opponent_side]
            )
            opponent_observed_xg = float(result["actual_xg"][opponent_side])
            attack_residual = math.log(
                (observed_xg + floor) / (base_xg + floor)
            )
            defensive_exposure_residual = math.log(
                (opponent_observed_xg + floor) / (opponent_base_xg + floor)
            )
            direction = next(
                row
                for row in diagnosis["directional_context_review"]
                if row["side"] == side
            )
            route_weight = weight * float(direction["combined_reliability"])
            row = {
                "match_id": match_id,
                "kickoff_utc": result["kickoff_utc"],
                "team_id": team_id,
                "team": result[f"{side}_team"],
                "opponent": result[f"{opponent_side}_team"],
                "venue": side,
                "weight": _rounded(weight),
                "recency_weight": _rounded(recency),
                "observation_reliability": _rounded(observation_reliability),
                "attack_log_residual": _rounded(attack_residual),
                "defensive_exposure_log_residual": _rounded(
                    defensive_exposure_residual
                ),
                "goal_environment_log_residual": _rounded(tempo_residual),
                "finishing_residual_goals_minus_xg": _rounded(
                    float(result[f"final_{side}_goals"]) - observed_xg
                ),
                "goals_allowed_minus_xg_allowed": _rounded(
                    float(result[f"final_{opponent_side}_goals"])
                    - opponent_observed_xg
                ),
                "xi_hit_rate": _rounded(lineup_hit_rate),
                "formation_correct": float(lineup["formation_correct"]),
                "preferred_route": direction["preferred_route"],
                "route_weight": _rounded(route_weight),
                "context_xg_mae_improvement": direction[
                    "context_xg_mae_improvement"
                ],
                "match_review_class": diagnosis["review_class"],
            }
            team_observations[team_id].append(row)
            all_route_observations.append(row)

    minimum_team_matches = int(
        config["promotion_gates"]["minimum_team_matches"]
    )
    teams = []
    for team_id, observations in team_observations.items():
        def metric(name: str) -> dict[str, Any]:
            return _posterior_metric(
                [
                    {"value": row[name], "weight": row["weight"]}
                    for row in observations
                ],
                config=config,
                minimum_observations=minimum_team_matches,
            )

        team = observations[-1]["team"]
        metrics = {
            "attack_creation": metric("attack_log_residual"),
            "defensive_exposure": metric("defensive_exposure_log_residual"),
            "goal_environment": metric("goal_environment_log_residual"),
        }
        route_beliefs = _route_beliefs(observations, config)
        teams.append(
            {
                "team_id": team_id,
                "team": team,
                "completed_matches": len(observations),
                "beliefs": metrics,
                "lineup_projection": _lineup_belief(observations, config),
                "route_hypotheses": route_beliefs,
                "finishing_variance": {
                    "goals_minus_xg_per_match": _rounded(
                        _weighted_mean(
                            observations, "finishing_residual_goals_minus_xg"
                        )
                    ),
                    "goals_allowed_minus_xg_allowed_per_match": _rounded(
                        _weighted_mean(
                            observations, "goals_allowed_minus_xg_allowed"
                        )
                    ),
                    "changes_strength_beliefs": False,
                },
                "research_flags": sorted(
                    {
                        "small_team_sample"
                        if len(observations) < minimum_team_matches
                        else "",
                        "lineup_projection_review"
                        if _lineup_belief(observations, config)["review_required"]
                        else "",
                    }
                    - {""}
                ),
                "observation_match_ids": [row["match_id"] for row in observations],
            }
        )
    teams.sort(key=lambda row: row["team"])

    promotion_candidates = []
    for team in teams:
        for metric, belief in team["beliefs"].items():
            if belief["promotion_candidate"]:
                promotion_candidates.append(
                    {
                        "team_id": team["team_id"],
                        "team": team["team"],
                        "dimension": metric,
                        "posterior_log_residual": belief["posterior_log_residual"],
                        "posterior_multiplier": belief["posterior_multiplier"],
                        "applied_to_forecast": False,
                    }
                )

    coefficient_ablation = None
    if base_predictions is not None and goal_model_artifact is not None:
        coefficient_ablation = evaluate_goal_coefficient_ablation(
            list(base_predictions), result_rows, goal_model_artifact
        )
    structural = [
        row["fixture"]
        for row in evaluation["fixtures"]
        if row["review_class"] == "structural_miss"
    ]
    lineup_reviews = [
        {
            "team": team["team"],
            "mean_xi_hits_of_11": team["lineup_projection"][
                "mean_xi_hits_of_11"
            ],
            "formation_accuracy": team["lineup_projection"][
                "formation_accuracy"
            ],
            "reasons": team["lineup_projection"]["review_reasons"],
        }
        for team in teams
        if team["lineup_projection"]["review_required"]
    ]
    lineup_reviews.sort(key=lambda row: row["mean_xi_hits_of_11"])
    league_route_beliefs = _route_beliefs(all_route_observations, config)
    return {
        "research_state_version": RESEARCH_STATE_VERSION,
        "research_loop_version": config["version"],
        "status": config["status"],
        "as_of": as_of,
        "learned_through_kickoff_utc": max(
            str(row["kickoff_utc"]) for row in result_rows
        ),
        "input_fingerprint_sha256": _canonical_fingerprint(result_rows),
        "input_match_ids": sorted(int(row["match_id"]) for row in result_rows),
        "method": {
            "target": config["learning_target"],
            "update": "zero-centered shrinkage posterior over recency-and-lineup-reliability weighted log-xG residuals",
            "recency_half_life_days": half_life,
            "prior_match_equivalents": config["prior_match_equivalents"],
            "scoreline_finishing_separated_from_xg_strength": True,
            "recomputed_from_full_append_only_ledger": True,
        },
        "coverage": evaluation["validation"],
        "league_learning": {
            "base_vs_context_metrics": evaluation["metrics"],
            "diagnostics": evaluation["diagnostics"],
            "pre_match_goal_coefficient_ablation": coefficient_ablation,
            "league_route_beliefs": league_route_beliefs,
        },
        "teams": teams,
        "research_queue": {
            "structural_fixture_reviews": structural,
            "lineup_projection_reviews": lineup_reviews,
            "missing_preferred_routes": evaluation["diagnostics"][
                "preferred_route_coverage"
            ]["missing"],
        },
        "promotion_candidates": promotion_candidates,
        "forecast_handoff": {
            "mode": config["promotion_gates"]["mode"],
            "eligible_candidates": len(promotion_candidates),
            "automatically_applied": 0,
            "research_state_available_for_next_cycle": True,
        },
        "locked_boundaries": config["locked_boundaries"],
        "decision_boundaries": {
            "core_architecture_changed": False,
            "base_weights_changed": False,
            "player_alpha_changed": False,
            "frozen_predictions_changed": False,
            "research_state_updated": True,
            "capital_deployment_ready": False,
        },
    }


def learning_summary(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return compact, deterministic queues for a human-readable checkpoint."""

    teams = state["teams"]

    def ranked(dimension: str, reverse: bool = True) -> list[dict[str, Any]]:
        rows = [
            {
                "team": team["team"],
                "matches": team["completed_matches"],
                "posterior_log_residual": team["beliefs"][dimension][
                    "posterior_log_residual"
                ],
                "posterior_multiplier": team["beliefs"][dimension][
                    "posterior_multiplier"
                ],
                "confidence": team["beliefs"][dimension]["evidence_confidence"],
            }
            for team in teams
        ]
        rows.sort(key=lambda row: row["posterior_log_residual"], reverse=reverse)
        return rows[:5]

    return {
        "attack_above_expectation": ranked("attack_creation"),
        "attack_below_expectation": ranked("attack_creation", reverse=False),
        "defensive_exposure_above_expectation": ranked("defensive_exposure"),
        "higher_tempo_than_expected": ranked("goal_environment"),
        "lower_tempo_than_expected": ranked("goal_environment", reverse=False),
    }
