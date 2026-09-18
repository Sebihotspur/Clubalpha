"""Auditable, evidence-weighted learning around Clubalpha's locked champion.

This module does not mutate forecasts or formulas.  It turns every settled
fixture into a Match Learning Card, maintains three deliberately different
memory speeds, and evaluates a residual-based challenger chronologically.
Only matches that occurred before a forecast may inform that forecast.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Iterable

from clubalpha.contextual_backtest import evaluate_contextual_backtest


ADAPTIVE_STATE_VERSION = "clubalpha_adaptive_learning_v1"
MATCH_CARD_VERSION = "clubalpha_match_learning_card_v1"
OUTCOMES = ("home_win", "draw", "away_win")


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _day(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _clip(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _adaptive_config(config: dict[str, Any]) -> dict[str, Any]:
    adaptive = config.get("adaptive_learning") or {}
    memory = adaptive.get("memory") or {}
    evidence = adaptive.get("evidence") or {}
    challenger = adaptive.get("challenger") or {}
    return {
        "memory": {
            "fast": {
                "half_life_days": float(
                    (memory.get("fast") or {}).get("half_life_days", 7.0)
                ),
                "prior_match_equivalents": float(
                    (memory.get("fast") or {}).get("prior_match_equivalents", 2.0)
                ),
                "minimum_observations": int(
                    (memory.get("fast") or {}).get("minimum_observations", 2)
                ),
            },
            "medium": {
                "half_life_days": float(
                    (memory.get("medium") or {}).get("half_life_days", 28.0)
                ),
                "prior_match_equivalents": float(
                    (memory.get("medium") or {}).get(
                        "prior_match_equivalents", 3.0
                    )
                ),
                "minimum_observations": int(
                    (memory.get("medium") or {}).get("minimum_observations", 3)
                ),
            },
            "slow": {
                "half_life_days": float(
                    (memory.get("slow") or {}).get("half_life_days", 120.0)
                ),
                "prior_match_equivalents": float(
                    (memory.get("slow") or {}).get("prior_match_equivalents", 8.0)
                ),
                "minimum_observations": int(
                    (memory.get("slow") or {}).get("minimum_observations", 8)
                ),
            },
        },
        "evidence": {
            "poor_lineup_hit_rate": float(
                evidence.get("poor_lineup_hit_rate", 0.72)
            ),
            "extreme_finishing_goals_minus_xg": float(
                evidence.get("extreme_finishing_goals_minus_xg", 1.0)
            ),
            "context_harm_side_xg_mae": float(
                evidence.get("context_harm_side_xg_mae", 0.03)
            ),
            "outcome_variance_multiplier": float(
                evidence.get("outcome_variance_multiplier", 0.25)
            ),
            "red_card_multiplier": float(
                evidence.get("red_card_multiplier", 0.25)
            ),
            "major_rotation_multiplier": float(
                evidence.get("major_rotation_multiplier", 0.65)
            ),
        },
        "challenger": {
            "minimum_prior_team_matches": int(
                challenger.get("minimum_prior_team_matches", 2)
            ),
            "minimum_validation_matches": int(
                challenger.get("minimum_validation_matches", 20)
            ),
            "maximum_absolute_log_xg_adjustment": float(
                challenger.get("maximum_absolute_log_xg_adjustment", 0.12)
            ),
            "minimum_brier_improvement": float(
                challenger.get("minimum_brier_improvement", 0.0)
            ),
            "minimum_xg_mae_improvement": float(
                challenger.get("minimum_xg_mae_improvement", 0.0)
            ),
            "promotion_mode": str(
                challenger.get("promotion_mode", "human_review_only")
            ),
        },
    }


def _validate_config(config: dict[str, Any], adaptive: dict[str, Any]) -> None:
    boundaries = config.get("locked_boundaries") or {}
    locked_false = (
        "player_alpha_formulas_mutable",
        "base_60_30_10_weights_mutable",
        "frozen_predictions_mutable",
        "automatic_code_rewrite_allowed",
        "automatic_capital_authorization_allowed",
    )
    if any(boundaries.get(key) is not False for key in locked_false):
        raise ValueError("adaptive learning weakens a locked boundary")
    if adaptive["challenger"]["promotion_mode"] != "human_review_only":
        raise ValueError("adaptive challenger must require human review")
    for speed in adaptive["memory"].values():
        if speed["half_life_days"] <= 0 or speed["prior_match_equivalents"] < 0:
            raise ValueError("adaptive memory settings must be positive")
        if speed["minimum_observations"] < 1:
            raise ValueError("adaptive memory requires at least one observation")


def _probabilities_from_xg(home_xg: float, away_xg: float) -> dict[str, float]:
    """Deterministic independent-Poisson translation for challenger scoring."""

    maximum_goals = 12

    def poisson(expected: float) -> list[float]:
        values = [math.exp(-expected)]
        for goals in range(1, maximum_goals + 1):
            values.append(values[-1] * expected / goals)
        return values

    home = poisson(home_xg)
    away = poisson(away_xg)
    grid = [
        (home_goals, away_goals, home_p * away_p)
        for home_goals, home_p in enumerate(home)
        for away_goals, away_p in enumerate(away)
    ]
    mass = sum(row[2] for row in grid)
    probabilities = {
        "home_win": sum(p for h, a, p in grid if h > a) / mass,
        "draw": sum(p for h, a, p in grid if h == a) / mass,
        "away_win": sum(p for h, a, p in grid if h < a) / mass,
        "over_2_5": sum(p for h, a, p in grid if h + a > 2.5) / mass,
    }
    return {key: _rounded(value) for key, value in probabilities.items()}


def _one_x_two(probabilities: dict[str, Any]) -> dict[str, float]:
    return {key: float(probabilities[key]) for key in OUTCOMES}


def _over_2_5(probabilities: dict[str, Any]) -> float:
    if "over_2_5" in probabilities:
        return float(probabilities["over_2_5"])
    return float(probabilities["over"]["2.5"])


def _top_outcome(probabilities: dict[str, float]) -> str:
    return max(OUTCOMES, key=lambda key: probabilities[key])


def _brier(probabilities: dict[str, float], outcome: str) -> float:
    return sum((probabilities[key] - float(key == outcome)) ** 2 for key in OUTCOMES)


def _optional_red_cards(result: dict[str, Any]) -> int:
    total = 0
    for side in ("home", "away"):
        stats = result.get(f"{side}_stats") or {}
        for key in ("red_cards", "redCards", "red_card"):
            value = stats.get(key)
            if value is not None:
                total += int(float(value))
                break
    return total


def _match_attribution(
    diagnosis: dict[str, Any],
    result: dict[str, Any],
    lineup_rows: list[dict[str, Any]],
    adaptive: dict[str, Any],
) -> dict[str, Any]:
    evidence = adaptive["evidence"]
    lineup_rates = [float(row["xi_hit_rate"]) for row in lineup_rows]
    lineup_reliability = sum(lineup_rates) / len(lineup_rates) if lineup_rates else 0.5
    formation_misses = sum(not bool(row["formation_correct"]) for row in lineup_rows)
    major_rotation = bool(
        lineup_rates and min(lineup_rates) < evidence["poor_lineup_hit_rate"]
    )
    red_cards = _optional_red_cards(result)
    extreme_finishing = any(
        abs(float(result[f"final_{side}_goals"]) - float(result["actual_xg"][side]))
        >= evidence["extreme_finishing_goals_minus_xg"]
        for side in ("home", "away")
    )
    context_harm = (
        float(diagnosis["xg_side_mae_improvement"])
        < -evidence["context_harm_side_xg_mae"]
    )
    process_weight = lineup_reliability
    if major_rotation:
        process_weight *= evidence["major_rotation_multiplier"]
    if red_cards:
        process_weight *= evidence["red_card_multiplier"]
    outcome_weight = process_weight
    if extreme_finishing or diagnosis["review_class"] == "process_supported_outcome_variance":
        outcome_weight *= evidence["outcome_variance_multiplier"]

    # Individual draw misses become calibration reviews only when the xG process
    # also looked draw-like. Aggregate calibration still decides any correction.
    draw_review = bool(
        result["outcome"] == "draw"
        and diagnosis["xg_process_outcome"] == "draw"
        and diagnosis["contextual_top_pick"] != "draw"
    )
    if major_rotation:
        primary = "lineup_projection"
    elif red_cards:
        primary = "match_state_disruption"
    elif diagnosis["review_class"] == "process_supported_outcome_variance" or extreme_finishing:
        primary = "outcome_variance"
    elif draw_review:
        primary = "draw_calibration_review"
    elif diagnosis["review_class"] == "structural_miss" and context_harm:
        primary = "archetype_context"
    elif diagnosis["review_class"] == "structural_miss":
        primary = "club_form_or_team_strength"
    else:
        primary = "model_supported"

    secondary = []
    if formation_misses:
        secondary.append("formation_projection")
    if context_harm:
        secondary.append("context_worsened_xg_error")
    if extreme_finishing:
        secondary.append("extreme_finishing")
    if draw_review:
        secondary.append("draw_probability_review")
    return {
        "primary": primary,
        "secondary": sorted(set(secondary)),
        "review_class": diagnosis["review_class"],
        "major_rotation_or_lineup_miss": major_rotation,
        "formation_misses": formation_misses,
        "red_cards_observed": red_cards,
        "extreme_finishing": extreme_finishing,
        "context_harmed_side_xg_mae": context_harm,
        "process_learning_weight": _rounded(process_weight),
        "outcome_learning_weight": _rounded(outcome_weight),
    }


def _team_signal(
    *,
    side: str,
    prediction: dict[str, Any],
    result: dict[str, Any],
    lineup: dict[str, Any] | None,
    attribution: dict[str, Any],
    floor: float,
) -> dict[str, Any]:
    opponent_side = "away" if side == "home" else "home"
    predicted = prediction["contextual"]["predicted_xg"]
    actual = result["actual_xg"]
    attack = math.log((float(actual[side]) + floor) / (float(predicted[side]) + floor))
    exposure = math.log(
        (float(actual[opponent_side]) + floor)
        / (float(predicted[opponent_side]) + floor)
    )
    tempo = math.log(
        (float(actual["total"]) + 2 * floor)
        / (float(predicted["total"]) + 2 * floor)
    )
    return {
        "team_id": int(result[f"{side}_team_id"]),
        "team": result[f"{side}_team"],
        "opponent": result[f"{opponent_side}_team"],
        "venue": side,
        "attack_log_residual": _rounded(attack),
        "defensive_exposure_log_residual": _rounded(exposure),
        "goal_environment_log_residual": _rounded(tempo),
        "structural_quality_log_residual": _rounded(0.5 * (attack - exposure)),
        "xi_hit_rate": _rounded(float(lineup["xi_hit_rate"]) if lineup else 0.5),
        "formation_correct": bool(lineup and lineup["formation_correct"]),
        "process_learning_weight": attribution["process_learning_weight"],
        "memory_targets": {
            "fast": ["lineup_reliability", "formation_persistence"],
            "medium": ["attack_creation", "defensive_exposure", "goal_environment"],
            "slow": ["structural_quality_review"],
        },
    }


def build_match_learning_cards(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    lineup_snapshot: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one immutable diagnosis card for every completed fixture."""

    prediction_rows = list(predictions)
    result_rows = list(results)
    adaptive = _adaptive_config(config)
    _validate_config(config, adaptive)
    evaluation = evaluate_contextual_backtest(
        prediction_rows, result_rows, lineup_snapshot=lineup_snapshot
    )
    predictions_by_id = {
        int(row["fixture"]["match_id"]): row for row in prediction_rows
    }
    results_by_id = {int(row["match_id"]): row for row in result_rows}
    diagnosis_by_id = {int(row["match_id"]): row for row in evaluation["fixtures"]}
    lineups_by_match: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in (evaluation.get("lineup_projection") or {}).get("rows") or []:
        lineups_by_match[int(row["match_id"])].append(row)
    floor = float(config["xg_floor"])
    cards = []
    for match_id in sorted(
        results_by_id, key=lambda value: str(results_by_id[value]["kickoff_utc"])
    ):
        prediction = predictions_by_id[match_id]
        result = results_by_id[match_id]
        diagnosis = diagnosis_by_id[match_id]
        lineup_rows = lineups_by_match.get(match_id) or []
        lineup_by_team = {int(row["team_id"]): row for row in lineup_rows}
        attribution = _match_attribution(
            diagnosis, result, lineup_rows, adaptive
        )
        contextual_probabilities = _one_x_two(
            prediction["contextual"]["probabilities"]
        )
        total_goals = int(result["final_home_goals"]) + int(
            result["final_away_goals"]
        )
        team_signals = []
        for side in ("home", "away"):
            team_id = int(result[f"{side}_team_id"])
            team_signals.append(
                _team_signal(
                    side=side,
                    prediction=prediction,
                    result=result,
                    lineup=lineup_by_team.get(team_id),
                    attribution=attribution,
                    floor=floor,
                )
            )
        cards.append(
            {
                "match_learning_card_version": MATCH_CARD_VERSION,
                "match_id": match_id,
                "kickoff_utc": result["kickoff_utc"],
                "fixture": diagnosis["fixture"],
                "competition_scope": prediction["fixture"].get(
                    "source_scope", "unknown"
                ),
                "pre_match_fingerprint": {
                    "baseline_predicted_xg": prediction["baseline"]["predicted_xg"],
                    "contextual_predicted_xg": prediction["contextual"]["predicted_xg"],
                    "contextual_probabilities": {
                        **contextual_probabilities,
                        "over_2_5": _over_2_5(
                            prediction["contextual"]["probabilities"]
                        ),
                    },
                    "probability_leader": _top_outcome(contextual_probabilities),
                    "directional_context": prediction.get("directional_context"),
                },
                "observed": {
                    "score": diagnosis["score"],
                    "outcome": result["outcome"],
                    "actual_xg": result["actual_xg"],
                    "xg_process_outcome": diagnosis["xg_process_outcome"],
                    "over_2_5": total_goals > 2,
                    "source": result.get("source"),
                    "source_coverage_level": result.get(
                        "source_coverage_level", "unknown"
                    ),
                },
                "lineup_audit": lineup_rows,
                "performance": {
                    "one_x_two_hit": diagnosis["contextual_top_pick"]
                    == result["outcome"],
                    "over_2_5_hit": (
                        _over_2_5(prediction["contextual"]["probabilities"])
                        >= 0.5
                    )
                    == (total_goals > 2),
                    "contextual_actual_outcome_probability": diagnosis[
                        "contextual_actual_outcome_probability"
                    ],
                    "context_xg_side_mae_improvement": diagnosis[
                        "xg_side_mae_improvement"
                    ],
                    "baseline_scores": diagnosis["scores"]["baseline"],
                    "champion_scores": diagnosis["scores"]["contextual"],
                },
                "error_attribution": attribution,
                "team_memory_signals": team_signals,
                "governance": {
                    "player_alpha_changed": False,
                    "base_60_30_10_changed": False,
                    "frozen_prediction_changed": False,
                    "automatic_forecast_update": False,
                    "automatic_capital_authorization": False,
                },
            }
        )
    return cards


