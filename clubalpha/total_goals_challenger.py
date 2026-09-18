"""Historical-xG calibration challenger for the Over/Under 2.5 market.

The locked football intelligence and its expected-goals forecast remain the
inputs. This module only asks whether historical matches with a similar total
xG environment produced three or more goals more or less often than an
independent-Poisson total would imply.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Iterable


VERSION = "clubalpha_total_goals_challenger_v1"


def poisson_over_2_5(total_xg: float) -> float:
    value = max(0.0, float(total_xg))
    return 1.0 - math.exp(-value) * (1.0 + value + value * value / 2.0)


def _day(value: str) -> datetime:
    return datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)


def _binary_scores(probability: float, outcome: bool) -> tuple[float, float]:
    p = min(1.0 - 1e-12, max(1e-12, float(probability)))
    y = 1.0 if outcome else 0.0
    return (p - y) ** 2, -math.log(p if outcome else 1.0 - p)


def historical_observations(
    rows: Iterable[dict[str, Any]],
    *,
    competition_id: int,
    before: str,
) -> list[dict[str, Any]]:
    """Return one leakage-safe row per completed match."""

    observations = []
    seen = set()
    for row in rows:
        match_id = int(row.get("match_id") or -1)
        if (
            match_id in seen
            or int(row.get("competition_id") or -1) != int(competition_id)
            or row.get("venue") != "home"
            or str(row.get("kickoff_utc") or "")[:10] >= before
        ):
            continue
        values = (
            row.get("expected_goals_for"),
            row.get("expected_goals_against"),
            row.get("goals_for"),
            row.get("goals_against"),
        )
        if any(value is None for value in values):
            continue
        seen.add(match_id)
        total_xg = float(values[0]) + float(values[1])
        total_goals = int(float(values[2]) + float(values[3]))
        observations.append(
            {
                "match_id": match_id,
                "kickoff_utc": row["kickoff_utc"],
                "season": row.get("season"),
                "total_xg": total_xg,
                "over_2_5": total_goals > 2,
            }
        )
    return sorted(observations, key=lambda row: (row["kickoff_utc"], row["match_id"]))


def _pava(values: list[float], weights: list[float]) -> list[float]:
    blocks: list[dict[str, Any]] = []
    for index, (value, weight) in enumerate(zip(values, weights)):
        blocks.append(
            {"start": index, "end": index, "weight": weight, "value": value}
        )
        while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
            right = blocks.pop()
            left = blocks.pop()
            combined_weight = left["weight"] + right["weight"]
            blocks.append(
                {
                    "start": left["start"],
                    "end": right["end"],
                    "weight": combined_weight,
                    "value": (
                        left["value"] * left["weight"]
                        + right["value"] * right["weight"]
                    )
                    / combined_weight,
                }
            )
    output = [0.0] * len(values)
    for block in blocks:
        for index in range(block["start"], block["end"] + 1):
            output[index] = block["value"]
    return output


def _grid_points(config: dict[str, Any]) -> list[float]:
    grid = config["grid"]
    minimum = float(grid["minimum_total_xg"])
    maximum = float(grid["maximum_total_xg"])
    step = float(grid["step"])
    count = int(round((maximum - minimum) / step))
    return [round(minimum + step * index, 6) for index in range(count + 1)]


def fit_probability_grid(
    observations: list[dict[str, Any]],
    *,
    bandwidth: float,
    prior_strength: float,
    half_life_days: float,
    cutoff: str,
    config: dict[str, Any],
) -> list[dict[str, float]]:
    points = _grid_points(config)
    cutoff_day = _day(cutoff)
    probabilities = []
    evidence = []
    for point in points:
        weighted_events = 0.0
        weighted_matches = 0.0
        for row in observations:
            distance = (float(row["total_xg"]) - point) / bandwidth
            kernel = math.exp(-0.5 * distance * distance)
            age = max(0, (cutoff_day - _day(row["kickoff_utc"])).days)
            recency = 0.5 ** (age / half_life_days)
            weight = kernel * recency
            weighted_matches += weight
            weighted_events += weight * float(row["over_2_5"])
        prior_probability = poisson_over_2_5(point)
        denominator = weighted_matches + prior_strength
        probabilities.append(
            (weighted_events + prior_strength * prior_probability) / denominator
        )
        evidence.append(denominator)
    monotone = _pava(probabilities, evidence)
    return [
        {
            "total_xg": point,
            "over_2_5": round(probability, 8),
            "local_weighted_matches": round(max(0.0, weight - prior_strength), 4),
        }
        for point, probability, weight in zip(points, monotone, evidence)
    ]


def probability_from_grid(total_xg: float, grid: list[dict[str, Any]]) -> float:
    value = float(total_xg)
    if value <= float(grid[0]["total_xg"]):
        return float(grid[0]["over_2_5"])
    if value >= float(grid[-1]["total_xg"]):
        return float(grid[-1]["over_2_5"])
    for left, right in zip(grid, grid[1:]):
        low = float(left["total_xg"])
        high = float(right["total_xg"])
        if low <= value <= high:
            share = (value - low) / (high - low)
            return float(left["over_2_5"]) + share * (
                float(right["over_2_5"]) - float(left["over_2_5"])
            )
    raise ValueError("total-xG calibration grid is not ordered")


def _score_grid(
    grid: list[dict[str, Any]], observations: list[dict[str, Any]]
) -> dict[str, float]:
    challenger = []
    poisson = []
    for row in observations:
        outcome = bool(row["over_2_5"])
        challenger.append(
            _binary_scores(probability_from_grid(row["total_xg"], grid), outcome)
        )
        poisson.append(_binary_scores(poisson_over_2_5(row["total_xg"]), outcome))
    return {
        "matches": len(observations),
        "challenger_brier": sum(row[0] for row in challenger) / len(challenger),
        "challenger_log_loss": sum(row[1] for row in challenger) / len(challenger),
        "poisson_brier": sum(row[0] for row in poisson) / len(poisson),
        "poisson_log_loss": sum(row[1] for row in poisson) / len(poisson),
    }


def fit_competition_artifact(
    observations: list[dict[str, Any]],
    *,
    key: str,
    competition_id: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    selection = config["selection"]
    seasons = sorted(
        {str(row["season"]) for row in observations},
        key=lambda season: min(
            row["kickoff_utc"] for row in observations if str(row["season"]) == season
        ),
    )
    minimum_seasons = int(selection["minimum_training_seasons"])
    folds = seasons[minimum_seasons:]
    candidates = []
    for bandwidth in selection["bandwidth_candidates"]:
        for prior_strength in selection["poisson_prior_strength_candidates"]:
            fold_scores = []
            for validation_season in folds:
                validation = [
                    row for row in observations if str(row["season"]) == validation_season
                ]
                cutoff = min(row["kickoff_utc"] for row in validation)[:10]
                training = [row for row in observations if row["kickoff_utc"][:10] < cutoff]
                if (
                    len(training) < int(selection["minimum_training_matches"])
                    or len(validation) < int(selection["minimum_validation_matches"])
                ):
                    continue
                grid = fit_probability_grid(
                    training,
                    bandwidth=float(bandwidth),
                    prior_strength=float(prior_strength),
                    half_life_days=float(selection["recency_half_life_days"]),
                    cutoff=cutoff,
                    config=config,
                )
                fold_scores.append(_score_grid(grid, validation))
            if not fold_scores:
                continue
            matches = sum(row["matches"] for row in fold_scores)
            summary = {
                "bandwidth": float(bandwidth),
                "poisson_prior_strength": float(prior_strength),
                "validation_matches": matches,
            }
            for metric in (
                "challenger_brier",
                "challenger_log_loss",
                "poisson_brier",
                "poisson_log_loss",
            ):
                summary[metric] = sum(
                    row[metric] * row["matches"] for row in fold_scores
                ) / matches
            candidates.append(summary)
    if not candidates:
        raise ValueError(f"{key} has no eligible chronological validation folds")
    selected = min(
        candidates,
        key=lambda row: (row["challenger_log_loss"], row["challenger_brier"]),
    )
    final_grid = fit_probability_grid(
        observations,
        bandwidth=selected["bandwidth"],
        prior_strength=selected["poisson_prior_strength"],
        half_life_days=float(selection["recency_half_life_days"]),
        cutoff=config["training_cutoff"],
        config=config,
    )
    return {
        "key": key,
        "competition_id": competition_id,
        "training_matches": len(observations),
        "training_seasons": seasons,
        "selected_parameters": {
            "bandwidth": selected["bandwidth"],
            "poisson_prior_strength": selected["poisson_prior_strength"],
            "recency_half_life_days": float(selection["recency_half_life_days"]),
        },
        "chronological_validation": {
            **{key: round(value, 8) if isinstance(value, float) else value for key, value in selected.items()},
            "brier_improvement": round(
                selected["poisson_brier"] - selected["challenger_brier"], 8
            ),
            "log_loss_improvement": round(
                selected["poisson_log_loss"] - selected["challenger_log_loss"], 8
            ),
        },
        "probability_grid": final_grid,
    }


def apply_challenger(total_xg: float, artifact: dict[str, Any], key: str) -> float:
    competitions = {row["key"]: row for row in artifact["competitions"]}
    if key not in competitions:
        raise ValueError(f"total-goals challenger has no competition {key}")
    return probability_from_grid(total_xg, competitions[key]["probability_grid"])


def evaluate_probabilities(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    output: dict[str, Any] = {"matches": len(materialized)}
    for key in ("baseline", "challenger"):
        scores = [
            _binary_scores(float(row[f"{key}_probability"]), bool(row["over_2_5"]))
            for row in materialized
        ]
        output[key] = {
            "brier": round(sum(row[0] for row in scores) / len(scores), 8),
            "log_loss": round(sum(row[1] for row in scores) / len(scores), 8),
            "direction_accuracy": round(
                sum(
                    (float(row[f"{key}_probability"]) >= 0.5)
                    == bool(row["over_2_5"])
                    for row in materialized
                )
                / len(materialized),
                8,
            ),
        }
    output["improvement_positive_is_better"] = {
        "brier": round(output["baseline"]["brier"] - output["challenger"]["brier"], 8),
        "log_loss": round(
            output["baseline"]["log_loss"] - output["challenger"]["log_loss"], 8
        ),
        "direction_accuracy": round(
            output["challenger"]["direction_accuracy"]
            - output["baseline"]["direction_accuracy"],
            8,
        ),
    }
    return output
