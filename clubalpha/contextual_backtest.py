"""Evaluation helpers for the frozen Contextual Interaction shadow slate.

The evaluator keeps three questions separate:

* did the forecast assign probability to the result that actually occurred?
* did its expected-goals estimate match the chances the teams created?
* did the frozen projected XI resemble the declared starting XI?

That separation prevents a low-probability finishing outcome from being treated
as proof that the underlying football read was wrong.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable


OUTCOMES = ("home_win", "draw", "away_win")
RESULT_VERSION = "clubalpha_contextual_result_v1"
PROCESS_DRAW_XG_GAP = 0.25


def _mean(values: Iterable[float]) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _distribution(values: Iterable[float]) -> dict[str, float]:
    rows = list(values)
    return {
        "minimum": _rounded(min(rows)),
        "maximum": _rounded(max(rows)),
        "mean": _rounded(_mean(rows)),
        "population_sd": _rounded(statistics.pstdev(rows)),
    }


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _prediction_index(
    predictions: Iterable[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(predictions, start=1):
        try:
            match_id = int(row["fixture"]["match_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"contextual prediction row {index} has no valid match id"
            ) from exc
        if match_id in output:
            raise ValueError("contextual predictions contain duplicate match ids")
        output[match_id] = row
    if not output:
        raise ValueError("contextual prediction archive is empty")
    return output


def validate_contextual_results(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Validate an append-only observed-result stream against frozen matches."""

    prediction_by_id = _prediction_index(predictions)
    rows = list(results)
    seen: set[int] = set()
    required = (
        "result_version",
        "recorded_at_utc",
        "match_id",
        "season",
        "kickoff_utc",
        "home_team_id",
        "home_team",
        "away_team_id",
        "away_team",
        "final_home_goals",
        "final_away_goals",
        "outcome",
        "actual_xg",
        "home_stats",
        "away_stats",
        "home_lineup",
        "away_lineup",
        "source",
        "source_match_id",
    )
    for index, row in enumerate(rows, start=1):
        missing = [field for field in required if row.get(field) is None]
        if missing:
            raise ValueError(f"contextual result row {index} is missing: {missing}")
        try:
            match_id = int(row["match_id"])
            home_id = int(row["home_team_id"])
            away_id = int(row["away_team_id"])
            if isinstance(row["final_home_goals"], bool) or isinstance(
                row["final_away_goals"], bool
            ):
                raise ValueError
            home_goals = int(row["final_home_goals"])
            away_goals = int(row["final_away_goals"])
            if home_goals != row["final_home_goals"] or away_goals != row[
                "final_away_goals"
            ]:
                raise ValueError
            home_xg = float(row["actual_xg"]["home"])
            away_xg = float(row["actual_xg"]["away"])
            total_xg = float(row["actual_xg"]["total"])
            kickoff = _timestamp(row["kickoff_utc"])
            recorded = _timestamp(row["recorded_at_utc"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"contextual result row {index} contains invalid field types"
            ) from exc
        if row["result_version"] != RESULT_VERSION:
            raise ValueError(f"contextual result row {index} has the wrong version")
        if match_id not in prediction_by_id:
            raise ValueError(
                f"contextual result row {index} does not join a frozen match"
            )
        if match_id in seen:
            raise ValueError("contextual result stream contains duplicate match ids")
        seen.add(match_id)
        fixture = prediction_by_id[match_id]["fixture"]
        if home_id != int(fixture["home_team_id"]) or away_id != int(
            fixture["away_team_id"]
        ):
            raise ValueError(f"contextual result row {index} reverses the fixture")
        if row["home_team"] != fixture["home_team"] or row["away_team"] != fixture[
            "away_team"
        ]:
            raise ValueError(f"contextual result row {index} changes team identity")
        if kickoff != _timestamp(fixture["kickoff_utc"]):
            raise ValueError(f"contextual result row {index} changes kickoff time")
        if home_goals < 0 or away_goals < 0 or home_xg < 0 or away_xg < 0:
            raise ValueError(f"contextual result row {index} contains negative values")
        if not all(math.isfinite(value) for value in (home_xg, away_xg, total_xg)):
            raise ValueError(f"contextual result row {index} contains non-finite xG")
        if abs(total_xg - home_xg - away_xg) > 1e-9:
            raise ValueError(f"contextual result row {index} xG total does not reconcile")
        expected_outcome = (
            "home_win"
            if home_goals > away_goals
            else "away_win" if away_goals > home_goals else "draw"
        )
        if row["outcome"] != expected_outcome:
            raise ValueError(
                f"contextual result row {index} outcome does not match its score"
            )
        if recorded < kickoff:
            raise ValueError(
                f"contextual result row {index} was recorded before kickoff"
            )
        for side in ("home", "away"):
            starter_ids = row[f"{side}_lineup"].get("starter_ids") or []
            if len(starter_ids) != 11 or len(set(map(int, starter_ids))) != 11:
                raise ValueError(
                    f"contextual result row {index} has no exact {side} starting XI"
                )
        if not str(row["source"]).strip() or not str(row["source_match_id"]).strip():
            raise ValueError(f"contextual result row {index} has no source identity")
    return {
        "frozen_fixtures": len(prediction_by_id),
        "completed_results": len(rows),
        "pending_results": len(prediction_by_id) - len(rows),
        "unique_match_ids": len(seen),
        "complete": len(rows) == len(prediction_by_id),
    }


def _one_x_two(probabilities: dict[str, Any]) -> dict[str, float]:
    output = {key: float(probabilities[key]) for key in OUTCOMES}
    if any(value < 0 or value > 1 for value in output.values()):
        raise ValueError("1X2 probability outside [0, 1]")
    if abs(sum(output.values()) - 1.0) > 1e-6:
        raise ValueError("1X2 probabilities do not sum to one")
    return output


def _top_outcome(probabilities: dict[str, float]) -> str:
    return max(OUTCOMES, key=lambda key: probabilities[key])


def _process_outcome(home_xg: float, away_xg: float) -> str:
    if abs(home_xg - away_xg) < PROCESS_DRAW_XG_GAP:
        return "draw"
    return "home_win" if home_xg > away_xg else "away_win"


def _brier_1x2(probabilities: dict[str, float], outcome: str) -> float:
    return sum(
        (probabilities[key] - float(key == outcome)) ** 2 for key in OUTCOMES
    )


def _log_loss(probability: float) -> float:
    return -math.log(max(1e-15, min(1.0 - 1e-15, probability)))


def _binary_brier(probability: float, happened: bool) -> float:
    return (probability - float(happened)) ** 2


def _model_fixture_scores(
    model: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    predicted_xg = model["predicted_xg"]
    probabilities = _one_x_two(model["probabilities"])
    actual_xg = result["actual_xg"]
    actual_goals = (
        int(result["final_home_goals"]),
        int(result["final_away_goals"]),
    )
    xg_errors = (
        abs(float(predicted_xg["home"]) - float(actual_xg["home"])),
        abs(float(predicted_xg["away"]) - float(actual_xg["away"])),
    )
    goal_errors = (
        abs(float(predicted_xg["home"]) - actual_goals[0]),
        abs(float(predicted_xg["away"]) - actual_goals[1]),
    )
    outcome = str(result["outcome"])
    total_goals = sum(actual_goals)
    btts = all(value > 0 for value in actual_goals)
    over_2_5 = total_goals > 2.5
    over_probability = float(model["probabilities"]["over"]["2.5"])
    btts_probability = float(model["probabilities"]["btts_yes"])
    return {
        "xg_side_absolute_errors": list(xg_errors),
        "xg_side_squared_errors": [value**2 for value in xg_errors],
        "xg_total_absolute_error": abs(
            float(predicted_xg["home"])
            + float(predicted_xg["away"])
            - float(actual_xg["home"])
            - float(actual_xg["away"])
        ),
        "goal_side_absolute_errors": list(goal_errors),
        "one_x_two_brier": _brier_1x2(probabilities, outcome),
        "one_x_two_log_loss": _log_loss(probabilities[outcome]),
        "one_x_two_top_pick": _top_outcome(probabilities),
        "one_x_two_top_pick_correct": _top_outcome(probabilities) == outcome,
        "actual_outcome_probability": probabilities[outcome],
        "over_2_5_brier": _binary_brier(over_probability, over_2_5),
        "over_2_5_log_loss": _log_loss(
            over_probability if over_2_5 else 1.0 - over_probability
        ),
        "btts_brier": _binary_brier(btts_probability, btts),
        "btts_log_loss": _log_loss(
            btts_probability if btts else 1.0 - btts_probability
        ),
    }


def _model_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    scores = [row["scores"][key] for row in rows]
    side_absolute = [
        value for score in scores for value in score["xg_side_absolute_errors"]
    ]
    side_squared = [
        value for score in scores for value in score["xg_side_squared_errors"]
    ]
    goal_absolute = [
        value for score in scores for value in score["goal_side_absolute_errors"]
    ]
    return {
        "xg_side_mae": _rounded(_mean(side_absolute)),
        "xg_side_rmse": _rounded(math.sqrt(_mean(side_squared))),
        "xg_total_mae": _rounded(
            _mean(score["xg_total_absolute_error"] for score in scores)
        ),
        "goal_side_mae": _rounded(_mean(goal_absolute)),
        "one_x_two_brier": _rounded(
            _mean(score["one_x_two_brier"] for score in scores)
        ),
        "one_x_two_log_loss": _rounded(
            _mean(score["one_x_two_log_loss"] for score in scores)
        ),
        "one_x_two_top_pick_accuracy": _rounded(
            _mean(float(score["one_x_two_top_pick_correct"]) for score in scores)
        ),
        "over_2_5_brier": _rounded(
            _mean(score["over_2_5_brier"] for score in scores)
        ),
        "over_2_5_log_loss": _rounded(
            _mean(score["over_2_5_log_loss"] for score in scores)
        ),
        "btts_brier": _rounded(_mean(score["btts_brier"] for score in scores)),
        "btts_log_loss": _rounded(
            _mean(score["btts_log_loss"] for score in scores)
        ),
    }


def _lineup_summary(
    results: list[dict[str, Any]], snapshot: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not snapshot:
        return None
    clubs_by_fixture: dict[tuple[int, int], dict[str, Any]] = {}
    clubs_by_team: dict[int, dict[str, Any]] = {}
    for club in snapshot.get("clubs") or []:
        team_id = int(club["team_id"])
        clubs_by_team[team_id] = club
        match_id = (club.get("next_fixture") or {}).get("match_id")
        if match_id is not None:
            key = (int(match_id), team_id)
            if key in clubs_by_fixture:
                raise ValueError(
                    "lineup snapshot contains duplicate fixture/team projections"
                )
            clubs_by_fixture[key] = club
    rows = []
    for result in results:
        for side in ("home", "away"):
            team_id = int(result[f"{side}_team_id"])
            club = clubs_by_fixture.get((int(result["match_id"]), team_id))
            if club is None:
                club = clubs_by_team.get(team_id)
            if not club:
                continue
            projected_players = {
                int(player["player_id"]): player.get("player")
                for player in club.get("expected_xi") or []
            }
            actual_players = {
                int(player["player_id"]): player.get("player")
                for player in result[f"{side}_lineup"].get("starters") or []
            }
            projected_ids = set(projected_players)
            actual_ids = set(map(int, result[f"{side}_lineup"]["starter_ids"]))
            hits = len(projected_ids & actual_ids)
            projected_formation = club.get("formation")
            actual_formation = result[f"{side}_lineup"].get("formation")
            rows.append(
                {
                    "match_id": int(result["match_id"]),
                    "team_id": team_id,
                    "team": result[f"{side}_team"],
                    "projected_starters": len(projected_ids),
                    "xi_hits": hits,
                    "xi_hit_rate": _rounded(hits / 11.0),
                    "projected_formation": projected_formation,
                    "actual_formation": actual_formation,
                    "formation_correct": projected_formation == actual_formation,
                    "missed_projected_player_ids": sorted(projected_ids - actual_ids),
                    "unprojected_starter_ids": sorted(actual_ids - projected_ids),
                    "missed_projected_players": [
                        projected_players[player_id]
                        for player_id in sorted(projected_ids - actual_ids)
                    ],
                    "unprojected_starters": [
                        actual_players.get(player_id)
                        for player_id in sorted(actual_ids - projected_ids)
                    ],
                }
            )
    return {
        "snapshot_version": snapshot.get("snapshot_version"),
        "team_lineups": len(rows),
        "mean_xi_hits_of_11": _rounded(_mean(row["xi_hits"] for row in rows)),
        "xi_hit_rate": _rounded(_mean(row["xi_hit_rate"] for row in rows)),
        "formation_accuracy": _rounded(
            _mean(float(row["formation_correct"]) for row in rows)
        ),
        "rows": rows,
    }


def evaluate_contextual_backtest(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    *,
    lineup_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare the frozen base and contextual forecasts on observed matches."""

    prediction_rows = list(predictions)
    result_rows = list(results)
    validation = validate_contextual_results(prediction_rows, result_rows)
    if not result_rows:
        raise ValueError("no completed contextual results to score")
    prediction_by_id = _prediction_index(prediction_rows)
    fixtures = []
    route_rows: list[dict[str, Any]] = []
    for result in sorted(result_rows, key=lambda row: str(row["kickoff_utc"])):
        prediction = prediction_by_id[int(result["match_id"])]
        baseline_scores = _model_fixture_scores(prediction["baseline"], result)
        contextual_scores = _model_fixture_scores(prediction["contextual"], result)
        actual_xg = result["actual_xg"]
        process_outcome = _process_outcome(
            float(actual_xg["home"]), float(actual_xg["away"])
        )
        contextual_pick = contextual_scores["one_x_two_top_pick"]
        review_class = (
            "outcome_hit"
            if contextual_pick == result["outcome"]
            else "process_supported_outcome_variance"
            if contextual_pick == process_outcome
            else "structural_miss"
        )
        direction_rows = []
        for side in ("home", "away"):
            other = "away" if side == "home" else "home"
            direction = prediction["directional_context"][f"{side}_attack"]
            base_xg = float(prediction["baseline"]["predicted_xg"][side])
            context_xg = float(prediction["contextual"]["predicted_xg"][side])
            observed_xg = float(actual_xg[side])
            improvement = abs(base_xg - observed_xg) - abs(context_xg - observed_xg)
            movement = context_xg - base_xg
            aligned = movement * (observed_xg - base_xg) > 0
            if abs(movement) < 1e-12 or abs(observed_xg - base_xg) < 1e-12:
                aligned = None
            direction_row = {
                "side": side,
                "attacker": result[f"{side}_team"],
                "defender": result[f"{other}_team"],
                "preferred_route": direction["preferred_route"]["key"],
                "continuous_signal": direction["continuous_signal"],
                "combined_reliability": direction["combined_reliability"],
                "base_xg": _rounded(base_xg),
                "contextual_xg": _rounded(context_xg),
                "observed_xg": _rounded(observed_xg),
                "context_xg_mae_improvement": _rounded(improvement),
                "movement_aligned_with_observed_residual": aligned,
            }
            direction_rows.append(direction_row)
            route_rows.append(direction_row)
        fixtures.append(
            {
                "match_id": int(result["match_id"]),
                "kickoff_utc": result["kickoff_utc"],
                "fixture": f'{result["home_team"]} vs {result["away_team"]}',
                "score": f'{result["final_home_goals"]}-{result["final_away_goals"]}',
                "observed_xg": {
                    "home": _rounded(float(actual_xg["home"])),
                    "away": _rounded(float(actual_xg["away"])),
                    "total": _rounded(
                        float(actual_xg["home"]) + float(actual_xg["away"])
                    ),
                },
                "actual_outcome": result["outcome"],
                "xg_process_outcome": process_outcome,
                "review_class": review_class,
                "baseline_top_pick": baseline_scores["one_x_two_top_pick"],
                "contextual_top_pick": contextual_pick,
                "baseline_actual_outcome_probability": _rounded(
                    baseline_scores["actual_outcome_probability"]
                ),
                "contextual_actual_outcome_probability": _rounded(
                    contextual_scores["actual_outcome_probability"]
                ),
                "actual_outcome_probability_improvement": _rounded(
                    contextual_scores["actual_outcome_probability"]
                    - baseline_scores["actual_outcome_probability"]
                ),
                "base_predicted_xg": prediction["baseline"]["predicted_xg"],
                "contextual_predicted_xg": prediction["contextual"]["predicted_xg"],
                "xg_side_mae_improvement": _rounded(
                    _mean(baseline_scores["xg_side_absolute_errors"])
                    - _mean(contextual_scores["xg_side_absolute_errors"])
                ),
                "directional_context_review": direction_rows,
                "scores": {
                    "baseline": baseline_scores,
                    "contextual": contextual_scores,
                },
            }
        )

    baseline_summary = _model_summary(fixtures, "baseline")
    contextual_summary = _model_summary(fixtures, "contextual")
    improvement = {
        key: _rounded(baseline_summary[key] - contextual_summary[key])
        for key in baseline_summary
        if key != "one_x_two_top_pick_accuracy"
    }
    improvement["one_x_two_top_pick_accuracy"] = _rounded(
        contextual_summary["one_x_two_top_pick_accuracy"]
        - baseline_summary["one_x_two_top_pick_accuracy"]
    )

    route_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in route_rows:
        route_groups[str(row["preferred_route"])].append(row)
    route_diagnostics = []
    for route, rows in sorted(route_groups.items()):
        aligned = [
            row["movement_aligned_with_observed_residual"]
            for row in rows
            if row["movement_aligned_with_observed_residual"] is not None
        ]
        route_diagnostics.append(
            {
                "preferred_route": route,
                "attack_directions": len(rows),
                "movement_alignment_rate": _rounded(
                    _mean(float(value) for value in aligned)
                ),
                "mean_xg_mae_improvement": _rounded(
                    _mean(row["context_xg_mae_improvement"] for row in rows)
                ),
            }
        )

    known_routes = {
        "box_pressure",
        "set_pieces",
        "wide_delivery",
        "high_press",
        "direct_transition",
    }
    observed_routes = set(route_groups)
    observed_totals = [float(row["observed_xg"]["total"]) for row in fixtures]
    base_totals = [float(row["base_predicted_xg"]["total"]) for row in fixtures]
    context_totals = [
        float(row["contextual_predicted_xg"]["total"]) for row in fixtures
    ]
    xg_shifts = [
        abs(
            float(row["contextual_xg"])
            - float(row["base_xg"])
        )
        for row in route_rows
    ]

    return {
        "validation": validation,
        "sample": {
            "matches": len(fixtures),
            "team_attack_directions": len(route_rows),
            "xg_process_draw_threshold": PROCESS_DRAW_XG_GAP,
            "sufficient_to_recalibrate": False,
        },
        "metrics": {
            "baseline": baseline_summary,
            "contextual": contextual_summary,
            "holy_grail_improvement_positive_is_better": improvement,
        },
        "diagnostics": {
            "outcome_hits": sum(
                row["review_class"] == "outcome_hit" for row in fixtures
            ),
            "process_supported_outcome_variance": sum(
                row["review_class"] == "process_supported_outcome_variance"
                for row in fixtures
            ),
            "structural_misses": sum(
                row["review_class"] == "structural_miss" for row in fixtures
            ),
            "context_improved_actual_outcome_probability": sum(
                row["actual_outcome_probability_improvement"] > 0
                for row in fixtures
            ),
            "context_improved_side_xg_mae": sum(
                row["xg_side_mae_improvement"] > 0 for row in fixtures
            ),
            "goal_environment_dispersion": {
                "observed_xg_total": _distribution(observed_totals),
                "baseline_predicted_xg_total": _distribution(base_totals),
                "contextual_predicted_xg_total": _distribution(context_totals),
            },
            "context_adjustment_scale": {
                "mean_absolute_side_xg_shift": _rounded(_mean(xg_shifts)),
                "maximum_absolute_side_xg_shift": _rounded(max(xg_shifts)),
            },
            "preferred_route_coverage": {
                "observed": sorted(observed_routes),
                "missing": sorted(known_routes - observed_routes),
                "covered_routes": len(observed_routes),
                "known_routes": len(known_routes),
            },
            "route_diagnostics": route_diagnostics,
        },
        "lineup_projection": _lineup_summary(result_rows, lineup_snapshot),
        "fixtures": fixtures,
    }


def evaluate_goal_coefficient_ablation(
    base_predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    goal_model_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Score only coefficient choices that were already frozen pre-kickoff.

    The dated Prediction Lab rows contain xG generated with the applied
    conservative coefficient and the side-specific fixture signal. That makes
    it possible to reconstruct the league baseline and test the artifact's
    zero, point, and raw coefficient alternatives without fitting to these
    outcomes.
    """

    prediction_by_id = {
        int(row["fixture"]["match_id"]): row for row in base_predictions
    }
    result_rows = list(results)
    if not result_rows:
        raise ValueError("goal coefficient ablation requires completed results")
    applied = float(goal_model_artifact["coefficient"])
    candidates = {
        "zero_coefficient": 0.0,
        "applied_conservative": applied,
        "frozen_point_estimate": float(goal_model_artifact["point_coefficient"]),
        "frozen_raw_estimate": float(goal_model_artifact["raw_coefficient"]),
    }
    reports = []
    for name, coefficient in candidates.items():
        side_errors = []
        side_squared_errors = []
        total_errors = []
        predicted_totals = []
        reconstructed_baselines = {"home": [], "away": []}
        for result in result_rows:
            match_id = int(result["match_id"])
            prediction = prediction_by_id.get(match_id)
            if prediction is None:
                raise ValueError(
                    f"goal coefficient ablation has no prediction for match {match_id}"
                )
            candidate_xg = {}
            for side in ("home", "away"):
                signal = float(
                    prediction["fixture_intelligence"][side]["fixture_signal_z"]
                )
                frozen_xg = float(prediction["predicted_xg"][side])
                league_baseline = frozen_xg / math.exp(applied * signal)
                reconstructed_baselines[side].append(league_baseline)
                value = league_baseline * math.exp(coefficient * signal)
                candidate_xg[side] = value
                error = abs(value - float(result["actual_xg"][side]))
                side_errors.append(error)
                side_squared_errors.append(error**2)
            predicted_total = candidate_xg["home"] + candidate_xg["away"]
            predicted_totals.append(predicted_total)
            total_errors.append(
                abs(predicted_total - float(result["actual_xg"]["total"]))
            )
        reports.append(
            {
                "candidate": name,
                "coefficient": _rounded(coefficient, 9),
                "side_xg_mae": _rounded(_mean(side_errors)),
                "side_xg_rmse": _rounded(math.sqrt(_mean(side_squared_errors))),
                "total_xg_mae": _rounded(_mean(total_errors)),
                "predicted_total_xg_distribution": _distribution(predicted_totals),
                "reconstructed_competition_baseline": {
                    side: _rounded(_mean(values))
                    for side, values in reconstructed_baselines.items()
                },
            }
        )
    best = min(reports, key=lambda row: float(row["side_xg_mae"]))
    return {
        "goal_model_version": goal_model_artifact.get("version"),
        "goal_model_trained_through": goal_model_artifact.get("trained_through"),
        "outcomes_used_to_choose_candidates": False,
        "reconstruction_assumes_frozen_xg_was_not_clipped": True,
        "best_side_xg_mae_candidate": best["candidate"],
        "candidates": reports,
    }
