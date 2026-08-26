"""Continuous, opponent-specific context applied after the locked base model.

Archetype labels are explanatory only. The mathematics uses directional route
expression, opponent exposure, projected-XI execution, and evidence quality.
The v1 coefficient is an explicitly unvalidated shadow sensitivity.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Any

from clubalpha.style_matchup import evaluate_style_matchup


def _softmax(values: dict[str, float], temperature: float) -> dict[str, float]:
    if temperature <= 0:
        raise ValueError("Route preference temperature must be positive")
    maximum = max(values.values())
    exponentials = {
        key: math.exp(temperature * (value - maximum))
        for key, value in values.items()
    }
    total = sum(exponentials.values())
    return {key: value / total for key, value in exponentials.items()}


def _xi_confidence(profile: dict[str, Any], config: dict[str, Any]) -> float:
    label = str((profile.get("projected_xi") or {}).get("grade_confidence") or "low")
    return float(config["projected_xi_confidence"].get(label, 0.0))


def directional_context(
    attacker: dict[str, Any],
    defender: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Return a smooth scoring-context signal for one attack direction."""

    matchup = evaluate_style_matchup(attacker, defender)
    route_expression = {
        str(row["key"]): float(row["route_expression_z"])
        for row in matchup["routes"]
    }
    preferences = _softmax(
        route_expression, float(config["route_preference_temperature"])
    )
    evidence_values = config["channel_evidence_reliability"]
    saturation = float(config["signal_saturation_z"])
    if saturation <= 0:
        raise ValueError("Context signal saturation must be positive")

    missing_pressing = "pressing_evidence_missing" in set(
        list(attacker.get("quality_flags") or [])
        + list(defender.get("quality_flags") or [])
    )
    weighted_signal = 0.0
    effective_weight = 0.0
    channel_rows = []
    for row in matchup["routes"]:
        key = str(row["key"])
        evidence_reliability = float(evidence_values[row["evidence_tier"]])
        if key == "high_press" and missing_pressing:
            evidence_reliability = 0.0
        preference = preferences[key]
        weight = preference * evidence_reliability
        bounded_signal = math.tanh(float(row["challenger_signal_z"]) / saturation)
        weighted_signal += weight * bounded_signal
        effective_weight += weight
        channel_rows.append(
            {
                **row,
                "route_preference": round(preference, 6),
                "evidence_reliability": round(evidence_reliability, 6),
                "effective_weight": round(weight, 6),
                "bounded_signal": round(bounded_signal, 6),
            }
        )

    signal = weighted_signal / effective_weight if effective_weight > 0 else 0.0
    channel_reliability = sum(
        preferences[row["key"]] * float(row["evidence_reliability"])
        for row in channel_rows
    )
    xi_reliability = math.sqrt(
        _xi_confidence(attacker, config) * _xi_confidence(defender, config)
    )
    reliability = max(0.0, min(1.0, channel_reliability * xi_reliability))
    log_adjustment = (
        float(config["maximum_absolute_log_xg_adjustment"])
        * signal
        * reliability
    )
    channel_rows.sort(key=lambda row: row["effective_weight"], reverse=True)
    return {
        "attacker": attacker["team"],
        "defender": defender["team"],
        "attacker_archetype": attacker["archetype"],
        "defender_archetype": defender["archetype"],
        "continuous_signal": round(signal, 6),
        "channel_reliability": round(channel_reliability, 6),
        "projected_xi_reliability": round(xi_reliability, 6),
        "combined_reliability": round(reliability, 6),
        "log_xg_adjustment": round(log_adjustment, 6),
        "xg_multiplier": round(math.exp(log_adjustment), 6),
        "preferred_route": channel_rows[0],
        "channels": channel_rows,
        "archetype_label_used_in_math": False,
    }


def _poisson_draw(rng: random.Random, expected_goals: float) -> int:
    threshold = math.exp(-expected_goals)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_expected_goals(
    home_xg: float,
    away_xg: float,
    *,
    draws: int,
    totals_lines: list[float],
    seed: int,
) -> dict[str, Any]:
    """Simulate one coherent 1X2/totals/BTTS distribution from adjusted xG."""

    if home_xg <= 0 or away_xg <= 0 or draws <= 0:
        raise ValueError("Expected goals and simulation draws must be positive")
    rng = random.Random(seed)
    outcomes: Counter[str] = Counter()
    scorelines: Counter[tuple[int, int]] = Counter()
    totals = {str(line): 0 for line in totals_lines}
    btts = 0
    for _ in range(draws):
        home_goals = _poisson_draw(rng, home_xg)
        away_goals = _poisson_draw(rng, away_xg)
        outcome = (
            "home"
            if home_goals > away_goals
            else "away" if away_goals > home_goals else "draw"
        )
        outcomes[outcome] += 1
        scorelines[(home_goals, away_goals)] += 1
        for line in totals_lines:
            if home_goals + away_goals > line:
                totals[str(line)] += 1
        if home_goals > 0 and away_goals > 0:
            btts += 1
    probabilities = {
        "home_win": round(outcomes["home"] / draws, 6),
        "draw": round(outcomes["draw"] / draws, 6),
        "away_win": round(outcomes["away"] / draws, 6),
        "over": {line: round(count / draws, 6) for line, count in totals.items()},
        "under": {
            line: round(1.0 - count / draws, 6)
            for line, count in totals.items()
        },
        "btts_yes": round(btts / draws, 6),
        "btts_no": round(1.0 - btts / draws, 6),
    }
    return {
        "draws": draws,
        "seed": seed,
        "probabilities": probabilities,
        "most_likely_scorelines": [
            {"score": f"{home}-{away}", "probability": round(count / draws, 6)}
            for (home, away), count in scorelines.most_common(5)
        ],
    }


