"""Chronological shadow predictions built on Fixture State intelligence.

This module owns three deliberately separate steps:

1. fit comparable component scales from an earlier dated snapshot;
2. fit a goal-adjustment coefficient from later observed FotMob xG;
3. simulate future fixtures without claiming market or capital readiness.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from datetime import date
from typing import Any, Iterable


COMPONENTS = (
    "club_form",
    "player_quality_lineup",
    "historical_residual",
)


def _day(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {value}") from exc


def _mean_absolute_error(pairs: Iterable[tuple[float, float]]) -> float | None:
    values = [abs(prediction - observed) for prediction, observed in pairs]
    return statistics.mean(values) if values else None


def fit_component_scale_artifact(
    states: Iterable[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Fit frozen component SDs without reading match outcomes."""

    rows = list(states)
    if not rows:
        raise ValueError("Component scale fitting requires Fixture State rows")
    dates = {str(row.get("as_of")) for row in rows}
    if len(dates) != 1:
        raise ValueError("Component scale fitting requires one snapshot as-of date")
    versions = {str(row.get("fixture_state_version")) for row in rows}
    if len(versions) != 1:
        raise ValueError("Component scale fitting requires one Fixture State version")
    eligible = [
        row
        for row in rows
        if row.get("decision_boundaries", {}).get(
            "raw_components_ready_for_scale_fitting"
        )
    ]
    minimum_sides = int(config["component_scaling"]["minimum_training_fixture_sides"])
    fixture_sides = len(eligible) * 2
    if fixture_sides < minimum_sides:
        raise ValueError(
            f"Component scale fitting requires at least {minimum_sides} fixture sides; "
            f"found {fixture_sides}"
        )

    scales: dict[str, float] = {}
    for component in COMPONENTS:
        values = [
            float(row[side]["components"][component]["effective_signal_z"])
            for row in eligible
            for side in ("home", "away")
        ]
        spread = statistics.stdev(values)
        if spread <= 0:
            raise ValueError(f"Component {component} has no usable historical spread")
        scales[component] = round(spread, 9)

    validation_sides = int(
        config["component_scaling"].get(
            "minimum_validation_fixture_sides", minimum_sides
        )
    )

    return {
        "version": config["component_scaling"]["artifact_version"],
        "method": config["component_scaling"]["method"],
        "trained_through": next(iter(dates)),
        "training_snapshot_count": 1,
        "training_fixture_count": len(eligible),
        "training_fixture_sides": fixture_sides,
        "source_fixture_state_version": next(iter(versions)),
        "outcomes_used": False,
        "scales": scales,
        "decision_boundaries": {
            "shadow_scaling_ready": True,
            "scale_validated": fixture_sides >= validation_sides,
        },
        "quality_flags": (
            ["small_component_scale_sample"]
            if fixture_sides < validation_sides
            else []
        ),
    }


