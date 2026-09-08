"""Evidence-shrunk venue and draw calibration for future shadow forecasts.

The layer sits after the locked 60/30/10 fixture intelligence and contextual
xG adjustment. It learns only from append-only, frozen forecasts and completed
results. Player Alpha and the component weights are never refitted here.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Iterable


CALIBRATION_VERSION = "clubalpha_fixture_calibration_v1"


def _day(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


def _clip(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _logit(probability: float) -> float:
    probability = max(1e-9, min(1.0 - 1e-9, probability))
    return math.log(probability / (1.0 - probability))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != CALIBRATION_VERSION:
        raise ValueError("fixture calibration config version is not supported")
    if float(config["xg_floor"]) <= 0:
        raise ValueError("fixture calibration xG floor must be positive")
    for section in ("venue", "draw"):
        if float(config[section]["prior_match_equivalents"]) < 0:
            raise ValueError(f"{section} prior must be non-negative")
    boundaries = config.get("locked_boundaries") or {}
    forbidden = (
        "player_alpha_formulas_mutable",
        "base_60_30_10_weights_mutable",
        "frozen_predictions_mutable",
        "automatic_capital_authorization_allowed",
    )
    if any(boundaries.get(key) is not False for key in forbidden):
        raise ValueError("fixture calibration weakens a locked boundary")


def build_calibration_observations(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join normalized contextual forecasts to their append-only results."""

    result_by_id = {int(row["match_id"]): row for row in results}
    observations = []
    for prediction in predictions:
        fixture = prediction["fixture"]
        match_id = int(fixture["match_id"])
        result = result_by_id.get(match_id)
        if result is None:
            continue
        model = prediction["contextual"]
        observations.append(
            {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team_id": int(fixture["home_team_id"]),
                "home_team": fixture["home_team"],
                "away_team_id": int(fixture["away_team_id"]),
                "away_team": fixture["away_team"],
                "predicted_xg": {
                    "home": float(model["predicted_xg"]["home"]),
                    "away": float(model["predicted_xg"]["away"]),
                },
                "probabilities": {
                    "home_win": float(model["probabilities"]["home_win"]),
                    "draw": float(model["probabilities"]["draw"]),
                    "away_win": float(model["probabilities"]["away_win"]),
                },
                "actual_xg": {
                    "home": float(result["actual_xg"]["home"]),
                    "away": float(result["actual_xg"]["away"]),
                },
                "outcome": result["outcome"],
            }
        )
    observations.sort(key=lambda row: (row["kickoff_utc"], row["match_id"]))
    return observations


def _team_venue_modifiers(
    observations: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    venue = config["venue"]
    floor = float(config["xg_floor"])
    grouped: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"team": None, "home": [], "away": []}
    )
    for row in observations:
        predicted_ratio = (row["predicted_xg"]["home"] + floor) / (
            row["predicted_xg"]["away"] + floor
        )
        observed_ratio = (row["actual_xg"]["home"] + floor) / (
            row["actual_xg"]["away"] + floor
        )
        residual = math.log(observed_ratio / predicted_ratio)
        home = grouped[int(row["home_team_id"])]
        home["team"] = row["home_team"]
        home["home"].append(residual)
        away = grouped[int(row["away_team_id"])]
        away["team"] = row["away_team"]
        away["away"].append(-residual)

    minimum_home = int(venue["minimum_team_home_matches"])
    minimum_away = int(venue["minimum_team_away_matches"])
    prior = float(venue["team_prior_match_equivalents"])
    limit = float(venue["maximum_absolute_team_log_ratio_effect"])
    output = []
    for team_id, values in grouped.items():
        home_rows = values["home"]
        away_rows = values["away"]
        eligible = len(home_rows) >= minimum_home and len(away_rows) >= minimum_away
        raw_difference = (
            sum(home_rows) / len(home_rows) - sum(away_rows) / len(away_rows)
            if home_rows and away_rows
            else 0.0
        )
        evidence = len(home_rows) + len(away_rows)
        confidence = evidence / (prior + evidence) if prior + evidence else 0.0
        # Half the home-minus-away difference is the team's effect at either
        # venue around its neutral strength. It is zero until both venue gates pass.
        effect = _clip(0.5 * raw_difference * confidence, limit) if eligible else 0.0
        output.append(
            {
                "team_id": team_id,
                "team": values["team"],
                "home_matches": len(home_rows),
                "away_matches": len(away_rows),
                "raw_home_minus_away_log_ratio": round(raw_difference, 6),
                "evidence_confidence": round(confidence, 6),
                "eligible": eligible,
                "log_ratio_effect": round(effect, 6),
            }
        )
    return sorted(output, key=lambda row: row["team"])