def contextualize_prediction(
    baseline: dict[str, Any],
    home_profile: dict[str, Any],
    away_profile: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Apply directional context to one immutable baseline prediction."""

    fixture = baseline["fixture"]
    if fixture["home_team"] != home_profile["team"]:
        raise ValueError("Home profile does not match prediction fixture")
    if fixture["away_team"] != away_profile["team"]:
        raise ValueError("Away profile does not match prediction fixture")
    home_context = directional_context(home_profile, away_profile, config)
    away_context = directional_context(away_profile, home_profile, config)
    base_home_xg = float(baseline["predicted_xg"]["home"])
    base_away_xg = float(baseline["predicted_xg"]["away"])
    home_xg = base_home_xg * float(home_context["xg_multiplier"])
    away_xg = base_away_xg * float(away_context["xg_multiplier"])
    simulation_config = config["simulation"]
    simulation = simulate_expected_goals(
        home_xg,
        away_xg,
        draws=int(simulation_config["draws"]),
        totals_lines=[float(line) for line in simulation_config["totals_lines"]],
        seed=int(baseline["simulation"]["seed"]),
    )
    contextual_probabilities = simulation["probabilities"]
    baseline_probabilities = baseline["probabilities"]
    probability_delta = {
        key: round(
            float(contextual_probabilities[key]) - float(baseline_probabilities[key]),
            6,
        )
        for key in ("home_win", "draw", "away_win", "btts_yes")
    }
    for line in simulation_config["totals_lines"]:
        label = str(line)
        probability_delta[f"over_{label}"] = round(
            float(contextual_probabilities["over"][label])
            - float(baseline_probabilities["over"][label]),
            6,
        )

    favorite_side = (
        "home"
        if float(baseline_probabilities["home_win"])
        >= float(baseline_probabilities["away_win"])
        else "away"
    )
    favorite_key = f"{favorite_side}_win"
    favorite_delta = probability_delta[favorite_key]
    probability_threshold = float(
        config["display_thresholds"]["probability_change"]
    )
    verdict = (
        "baseline_reinforced"
        if favorite_delta >= probability_threshold
        else "baseline_fragile"
        if favorite_delta <= -probability_threshold
        else "baseline_supported"
        if favorite_delta > 0
        else "no_clear_contextual_edge"
    )
    base_total = base_home_xg + base_away_xg
    contextual_total = home_xg + away_xg
    total_change = contextual_total - base_total
    total_threshold = float(config["display_thresholds"]["total_xg_change"])
    goal_environment = (
        "expansive"
        if total_change >= total_threshold
        else "suppressed" if total_change <= -total_threshold else "neutral"
    )
    return {
        "contextual_interaction_version": config["version"],
        "status": config["status"],
        "fixture": dict(fixture),
        "baseline": {
            "prediction_version": baseline["prediction_version"],
            "predicted_xg": dict(baseline["predicted_xg"]),
            "probabilities": dict(baseline_probabilities),
        },
        "directional_context": {
            "home_attack": home_context,
            "away_attack": away_context,
        },
        "contextual": {
            "predicted_xg": {
                "home": round(home_xg, 6),
                "away": round(away_xg, 6),
                "total": round(contextual_total, 6),
            },
            "probabilities": contextual_probabilities,
            "most_likely_scorelines": simulation["most_likely_scorelines"],
        },
        "change": {
            "predicted_xg": {
                "home": round(home_xg - base_home_xg, 6),
                "away": round(away_xg - base_away_xg, 6),
                "total": round(total_change, 6),
            },
            "probabilities": probability_delta,
        },
        "context_read": {
            "base_favorite_side": favorite_side,
            "base_favorite": fixture[f"{favorite_side}_team"],
            "favorite_probability_delta": favorite_delta,
            "verdict": verdict,
            "goal_environment": goal_environment,
        },
        "simulation": {
            "draws": simulation["draws"],
            "seed": simulation["seed"],
            "same_deterministic_seed_as_baseline": True,
            "common_random_numbers_with_baseline": False,
        },
        "decision_boundaries": dict(config["decision_boundaries"]),
        "quality_flags": sorted(
            set(
                [
                    "context_coefficient_not_learned_from_residuals",
                    "context_shadow_sensitivity_only",
                    *list(home_profile.get("quality_flags") or []),
                    *list(away_profile.get("quality_flags") or []),
                ]
            )
        ),
    }