def scaled_fixture_signals(
    state: dict[str, Any],
    scale_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Apply frozen scales and the state's declared component weights."""

    state_day = _day(state.get("as_of"), "Fixture State as-of")
    scale_day = _day(scale_artifact.get("trained_through"), "scale training cutoff")
    if scale_day >= state_day:
        raise ValueError("Component scales must predate the prediction snapshot")
    supplied = set((scale_artifact.get("scales") or {}).keys())
    if supplied != set(COMPONENTS):
        raise ValueError("Component scale artifact is incomplete")
    if not state.get("decision_boundaries", {}).get(
        "raw_components_ready_for_scale_fitting"
    ):
        raise ValueError("Fixture State raw components are incomplete")
    weights = state.get("component_weights") or {}
    if set(weights) != set(COMPONENTS):
        raise ValueError("Fixture State weights are incomplete")

    output: dict[str, Any] = {}
    for side in ("home", "away"):
        normalized = {
            component: float(
                state[side]["components"][component]["effective_signal_z"]
            )
            / float(scale_artifact["scales"][component])
            for component in COMPONENTS
        }
        contributions = {
            component: float(weights[component]) * normalized[component]
            for component in COMPONENTS
        }
        output[side] = {
            "normalized_components_z": {
                key: round(value, 6) for key, value in normalized.items()
            },
            "weighted_contributions_z": {
                key: round(value, 6) for key, value in contributions.items()
            },
            "fixture_signal_z": round(sum(contributions.values()), 6),
        }
    return output


def fit_goal_model_artifact(
    states: Iterable[dict[str, Any]],
    actuals: Iterable[dict[str, Any]],
    scale_artifact: dict[str, Any],
    config: dict[str, Any],
    *,
    trained_through: str,
) -> dict[str, Any]:
    """Fit one conservative log-link coefficient against observed FotMob xG."""

    state_by_match = {
        int(row["fixture"]["match_id"]): row for row in states
    }
    actual_rows = list(actuals)
    cutoff = _day(trained_through, "goal-model training cutoff")
    scale_cutoff = _day(
        scale_artifact.get("trained_through"), "component-scale training cutoff"
    )
    if scale_cutoff >= cutoff:
        raise ValueError("Goal calibration must occur after component-scale training")

    grouped_observations: list[list[tuple[float, float, float, float]]] = []
    used_match_ids: list[int] = []
    used_snapshot_dates: set[str] = set()
    xg_floor = float(config["goal_model"]["observed_xg_floor"])
    for actual in actual_rows:
        match_id = int(actual["match_id"])
        state = state_by_match.get(match_id)
        if state is None:
            continue
        snapshot_day = _day(state.get("as_of"), "training Fixture State as-of")
        kickoff_day = _day(
            state.get("fixture", {}).get("kickoff_utc"), "training fixture kickoff"
        )
        if snapshot_day >= kickoff_day:
            raise ValueError("Goal-model training state must predate fixture kickoff")
        if kickoff_day > cutoff:
            raise ValueError("Goal-model training outcome occurs after its cutoff")
        used_snapshot_dates.add(snapshot_day.isoformat())
        scaled = scaled_fixture_signals(state, scale_artifact)
        match_observations: list[tuple[float, float, float, float]] = []
        for side in ("home", "away"):
            observed = actual.get(f"{side}_xg")
            baseline = state["goal_model_handoff"]["competition_baseline"].get(
                f"{side}_xg"
            )
            if observed is None or baseline is None or float(baseline) <= 0:
                continue
            observed_value = float(observed)
            baseline_value = float(baseline)
            if not math.isfinite(observed_value) or observed_value < 0:
                raise ValueError("Observed xG must be finite and non-negative")
            if not math.isfinite(baseline_value):
                raise ValueError("Competition baseline xG must be finite")
            observed_value = max(xg_floor, observed_value)
            target = math.log(observed_value / baseline_value)
            match_observations.append(
                (
                    float(scaled[side]["fixture_signal_z"]),
                    target,
                    observed_value,
                    baseline_value,
                )
            )
        if len(match_observations) == 2:
            grouped_observations.append(match_observations)
            used_match_ids.append(match_id)

    minimum_matches = int(config["goal_model"]["minimum_shadow_training_matches"])
    if len(grouped_observations) < minimum_matches:
        raise ValueError(
            f"Goal calibration requires at least {minimum_matches} complete matches"
        )
    observations = [item for group in grouped_observations for item in group]
    numerator = sum(signal * target for signal, target, _, _ in observations)
    denominator = sum(signal * signal for signal, _, _, _ in observations)
    if denominator <= 0:
        raise ValueError("Goal calibration signals have no usable variance")
    ridge = float(config["goal_model"]["ridge_lambda"])
    raw_coefficient = numerator / denominator
    point_coefficient = numerator / (denominator + ridge)

    bootstrap = config["goal_model"]["bootstrap"]
    bootstrap_samples = int(bootstrap["samples"])
    rng = random.Random(int(bootstrap["seed"]))
    bootstrap_coefficients: list[float] = []
    for _ in range(bootstrap_samples):
        sampled = [rng.choice(grouped_observations) for _ in grouped_observations]
        sampled_rows = [item for group in sampled for item in group]
        sample_numerator = sum(
            signal * target for signal, target, _, _ in sampled_rows
        )
        sample_denominator = sum(
            signal * signal for signal, _, _, _ in sampled_rows
        )
        bootstrap_coefficients.append(
            sample_numerator / (sample_denominator + ridge)
        )
    bootstrap_coefficients.sort()

    def percentile(fraction: float) -> float:
        index = min(
            len(bootstrap_coefficients) - 1,
            max(0, round(fraction * (len(bootstrap_coefficients) - 1))),
        )
        return bootstrap_coefficients[index]

    lower_coefficient = percentile(0.025)
    upper_coefficient = percentile(0.975)
    validation_minimum = int(
        config["goal_model"]["minimum_validation_matches"]
    )
    probability_validated = len(grouped_observations) >= validation_minimum
    coefficient_policy = str(
        config["goal_model"].get(
            "small_sample_coefficient_policy", "point_estimate"
        )
    )
    if probability_validated or coefficient_policy == "point_estimate":
        applied_coefficient = point_coefficient
    elif coefficient_policy == "bootstrap_95_bound_closest_to_zero":
        if lower_coefficient > 0:
            applied_coefficient = lower_coefficient
        elif upper_coefficient < 0:
            applied_coefficient = upper_coefficient
        else:
            applied_coefficient = 0.0
    else:
        raise ValueError(f"Unknown small-sample coefficient policy: {coefficient_policy}")

    baseline_pairs = [
        (baseline, observed) for _, _, observed, baseline in observations
    ]
    fitted_pairs = [
        (baseline * math.exp(point_coefficient * signal), observed)
        for signal, _, observed, baseline in observations
    ]
    applied_pairs = [
        (baseline * math.exp(applied_coefficient * signal), observed)
        for signal, _, observed, baseline in observations
    ]
    return {
        "version": config["goal_model"]["artifact_version"],
        "method": config["goal_model"]["method"],
        "target": config["goal_model"]["target"],
        "link": "competition_xg_baseline * exp(coefficient * fixture_signal_z)",
        "trained_through": cutoff.isoformat(),
        "training_fixture_state_as_of_dates": sorted(used_snapshot_dates),
        "component_scale_artifact_version": scale_artifact["version"],
        "training_matches": len(grouped_observations),
        "training_sides": len(observations),
        "training_match_ids": sorted(used_match_ids),
        "ridge_lambda": ridge,
        "raw_coefficient": round(raw_coefficient, 9),
        "point_coefficient": round(point_coefficient, 9),
        "coefficient": round(applied_coefficient, 9),
        "coefficient_policy": (
            "point_estimate"
            if probability_validated
            else coefficient_policy
        ),
        "bootstrap_95_interval": {
            "lower": round(lower_coefficient, 9),
            "upper": round(upper_coefficient, 9),
            "samples": bootstrap_samples,
            "resampling_unit": "match",
        },
        "training_metrics": {
            "competition_baseline_xg_mae": round(
                float(_mean_absolute_error(baseline_pairs)), 6
            ),
            "fitted_xg_mae": round(float(_mean_absolute_error(fitted_pairs)), 6),
            "applied_conservative_xg_mae": round(
                float(_mean_absolute_error(applied_pairs)), 6
            ),
        },
        "decision_boundaries": {
            "shadow_prediction_ready": len(grouped_observations) >= minimum_matches,
            "probability_validated": probability_validated,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": [
            "small_goal_calibration_sample"
        ]
        if len(grouped_observations) < validation_minimum
        else [],
    }


def _poisson_draw(rng: random.Random, expected_goals: float) -> int:
    threshold = math.exp(-expected_goals)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_fixture(
    state: dict[str, Any],
    scale_artifact: dict[str, Any],
    goal_model_artifact: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Generate one deterministic, shadow-only match probability distribution."""

    if not goal_model_artifact.get("decision_boundaries", {}).get(
        "shadow_prediction_ready"
    ):
        raise ValueError("Goal-model artifact is not shadow-prediction ready")
    if goal_model_artifact.get("component_scale_artifact_version") != (
        scale_artifact.get("version")
    ):
        raise ValueError("Goal model and component-scale artifact versions differ")
    snapshot_day = _day(state.get("as_of"), "prediction snapshot as-of")
    goal_cutoff = _day(
        goal_model_artifact.get("trained_through"), "goal-model training cutoff"
    )
    kickoff_day = _day(
        state.get("fixture", {}).get("kickoff_utc"), "prediction fixture kickoff"
    )
    if goal_cutoff > snapshot_day:
        raise ValueError("Goal model was trained after the prediction snapshot")
    if kickoff_day <= snapshot_day or kickoff_day <= goal_cutoff:
        raise ValueError("Prediction fixture must occur after all training cutoffs")

    scaled = scaled_fixture_signals(state, scale_artifact)
    coefficient = float(goal_model_artifact["coefficient"])
    if not math.isfinite(coefficient):
        raise ValueError("Goal-model coefficient must be finite")
    bounds = config["goal_model"]["predicted_xg_bounds"]
    minimum_xg = float(bounds["minimum"])
    maximum_xg = float(bounds["maximum"])
    predicted_xg: dict[str, float] = {}
    for side in ("home", "away"):
        baseline = float(
            state["goal_model_handoff"]["competition_baseline"][f"{side}_xg"]
        )
        if not math.isfinite(baseline) or baseline <= 0:
            raise ValueError("Prediction baseline xG must be finite and positive")
        value = baseline * math.exp(
            coefficient * float(scaled[side]["fixture_signal_z"])
        )
        predicted_xg[side] = max(minimum_xg, min(maximum_xg, value))

    simulation = config["simulation"]
    if simulation.get("distribution") != "independent_poisson":
        raise ValueError("Prediction Lab v0 supports independent_poisson only")
    draws = int(simulation["draws"])
    if draws <= 0:
        raise ValueError("Simulation draws must be positive")
    match_id = int(state["fixture"]["match_id"])
    seed = int(simulation["seed"]) + match_id
    rng = random.Random(seed)
    outcomes = Counter()
    scorelines = Counter()
    totals = {str(line): 0 for line in simulation["totals_lines"]}
    btts = 0
    home_goal_sum = 0
    away_goal_sum = 0
    for _ in range(draws):
        home_goals = _poisson_draw(rng, predicted_xg["home"])
        away_goals = _poisson_draw(rng, predicted_xg["away"])
        home_goal_sum += home_goals
        away_goal_sum += away_goals
        outcome = "home" if home_goals > away_goals else "away" if away_goals > home_goals else "draw"
        outcomes[outcome] += 1
        scorelines[(home_goals, away_goals)] += 1
        for line in simulation["totals_lines"]:
            if home_goals + away_goals > float(line):
                totals[str(line)] += 1
        if home_goals > 0 and away_goals > 0:
            btts += 1

    probabilities = {
        "home_win": round(outcomes["home"] / draws, 6),
        "draw": round(outcomes["draw"] / draws, 6),
        "away_win": round(outcomes["away"] / draws, 6),
        "over": {
            line: round(count / draws, 6) for line, count in totals.items()
        },
        "under": {
            line: round(1.0 - count / draws, 6)
            for line, count in totals.items()
        },
        "btts_yes": round(btts / draws, 6),
        "btts_no": round(1.0 - btts / draws, 6),
    }
    common_scorelines = [
        {
            "score": f"{home}-{away}",
            "probability": round(count / draws, 6),
        }
        for (home, away), count in scorelines.most_common(5)
    ]
    return {
        "prediction_version": config["version"],
        "status": "shadow_only",
        "as_of": state["as_of"],
        "fixture": dict(state["fixture"]),
        "artifacts": {
            "component_scales": scale_artifact["version"],
            "goal_model": goal_model_artifact["version"],
        },
        "fixture_intelligence": scaled,
        "predicted_xg": {
            "home": round(predicted_xg["home"], 6),
            "away": round(predicted_xg["away"], 6),
            "total": round(predicted_xg["home"] + predicted_xg["away"], 6),
        },
        "simulation": {
            "draws": draws,
            "distribution": simulation["distribution"],
            "seed": seed,
            "mean_simulated_goals": {
                "home": round(home_goal_sum / draws, 6),
                "away": round(away_goal_sum / draws, 6),
            },
        },
        "probabilities": probabilities,
        "most_likely_scorelines": common_scorelines,
        "decision_boundaries": {
            "shadow_prediction_ready": True,
            "probability_validated": bool(
                goal_model_artifact["decision_boundaries"]["probability_validated"]
            ),
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": sorted(
            set(
                [
                    *list(state.get("quality_flags") or []),
                    *list(scale_artifact.get("quality_flags") or []),
                    *list(goal_model_artifact.get("quality_flags") or []),
                ]
            )
        ),
    }


def build_prediction_slate(
    states: Iterable[dict[str, Any]],
    scale_artifact: dict[str, Any],
    goal_model_artifact: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    predictions = [
        simulate_fixture(state, scale_artifact, goal_model_artifact, config)
        for state in states
    ]
    return sorted(
        predictions,
        key=lambda row: (
            str(row["fixture"].get("kickoff_utc") or ""),
            int(row["fixture"]["match_id"]),
        ),
    )
