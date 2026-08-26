#!/usr/bin/env python3
"""Chronological backtest for Squad Selection v2.

Every target is projected from that club's earlier match rows only. Candidate
players are those previously observed for the club; a debuting or transferred
starter is therefore an explicit unseen-player miss rather than silent future
knowledge.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.squad_selection import _lineup_selection_role  # noqa: E402
from clubalpha.squad_selection_v2 import (  # noqa: E402
    minutes_only_baseline,
    project_team_selection,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


def timestamp(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate_source(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject lookalike files that cannot support a starting-XI backtest."""

    if not rows:
        raise ValueError("Player-match source is empty")
    required = ("match_id", "competition_id", "kickoff_utc", "team_id", "player_id")
    missing = {
        field: sum(row.get(field) is None for row in rows) for field in required
    }
    if any(missing.values()):
        raise ValueError(f"Player-match source has missing required fields: {missing}")

    starter_rows = sum(row.get("is_starter") is True for row in rows)
    lineup_position_rows = sum(row.get("lineup_position_id") is not None for row in rows)
    exact_team_lineups: dict[tuple[int, int], int] = defaultdict(int)
    for row in rows:
        if row.get("is_starter") is True:
            exact_team_lineups[(int(row["match_id"]), int(row["team_id"]))] += 1
    exact_lineups = sum(value == 11 for value in exact_team_lineups.values())
    if starter_rows == 0 or lineup_position_rows == 0 or exact_lineups == 0:
        raise ValueError(
            "Player-match source has no usable declared starting lineups "
            f"(starter_rows={starter_rows}, lineup_position_rows={lineup_position_rows}, "
            f"exact_team_lineups={exact_lineups})"
        )
    return {
        "rows": len(rows),
        "starter_rows": starter_rows,
        "lineup_position_rows": lineup_position_rows,
        "exact_team_lineups": exact_lineups,
        "required_field_missing_counts": missing,
    }


def minutes(row: dict[str, Any]) -> float:
    try:
        return max(
            0.0,
            min(
                90.0,
                float(
                    ((row.get("metrics") or {}).get("minutes_played") or {}).get(
                        "value"
                    )
                    or 0.0
                ),
            ),
        )
    except (TypeError, ValueError):
        return 0.0