def _recency_weight(kickoff_utc: str, as_of: str, half_life_days: float) -> float:
    age = max(0, (_day(as_of) - _day(kickoff_utc)).days)
    return 0.5 ** (age / half_life_days)


def _posterior(
    rows: list[dict[str, Any]],
    key: str,
    *,
    as_of: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    weighted = [
        (
            float(row["process_learning_weight"])
            * _recency_weight(row["kickoff_utc"], as_of, settings["half_life_days"]),
            float(row[key]),
        )
        for row in rows
    ]
    evidence = sum(weight for weight, _ in weighted)
    numerator = sum(weight * value for weight, value in weighted)
    prior = float(settings["prior_match_equivalents"])
    raw = numerator / evidence if evidence else 0.0
    posterior = numerator / (prior + evidence) if prior + evidence else 0.0
    return {
        "observations": len(rows),
        "effective_evidence": _rounded(evidence),
        "raw_weighted_mean": _rounded(raw),
        "posterior_log_residual": _rounded(posterior),
        "posterior_multiplier": _rounded(math.exp(posterior)),
        "evidence_confidence": _rounded(
            evidence / (prior + evidence) if prior + evidence else 0.0
        ),
        "eligible": len(rows) >= int(settings["minimum_observations"]),
        "applied_to_champion": False,
    }


def _memory_state(
    cards: list[dict[str, Any]], adaptive: dict[str, Any], *, as_of: str
) -> dict[str, Any]:
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        for signal in card["team_memory_signals"]:
            by_team[int(signal["team_id"])].append(
                {**signal, "kickoff_utc": card["kickoff_utc"]}
            )
    output = {"fast": [], "medium": [], "slow": []}
    for team_id, rows in sorted(by_team.items(), key=lambda item: item[1][-1]["team"]):
        team = rows[-1]["team"]
        fast = adaptive["memory"]["fast"]
        lineup_evidence = sum(
            float(row["process_learning_weight"])
            * _recency_weight(row["kickoff_utc"], as_of, fast["half_life_days"])
            for row in rows
        )
        lineup_observed = (
            sum(
                float(row["xi_hit_rate"])
                * float(row["process_learning_weight"])
                * _recency_weight(
                    row["kickoff_utc"], as_of, fast["half_life_days"]
                )
                for row in rows
            )
            / lineup_evidence
            if lineup_evidence
            else 0.8
        )
        prior = fast["prior_match_equivalents"]
        lineup_posterior = (
            (prior * 0.8 + lineup_evidence * lineup_observed)
            / (prior + lineup_evidence)
            if prior + lineup_evidence
            else 0.8
        )
        output["fast"].append(
            {
                "team_id": team_id,
                "team": team,
                "observations": len(rows),
                "projected_xi_reliability": _rounded(lineup_posterior),
                "formation_accuracy": _rounded(
                    sum(float(row["formation_correct"]) for row in rows) / len(rows)
                ),
                "eligible": len(rows) >= fast["minimum_observations"],
                "applied_to_champion": False,
            }
        )
        medium = adaptive["memory"]["medium"]
        output["medium"].append(
            {
                "team_id": team_id,
                "team": team,
                "attack_creation": _posterior(
                    rows, "attack_log_residual", as_of=as_of, settings=medium
                ),
                "defensive_exposure": _posterior(
                    rows,
                    "defensive_exposure_log_residual",
                    as_of=as_of,
                    settings=medium,
                ),
                "goal_environment": _posterior(
                    rows,
                    "goal_environment_log_residual",
                    as_of=as_of,
                    settings=medium,
                ),
            }
        )
        slow = adaptive["memory"]["slow"]
        output["slow"].append(
            {
                "team_id": team_id,
                "team": team,
                "structural_quality": _posterior(
                    rows,
                    "structural_quality_log_residual",
                    as_of=as_of,
                    settings=slow,
                ),
                "player_alpha_formula_update_allowed": False,
            }
        )
    return {
        "policy": {
            "fast": "lineups, formations and short-lived availability state",
            "medium": "attack, defence, tempo and matchup execution",
            "slow": "structural quality review; never an automatic Player Alpha rewrite",
        },
        "teams": output,
    }


def _history_posterior(
    rows: list[dict[str, Any]], key: str, *, as_of: str, settings: dict[str, Any]
) -> float:
    return float(
        _posterior(rows, key, as_of=as_of, settings=settings)[
            "posterior_log_residual"
        ]
    )


def _metric_summary(rows: list[dict[str, Any]], model: str) -> dict[str, Any]:
    if not rows:
        return {
            "fixtures": 0,
            "xg_side_mae": None,
            "one_x_two_brier": None,
            "one_x_two_accuracy": None,
            "over_2_5_brier": None,
        }
    return {
        "fixtures": len(rows),
        "xg_side_mae": _rounded(
            sum(rows[index][model]["xg_side_absolute_error"] for index in range(len(rows)))
            / (2 * len(rows))
        ),
        "one_x_two_brier": _rounded(
            sum(row[model]["one_x_two_brier"] for row in rows) / len(rows)
        ),
        "one_x_two_accuracy": _rounded(
            sum(row[model]["one_x_two_hit"] for row in rows) / len(rows)
        ),
        "over_2_5_brier": _rounded(
            sum(row[model]["over_2_5_brier"] for row in rows) / len(rows)
        ),
    }


def _chronological_challenger(
    cards: list[dict[str, Any]], adaptive: dict[str, Any]
) -> dict[str, Any]:
    settings = adaptive["memory"]["medium"]
    policy = adaptive["challenger"]
    history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    validation = []
    for card in sorted(cards, key=lambda row: (row["kickoff_utc"], row["match_id"])):
        signals = {row["venue"]: row for row in card["team_memory_signals"]}
        home = signals["home"]
        away = signals["away"]
        home_history = history[int(home["team_id"])]
        away_history = history[int(away["team_id"])]
        minimum = policy["minimum_prior_team_matches"]
        if len(home_history) >= minimum and len(away_history) >= minimum:
            as_of = card["kickoff_utc"]
            home_attack = _history_posterior(
                home_history, "attack_log_residual", as_of=as_of, settings=settings
            )
            home_exposure = _history_posterior(
                home_history,
                "defensive_exposure_log_residual",
                as_of=as_of,
                settings=settings,
            )
            away_attack = _history_posterior(
                away_history, "attack_log_residual", as_of=as_of, settings=settings
            )
            away_exposure = _history_posterior(
                away_history,
                "defensive_exposure_log_residual",
                as_of=as_of,
                settings=settings,
            )
            home_tempo = _history_posterior(
                home_history,
                "goal_environment_log_residual",
                as_of=as_of,
                settings=settings,
            )
            away_tempo = _history_posterior(
                away_history,
                "goal_environment_log_residual",
                as_of=as_of,
                settings=settings,
            )
            limit = policy["maximum_absolute_log_xg_adjustment"]
            tempo = 0.25 * (home_tempo + away_tempo)
            home_adjustment = _clip(
                0.5 * home_attack + 0.5 * away_exposure + tempo, limit
            )
            away_adjustment = _clip(
                0.5 * away_attack + 0.5 * home_exposure + tempo, limit
            )
            champion_xg = card["pre_match_fingerprint"]["contextual_predicted_xg"]
            challenger_xg = {
                "home": float(champion_xg["home"]) * math.exp(home_adjustment),
                "away": float(champion_xg["away"]) * math.exp(away_adjustment),
            }
            challenger_xg["total"] = challenger_xg["home"] + challenger_xg["away"]
            challenger_probabilities = _probabilities_from_xg(
                challenger_xg["home"], challenger_xg["away"]
            )
            champion_probabilities = card["pre_match_fingerprint"][
                "contextual_probabilities"
            ]
            outcome = card["observed"]["outcome"]
            observed_xg = card["observed"]["actual_xg"]
            happened_over = bool(card["observed"]["over_2_5"])

            def scores(xg: dict[str, float], probabilities: dict[str, float]) -> dict[str, Any]:
                one_x_two = _one_x_two(probabilities)
                over_probability = float(probabilities["over_2_5"])
                return {
                    "xg_side_absolute_error": abs(float(xg["home"]) - float(observed_xg["home"]))
                    + abs(float(xg["away"]) - float(observed_xg["away"])),
                    "one_x_two_brier": _brier(one_x_two, outcome),
                    "one_x_two_hit": _top_outcome(one_x_two) == outcome,
                    "over_2_5_brier": (over_probability - float(happened_over)) ** 2,
                }

            validation.append(
                {
                    "match_id": card["match_id"],
                    "kickoff_utc": card["kickoff_utc"],
                    "fixture": card["fixture"],
                    "home_log_xg_adjustment": _rounded(home_adjustment),
                    "away_log_xg_adjustment": _rounded(away_adjustment),
                    "champion": scores(champion_xg, champion_probabilities),
                    "challenger": scores(challenger_xg, challenger_probabilities),
                }
            )
        for signal in card["team_memory_signals"]:
            history[int(signal["team_id"])].append(
                {**signal, "kickoff_utc": card["kickoff_utc"]}
            )
    champion = _metric_summary(validation, "champion")
    challenger = _metric_summary(validation, "challenger")
    if validation:
        improvements = {
            "xg_side_mae": _rounded(
                float(champion["xg_side_mae"]) - float(challenger["xg_side_mae"])
            ),
            "one_x_two_brier": _rounded(
                float(champion["one_x_two_brier"])
                - float(challenger["one_x_two_brier"])
            ),
            "over_2_5_brier": _rounded(
                float(champion["over_2_5_brier"])
                - float(challenger["over_2_5_brier"])
            ),
        }
    else:
        improvements = {
            "xg_side_mae": None,
            "one_x_two_brier": None,
            "over_2_5_brier": None,
        }
    enough = len(validation) >= policy["minimum_validation_matches"]
    passes = bool(
        enough
        and improvements["xg_side_mae"] is not None
        and improvements["xg_side_mae"] >= policy["minimum_xg_mae_improvement"]
        and improvements["one_x_two_brier"] >= policy["minimum_brier_improvement"]
        and improvements["over_2_5_brier"] >= -0.005
    )
    return {
        "method": "chronological pre-match-only residual replay",
        "champion": champion,
        "challenger": challenger,
        "improvement_positive_is_better": improvements,
        "validation_rows": validation,
        "promotion_gate": {
            "minimum_validation_matches": policy["minimum_validation_matches"],
            "sample_sufficient": enough,
            "metrics_pass": passes,
            "status": "eligible_for_human_review" if passes else "hold_champion",
            "mode": policy["promotion_mode"],
            "automatically_promoted": False,
        },
    }


def build_adaptive_learning_state(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    lineup_snapshot: dict[str, Any],
    config: dict[str, Any],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Build cards, memory and challenger audit without touching the champion."""

    prediction_rows = list(predictions)
    result_rows = list(results)
    adaptive = _adaptive_config(config)
    _validate_config(config, adaptive)
    cards = build_match_learning_cards(
        prediction_rows, result_rows, lineup_snapshot, config
    )
    if cards and max(_day(row["kickoff_utc"]) for row in cards) > _day(as_of):
        raise ValueError("adaptive learning as-of date precedes an observed match")
    attribution_counts = Counter(
        card["error_attribution"]["primary"] for card in cards
    )
    return {
        "adaptive_learning_version": ADAPTIVE_STATE_VERSION,
        "status": "challenger_research_only",
        "as_of": as_of,
        "completed_match_cards": len(cards),
        "match_learning_cards": cards,
        "error_attribution_summary": dict(sorted(attribution_counts.items())),
        "memory": _memory_state(cards, adaptive, as_of=as_of),
        "champion_challenger": _chronological_challenger(cards, adaptive),
        "governance": {
            "champion": "locked Holy Grail contextual forecast",
            "adaptive_state_updates_automatically": True,
            "challenger_updates_champion_automatically": False,
            "player_alpha_formula_updates_automatically": False,
            "base_60_30_10_updates_automatically": False,
            "capital_deployment_ready": False,
        },
    }