def fit_fixture_calibration(
    observations: Iterable[dict[str, Any]],
    config: dict[str, Any],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Fit a conservative current-league venue and draw calibration artifact."""

    _validate_config(config)
    rows = list(observations)
    if not rows:
        raise ValueError("fixture calibration requires completed observations")
    if max(_day(row["kickoff_utc"]) for row in rows) > _day(as_of):
        raise ValueError("fixture calibration as-of date precedes an observation")
    minimum = int(config["minimum_training_matches"])
    if len(rows) < minimum:
        raise ValueError(
            f"fixture calibration requires at least {minimum} completed matches"
        )

    floor = float(config["xg_floor"])
    venue = config["venue"]
    predicted_home = sum(row["predicted_xg"]["home"] for row in rows)
    predicted_away = sum(row["predicted_xg"]["away"] for row in rows)
    observed_home = sum(row["actual_xg"]["home"] for row in rows)
    observed_away = sum(row["actual_xg"]["away"] for row in rows)
    predicted_ratio = (predicted_home + len(rows) * floor) / (
        predicted_away + len(rows) * floor
    )
    observed_ratio = (observed_home + len(rows) * floor) / (
        observed_away + len(rows) * floor
    )
    raw_venue_correction = math.log(observed_ratio / predicted_ratio)
    venue_prior = float(venue["prior_match_equivalents"])
    venue_confidence = len(rows) / (venue_prior + len(rows))
    venue_correction = _clip(
        raw_venue_correction * venue_confidence,
        float(venue["maximum_absolute_league_log_ratio_correction"]),
    )

    draw = config["draw"]
    predicted_draw_rate = sum(row["probabilities"]["draw"] for row in rows) / len(rows)
    observed_draws = sum(row["outcome"] == "draw" for row in rows)
    observed_draw_rate = observed_draws / len(rows)
    draw_prior = float(draw["prior_match_equivalents"])
    posterior_draw_rate = (
        draw_prior * predicted_draw_rate + observed_draws
    ) / (draw_prior + len(rows))
    raw_draw_correction = _logit(posterior_draw_rate) - _logit(predicted_draw_rate)
    draw_correction = _clip(
        raw_draw_correction,
        float(draw["maximum_absolute_logit_correction"]),
    )
    validation_minimum = int(config["minimum_validation_matches"])
    team_modifiers = _team_venue_modifiers(rows, config)
    return {
        "version": CALIBRATION_VERSION,
        "status": config["status"],
        "as_of": as_of,
        "learned_through_kickoff_utc": max(row["kickoff_utc"] for row in rows),
        "training_matches": len(rows),
        "training_match_ids": sorted(int(row["match_id"]) for row in rows),
        "method": {
            "venue": "evidence-shrunk aggregate xG log-ratio residual",
            "draw": "evidence-shrunk draw-rate logit intercept",
            "team_venue": "home-versus-away xG-ratio residual with two-sided evidence gate",
        },
        "league_venue": {
            "predicted_home_away_xg_ratio": round(predicted_ratio, 6),
            "observed_home_away_xg_ratio": round(observed_ratio, 6),
            "raw_log_ratio_correction": round(raw_venue_correction, 6),
            "evidence_confidence": round(venue_confidence, 6),
            "applied_log_ratio_correction": round(venue_correction, 6),
        },
        "draw_calibration": {
            "predicted_draw_rate": round(predicted_draw_rate, 6),
            "observed_draws": observed_draws,
            "observed_draw_rate": round(observed_draw_rate, 6),
            "posterior_draw_rate": round(posterior_draw_rate, 6),
            "applied_logit_correction": round(draw_correction, 6),
            "draw_zone_max_probability_gap": float(
                draw["draw_zone_max_probability_gap"]
            ),
            "draw_zone_max_side_probability": float(
                draw["draw_zone_max_side_probability"]
            ),
        },
        "team_venue_modifiers": team_modifiers,
        "decision_boundaries": {
            "shadow_forecast_ready": True,
            "probability_validated": len(rows) >= validation_minimum,
            "team_venue_modifiers_active": any(row["eligible"] for row in team_modifiers),
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "locked_boundaries": config["locked_boundaries"],
        "quality_flags": (
            ["small_fixture_calibration_sample"]
            if len(rows) < validation_minimum
            else []
        ),
    }


def _poisson_draw(rng: random.Random, expected_goals: float) -> int:
    threshold = math.exp(-expected_goals)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def _weighted_simulation(
    home_xg: float,
    away_xg: float,
    *,
    draw_logit_correction: float,
    draws: int,
    seed: int,
    totals_lines: list[float],
) -> dict[str, Any]:
    rng = random.Random(seed)
    scorelines: Counter[tuple[int, int]] = Counter()
    for _ in range(draws):
        scorelines[
            (_poisson_draw(rng, home_xg), _poisson_draw(rng, away_xg))
        ] += 1
    raw_draw = sum(count for (home, away), count in scorelines.items() if home == away) / draws
    target_draw = _sigmoid(_logit(raw_draw) + draw_logit_correction)
    draw_weight = target_draw / raw_draw
    non_draw_weight = (1.0 - target_draw) / (1.0 - raw_draw)
    weighted = {
        score: count * (draw_weight if score[0] == score[1] else non_draw_weight)
        for score, count in scorelines.items()
    }
    denominator = sum(weighted.values())
    outcomes = {
        "home_win": sum(value for (home, away), value in weighted.items() if home > away),
        "draw": sum(value for (home, away), value in weighted.items() if home == away),
        "away_win": sum(value for (home, away), value in weighted.items() if home < away),
    }
    over = {
        str(line): sum(
            value
            for (home, away), value in weighted.items()
            if home + away > float(line)
        )
        / denominator
        for line in totals_lines
    }
    btts = sum(
        value for (home, away), value in weighted.items() if home > 0 and away > 0
    ) / denominator
    one_x_two = {
        key: round(value / denominator, 6) for key, value in outcomes.items()
    }
    # The official archive requires an exact probability simplex. Independent
    # six-decimal rounding can otherwise leave a harmless +/-0.000001 residue.
    # Reconcile that residue to the largest outcome instead of weakening the
    # immutable-slate validator.
    probability_leader = max(one_x_two, key=one_x_two.get)
    simplex_residue = round(1.0 - sum(one_x_two.values()), 6)
    one_x_two[probability_leader] = round(
        one_x_two[probability_leader] + simplex_residue,
        6,
    )
    probabilities = {
        **one_x_two,
        "over": {key: round(value, 6) for key, value in over.items()},
        "under": {key: round(1.0 - value, 6) for key, value in over.items()},
        "btts_yes": round(btts, 6),
        "btts_no": round(1.0 - btts, 6),
    }
    common = [
        {"score": f"{home}-{away}", "probability": round(value / denominator, 6)}
        for (home, away), value in sorted(
            weighted.items(), key=lambda item: item[1], reverse=True
        )[:5]
    ]
    return {
        "probabilities": probabilities,
        "most_likely_scorelines": common,
        "raw_draw_probability": round(raw_draw, 6),
        "calibrated_draw_probability": probabilities["draw"],
    }


def calibrate_fixture_forecast(
    prediction: dict[str, Any],
    artifact: dict[str, Any],
    config: dict[str, Any],
    *,
    enforce_chronology: bool = True,
) -> dict[str, Any]:
    """Apply a frozen calibration artifact to one future shadow forecast."""

    _validate_config(config)
    if artifact.get("version") != CALIBRATION_VERSION:
        raise ValueError("fixture calibration artifact version is not supported")
    if not artifact.get("decision_boundaries", {}).get("shadow_forecast_ready"):
        raise ValueError("fixture calibration artifact is not shadow ready")
    fixture = prediction["fixture"]
    if enforce_chronology and _day(artifact["learned_through_kickoff_utc"]) >= _day(
        fixture["kickoff_utc"]
    ):
        raise ValueError("fixture calibration must predate the forecast fixture")

    team_modifiers = {
        int(row["team_id"]): row
        for row in artifact.get("team_venue_modifiers") or []
    }
    home_modifier = team_modifiers.get(int(fixture["home_team_id"])) or {}
    away_modifier = team_modifiers.get(int(fixture["away_team_id"])) or {}
    league_correction = float(
        artifact["league_venue"]["applied_log_ratio_correction"]
    )
    home_effect = float(home_modifier.get("log_ratio_effect") or 0.0)
    away_effect = float(away_modifier.get("log_ratio_effect") or 0.0)
    total_correction = _clip(
        league_correction + home_effect + away_effect,
        float(config["venue"]["maximum_absolute_total_log_ratio_correction"]),
    )
    before = prediction["predicted_xg"]
    home_xg = float(before["home"]) * math.exp(total_correction / 2.0)
    away_xg = float(before["away"]) * math.exp(-total_correction / 2.0)
    simulation = config["simulation"]
    result = _weighted_simulation(
        home_xg,
        away_xg,
        draw_logit_correction=float(
            artifact["draw_calibration"]["applied_logit_correction"]
        ),
        draws=int(simulation["draws"]),
        seed=int(simulation["seed"]) + int(fixture["match_id"]),
        totals_lines=list(simulation["totals_lines"]),
    )
    probabilities = result["probabilities"]
    side_key = (
        "home_win"
        if probabilities["home_win"] >= probabilities["away_win"]
        else "away_win"
    )
    side_probability = float(probabilities[side_key])
    draw_probability = float(probabilities["draw"])
    draw_zone = bool(
        abs(side_probability - draw_probability)
        <= float(config["draw"]["draw_zone_max_probability_gap"])
        and side_probability
        <= float(config["draw"]["draw_zone_max_side_probability"])
    )
    leader = max(
        ("home_win", "draw", "away_win"), key=lambda key: probabilities[key]
    )
    return {
        "calibration_version": CALIBRATION_VERSION,
        "status": "shadow_only",
        "fixture": dict(fixture),
        "predicted_xg_before_calibration": dict(before),
        "predicted_xg": {
            "home": round(home_xg, 6),
            "away": round(away_xg, 6),
            "total": round(home_xg + away_xg, 6),
        },
        "probabilities_before_calibration": dict(prediction["probabilities"]),
        "probabilities": probabilities,
        "most_likely_scorelines": result["most_likely_scorelines"],
        "calibration_read": {
            "league_log_ratio_correction": round(league_correction, 6),
            "home_team_log_ratio_effect": round(home_effect, 6),
            "away_team_log_ratio_effect": round(away_effect, 6),
            "total_log_ratio_correction": round(total_correction, 6),
            "draw_logit_correction": artifact["draw_calibration"][
                "applied_logit_correction"
            ],
            "raw_draw_probability_after_venue": result["raw_draw_probability"],
            "calibrated_draw_probability": result[
                "calibrated_draw_probability"
            ],
            "draw_zone": draw_zone,
            "probability_leader": leader,
            "side_leader": side_key,
            "risk_gate": "pass_draw_zone" if draw_zone else "shadow_evaluation",
        },
        "decision_boundaries": {
            "base_60_30_10_changed": False,
            "player_alpha_changed": False,
            "context_coefficient_changed": False,
            "frozen_predictions_changed": False,
            "probability_validated": artifact["decision_boundaries"][
                "probability_validated"
            ],
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": sorted(
            set(
                list(artifact.get("quality_flags") or [])
                + ["fixture_calibration_shadow_only"]
            )
        ),
    }