def candidate_pool(prior_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    roles: dict[int, str] = {}
    ordered = sorted(prior_rows, key=lambda row: str(row.get("kickoff_utc") or ""))
    for row in ordered:
        player_id = int(row["player_id"])
        latest[player_id] = row
        role = _lineup_selection_role(row.get("lineup_position_id"))
        if role:
            roles[player_id] = role
    return [
        {
            "player_id": player_id,
            "player": row.get("player"),
            "selection_role": roles.get(player_id),
            "injury": None,
        }
        for player_id, row in latest.items()
    ]


def score_projection(
    projection: dict[str, Any],
    target_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    actual_starters = {
        int(row["player_id"])
        for row in target_rows
        if row.get("is_starter") is True
    }
    predicted_starters = {
        int(row["player_id"]) for row in projection["predicted_starting_xi"]
    }
    predicted_players = {
        int(row["player_id"]): row for row in projection["players"]
    }
    actual_minutes = {int(row["player_id"]): minutes(row) for row in target_rows}
    universe = set(predicted_players) | set(actual_minutes)
    squared_start_errors = []
    minute_errors = []
    for player_id in universe:
        player = predicted_players.get(player_id) or {}
        probability = float(player.get("start_probability") or 0.0)
        squared_start_errors.append(
            (probability - float(player_id in actual_starters)) ** 2
        )
        minute_errors.append(
            abs(
                float(player.get("expected_minutes") or 0.0)
                - actual_minutes.get(player_id, 0.0)
            )
        )

    actual_formation = next(
        (row.get("team_formation") for row in target_rows if row.get("team_formation")),
        None,
    )
    actual_roles = [
        _lineup_selection_role(row.get("lineup_position_id"))
        for row in target_rows
        if row.get("is_starter") is True
    ]
    actual_slots = {
        role: actual_roles.count(role) for role in ("GK", "DEF", "MID", "FWD")
    }
    predicted_slots = projection["shape_projection"]["role_slots"]
    hit_count = len(actual_starters & predicted_starters)
    union_count = len(actual_starters | predicted_starters)
    unseen_starters = actual_starters - set(predicted_players)
    return {
        "xi_hits": hit_count,
        "xi_hit_rate": hit_count / 11.0,
        "xi_jaccard": hit_count / union_count if union_count else 0.0,
        "start_brier": mean(squared_start_errors) or 0.0,
        "minutes_mae": mean(minute_errors) or 0.0,
        "formation_correct": (
            projection["shape_projection"].get("formation") == actual_formation
            if actual_formation
            else None
        ),
        "role_shape_correct": predicted_slots == actual_slots,
        "unseen_starters": len(unseen_starters),
        "candidate_coverage": (11 - len(unseen_starters)) / 11.0,
    }


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    metrics = [row[key] for row in rows]
    formation = [row["formation_correct"] for row in metrics if row["formation_correct"] is not None]
    return {
        "team_projections": len(metrics),
        "mean_xi_hits_of_11": rounded(mean([row["xi_hits"] for row in metrics])),
        "xi_hit_rate": rounded(mean([row["xi_hit_rate"] for row in metrics])),
        "xi_jaccard": rounded(mean([row["xi_jaccard"] for row in metrics])),
        "start_brier": rounded(mean([row["start_brier"] for row in metrics])),
        "expected_minutes_mae": rounded(mean([row["minutes_mae"] for row in metrics])),
        "formation_accuracy": rounded(mean([float(value) for value in formation])),
        "role_shape_accuracy": rounded(
            mean([float(row["role_shape_correct"]) for row in metrics])
        ),
        "unseen_actual_starters": sum(row["unseen_starters"] for row in metrics),
        "candidate_starter_coverage": rounded(
            mean([row["candidate_coverage"] for row in metrics])
        ),
    }


def metric_delta(
    v1_summary: dict[str, Any], v2_summary: dict[str, Any]
) -> dict[str, Any]:
    return {
        "xi_hit_rate": rounded(
            float(v2_summary["xi_hit_rate"] or 0)
            - float(v1_summary["xi_hit_rate"] or 0)
        ),
        "mean_xi_hits_of_11": rounded(
            float(v2_summary["mean_xi_hits_of_11"] or 0)
            - float(v1_summary["mean_xi_hits_of_11"] or 0)
        ),
        "start_brier": rounded(
            float(v2_summary["start_brier"] or 0)
            - float(v1_summary["start_brier"] or 0)
        ),
        "expected_minutes_mae": rounded(
            float(v2_summary["expected_minutes_mae"] or 0)
            - float(v1_summary["expected_minutes_mae"] or 0)
        ),
        "formation_accuracy": rounded(
            float(v2_summary["formation_accuracy"] or 0)
            - float(v1_summary["formation_accuracy"] or 0)
        ),
        "role_shape_accuracy": rounded(
            float(v2_summary["role_shape_accuracy"] or 0)
            - float(v1_summary["role_shape_accuracy"] or 0)
        ),
    }


def comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    v1 = summarize(rows, "v1_minutes_policy")
    v2 = summarize(rows, "v2_probability_policy")
    return {
        "target_count": len(rows),
        "v1_minutes_policy": v1,
        "v2_probability_policy": v2,
        "delta_v2_minus_v1": metric_delta(v1, v2),
    }


def with_bonus(config: dict[str, Any], bonus: float) -> dict[str, Any]:
    candidate = copy.deepcopy(config)
    candidate["selection"]["latest_declared_start_bonus_minutes"] = float(bonus)
    by_source = candidate["selection"].get("latest_declared_start_bonus_by_source")
    if by_source is not None:
        by_source["current_season"] = float(bonus)
        by_source["previous_season"] = float(bonus)
    return candidate


def build_targets(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, int, int]:
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    match_ids = set()
    for row in rows:
        by_team[int(row["team_id"])].append(row)
        match_ids.add(int(row["match_id"]))

    targets: list[dict[str, Any]] = []
    for team_id, team_rows in by_team.items():
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in team_rows:
            grouped[int(row["match_id"])].append(row)
        ordered_matches = sorted(
            grouped.items(),
            key=lambda item: str(item[1][0].get("kickoff_utc") or ""),
        )
        prior_rows: list[dict[str, Any]] = []
        previous_exact_starters: set[int] | None = None
        second_previous_exact_starters: set[int] | None = None
        previous_match_kickoff: str | None = None
        previous_competition_id: Any = None
        for match_id, target_rows in ordered_matches:
            target_kickoff = target_rows[0].get("kickoff_utc")
            actual_starters = {
                int(row["player_id"])
                for row in target_rows
                if row.get("is_starter") is True
            }
            if prior_rows and len(actual_starters) == 11:
                candidates = candidate_pool(prior_rows)
                target_competition_id = target_rows[0].get("competition_id")
                v2 = project_team_selection(
                    prior_rows,
                    candidates,
                    target_kickoff,
                    target_competition_id,
                    config,
                    team_id=team_id,
                    team=target_rows[0].get("team"),
                )
                v1 = minutes_only_baseline(
                    prior_rows,
                    candidates,
                    target_kickoff,
                    target_competition_id,
                    config,
                )
                targets.append(
                    {
                        "match_id": match_id,
                        "kickoff_utc": target_kickoff,
                        "competition_id": target_competition_id,
                        "competition": target_rows[0].get("competition"),
                        "team_id": team_id,
                        "team": target_rows[0].get("team"),
                        "days_since_previous_match": (
                            round(
                                (
                                    timestamp(target_kickoff)
                                    - timestamp(previous_match_kickoff)
                                ).total_seconds()
                                / 86400.0,
                                3,
                            )
                            if previous_match_kickoff is not None
                            else None
                        ),
                        "competition_changed_since_previous_match": (
                            str(target_competition_id)
                            != str(previous_competition_id)
                            if previous_competition_id is not None
                            else None
                        ),
                        "lineup_changes_from_previous_exact_xi": (
                            11 - len(actual_starters & previous_exact_starters)
                            if previous_exact_starters is not None
                            else None
                        ),
                        "known_changes_between_two_previous_exact_xis": (
                            11
                            - len(
                                previous_exact_starters
                                & second_previous_exact_starters
                            )
                            if previous_exact_starters is not None
                            and second_previous_exact_starters is not None
                            else None
                        ),
                        "v1_minutes_policy": score_projection(v1, target_rows),
                        "v2_probability_policy": score_projection(v2, target_rows),
                    }
                )
            if len(actual_starters) == 11:
                second_previous_exact_starters = previous_exact_starters
                previous_exact_starters = actual_starters
            previous_match_kickoff = target_kickoff
            previous_competition_id = target_rows[0].get("competition_id")
            prior_rows.extend(target_rows)

    targets.sort(
        key=lambda row: (str(row["kickoff_utc"]), row["match_id"], row["team_id"])
    )
    return targets, len(match_ids), len(by_team), sum(
        value == 2
        for value in {
            match_id: sum(row["match_id"] == match_id for row in targets)
            for match_id in {row["match_id"] for row in targets}
        }.values()
    )


def grouped_comparisons(
    rows: list[dict[str, Any]], labeler: Any
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        label = labeler(row)
        if label is not None:
            groups[str(label)].append(row)
    return {label: comparison(group) for label, group in sorted(groups.items())}


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def paired_match_bootstrap(
    rows: list[dict[str, Any]], *, samples: int = 5000, seed: int = 20260826
) -> dict[str, Any]:
    by_match: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_match[int(row["match_id"])].append(row)
    match_ids = sorted(by_match)
    rng = random.Random(seed)
    xi_deltas: list[float] = []
    formation_deltas: list[float] = []
    role_deltas: list[float] = []
    for _ in range(samples):
        sampled = [
            row
            for _match_id in range(len(match_ids))
            for row in by_match[rng.choice(match_ids)]
        ]
        xi_deltas.append(
            sum(
                row["v2_probability_policy"]["xi_hits"]
                - row["v1_minutes_policy"]["xi_hits"]
                for row in sampled
            )
            / len(sampled)
        )
        formation_pairs = [
            float(row["v2_probability_policy"]["formation_correct"])
            - float(row["v1_minutes_policy"]["formation_correct"])
            for row in sampled
            if row["v2_probability_policy"]["formation_correct"] is not None
            and row["v1_minutes_policy"]["formation_correct"] is not None
        ]
        role_pairs = [
            float(row["v2_probability_policy"]["role_shape_correct"])
            - float(row["v1_minutes_policy"]["role_shape_correct"])
            for row in sampled
        ]
        formation_deltas.append(sum(formation_pairs) / len(formation_pairs))
        role_deltas.append(sum(role_pairs) / len(role_pairs))

    def interval(values: list[float]) -> dict[str, Any]:
        return {
            "ci_95": [
                rounded(percentile(values, 0.025)),
                rounded(percentile(values, 0.975)),
            ],
            "bootstrap_probability_above_zero": rounded(
                sum(value > 0 for value in values) / len(values)
            ),
        }

    return {
        "cluster_unit": "match_id",
        "samples": samples,
        "seed": seed,
        "mean_xi_hits_of_11_delta": interval(xi_deltas),
        "formation_accuracy_delta": interval(formation_deltas),
        "role_shape_accuracy_delta": interval(role_deltas),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-match-rows", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/squad-selection-v2.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/squad-selection-v2-backtest.json",
    )
    args = parser.parse_args()

    config = load_json(args.config)
    rows = load_jsonl(args.player_match_rows)
    source_schema = validate_source(rows)
    development_share = float(
        config.get("selection", {}).get("tuning", {}).get("development_share", 0.6)
    )
    configured_bonus = float(
        config["selection"]["latest_declared_start_bonus_minutes"]
    )
    configured_suppression = bool(
        config["selection"].get(
            "suppress_latest_xi_bonus_after_competition_change", False
        )
    )
    bonuses = [
        float(value)
        for value in config["selection"]["tuning"]["candidate_bonus_minutes"]
    ]
    if configured_bonus not in bonuses:
        raise ValueError(
            f"Configured bonus {configured_bonus} is absent from tuning candidates"
        )
    suppression_candidates = [
        bool(value)
        for value in config["selection"]["tuning"].get(
            "candidate_competition_switch_suppression", [False]
        )
    ]
    if configured_suppression not in suppression_candidates:
        raise ValueError(
            "Configured competition-switch suppression is absent from tuning candidates"
        )

    candidate_targets: dict[tuple[float, bool], list[dict[str, Any]]] = {}
    coverage: tuple[int, int, int] | None = None
    for suppression in suppression_candidates:
        for bonus in bonuses:
            candidate_config = with_bonus(config, bonus)
            candidate_config["selection"][
                "suppress_latest_xi_bonus_after_competition_change"
            ] = suppression
            built, source_matches, source_teams, matches_both_sides = build_targets(
                rows, candidate_config
            )
            if len(built) < 2:
                raise ValueError(
                    "Player-match source produced fewer than two eligible projections"
                )
            candidate_targets[(bonus, suppression)] = built
            current_coverage = (source_matches, source_teams, matches_both_sides)
            if coverage is None:
                coverage = current_coverage
            if current_coverage != coverage:
                raise RuntimeError(
                    "Tuning candidates produced inconsistent target coverage"
                )

    targets = candidate_targets[(configured_bonus, configured_suppression)]
    development_cut = max(
        1, min(len(targets) - 1, int(len(targets) * development_share))
    )
    tuning_results = []
    for suppression in suppression_candidates:
        for bonus in bonuses:
            development_result = comparison(
                candidate_targets[(bonus, suppression)][:development_cut]
            )
            tuning_results.append(
                {
                    "bonus_minutes": bonus,
                    "suppress_bonus_after_competition_change": suppression,
                    "development_mean_xi_hits_of_11": development_result[
                        "v2_probability_policy"
                    ]["mean_xi_hits_of_11"],
                    "development_xi_hit_rate": development_result[
                        "v2_probability_policy"
                    ]["xi_hit_rate"],
                }
            )
    selected_policy = max(
        tuning_results,
        key=lambda row: (
            float(row["development_mean_xi_hits_of_11"] or 0),
            -float(row["bonus_minutes"]),
            not bool(row["suppress_bonus_after_competition_change"]),
        ),
    )
    configured_policy_won_development = (
        configured_bonus == selected_policy["bonus_minutes"]
        and configured_suppression
        == selected_policy["suppress_bonus_after_competition_change"]
    )

    development = targets[:development_cut]
    holdout = targets[development_cut:]
    full_result = comparison(targets)
    development_result = comparison(development)
    holdout_result = comparison(holdout)
    holdout_delta = holdout_result["delta_v2_minus_v1"]
    activation_checks = {
        "configured_policy_won_development": configured_policy_won_development,
        "higher_holdout_xi_hit_rate": float(holdout_delta["xi_hit_rate"] or 0) > 0,
        "no_worse_holdout_expected_minutes_mae": float(
            holdout_delta["expected_minutes_mae"] or 0
        )
        <= 0,
        "no_worse_holdout_formation_accuracy": float(
            holdout_delta["formation_accuracy"] or 0
        )
        >= 0,
        "no_worse_holdout_role_shape_accuracy": float(
            holdout_delta["role_shape_accuracy"] or 0
        )
        >= 0,
    }
    activation_passed = all(activation_checks.values())
    source_matches, source_teams, matches_both_sides = coverage or (0, 0, 0)

    half = max(1, len(holdout) // 2)
    time_segments = {
        "earlier_holdout_half": comparison(holdout[:half]),
        "later_holdout_half": comparison(holdout[half:]),
    }

    def volatility(row: dict[str, Any]) -> str | None:
        changes = row["lineup_changes_from_previous_exact_xi"]
        if changes is None:
            return None
        if changes <= 2:
            return "stable_0_to_2_changes"
        if changes <= 4:
            return "rotated_3_to_4_changes"
        return "volatile_5_plus_changes"

    def coverage_band(row: dict[str, Any]) -> str:
        covered = round(
            11 * row["v2_probability_policy"]["candidate_coverage"]
        )
        if covered == 11:
            return "all_11_starters_previously_observed"
        if covered >= 10:
            return "10_starters_previously_observed"
        return "9_or_fewer_starters_previously_observed"

    def known_rotation(row: dict[str, Any]) -> str | None:
        changes = row["known_changes_between_two_previous_exact_xis"]
        if changes is None:
            return None
        if changes <= 2:
            return "stable_prior_xis_0_to_2_changes"
        if changes <= 4:
            return "rotated_prior_xis_3_to_4_changes"
        return "volatile_prior_xis_5_plus_changes"

    def rest_band(row: dict[str, Any]) -> str | None:
        days = row["days_since_previous_match"]
        if days is None:
            return None
        if days < 4:
            return "short_rest_under_4_days"
        if days < 6:
            return "medium_rest_4_to_5_days"
        return "long_rest_6_plus_days"

    def competition_transition(row: dict[str, Any]) -> str | None:
        changed = row["competition_changed_since_previous_match"]
        if changed is None:
            return None
        return "competition_changed" if changed else "same_competition"

    team_results = grouped_comparisons(holdout, lambda row: row.get("team"))
    team_deltas = [
        {
            "team": team,
            "target_count": result["target_count"],
            "mean_xi_hits_of_11_delta": result["delta_v2_minus_v1"][
                "mean_xi_hits_of_11"
            ],
        }
        for team, result in team_results.items()
    ]
    report = {
        "version": config["version"],
        "status": "lock_v2" if activation_passed else "retain_v1",
        "source": {
            "filename": args.player_match_rows.name,
            "sha256": sha256(args.player_match_rows),
            "schema": source_schema,
        },
        "method": {
            "chronological": True,
            "future_rows_used": False,
            "candidate_pool": "players previously observed for that club",
            "unseen_target_starters_scored_as_misses": True,
            "evidence_window_matches": int(config["recent_evidence"]["maximum_matches"]),
            "baseline": "v1-style recency-weighted minutes plus latest exact shape, on the same candidates and evidence window",
            "development_share": development_share,
            "holdout_share": round(1.0 - development_share, 3),
            "tuning_uses_development_only": True,
            "activation_metrics_use_holdout_only": True,
        },
        "coverage": {
            "source_rows": len(rows),
            "source_matches": source_matches,
            "source_teams": source_teams,
            "evaluated_team_projections": len(targets),
            "evaluated_matches_with_both_sides": matches_both_sides,
        },
        "development_tuning": {
            "metric": "mean exact-XI starter hits",
            "tie_break": "smaller persistence bonus",
            "candidates": tuning_results,
            "selected_policy": {
                "bonus_minutes": selected_policy["bonus_minutes"],
                "suppress_bonus_after_competition_change": selected_policy[
                    "suppress_bonus_after_competition_change"
                ],
            },
            "configured_policy": {
                "bonus_minutes": configured_bonus,
                "suppress_bonus_after_competition_change": configured_suppression,
            },
            "configured_policy_won_development": configured_policy_won_development,
        },
        "all_targets_descriptive_only": full_result,
        "chronological_development": development_result,
        "chronological_holdout": holdout_result,
        "holdout_robustness": {
            "paired_match_bootstrap": paired_match_bootstrap(holdout),
            "by_competition": grouped_comparisons(
                holdout, lambda row: row.get("competition")
            ),
            "by_time": time_segments,
            "by_realized_lineup_volatility": grouped_comparisons(
                holdout, volatility
            ),
            "by_known_prior_lineup_volatility": grouped_comparisons(
                holdout, known_rotation
            ),
            "by_known_rest_days": grouped_comparisons(holdout, rest_band),
            "by_known_competition_transition": grouped_comparisons(
                holdout, competition_transition
            ),
            "by_candidate_coverage": grouped_comparisons(holdout, coverage_band),
            "team_concentration": {
                "teams_improved": sum(
                    float(row["mean_xi_hits_of_11_delta"] or 0) > 0
                    for row in team_deltas
                ),
                "teams_tied": sum(
                    float(row["mean_xi_hits_of_11_delta"] or 0) == 0
                    for row in team_deltas
                ),
                "teams_worse": sum(
                    float(row["mean_xi_hits_of_11_delta"] or 0) < 0
                    for row in team_deltas
                ),
                "team_deltas": sorted(
                    team_deltas,
                    key=lambda row: (
                        -float(row["mean_xi_hits_of_11_delta"] or 0),
                        row["team"],
                    ),
                ),
            },
        },
        "activation_gate": {
            "checks": activation_checks,
            "evaluated_on": "final_40_percent_chronological_holdout",
            "passed": activation_passed,
            "decision": "lock_v2" if activation_passed else "keep_v1_and_iterate",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
