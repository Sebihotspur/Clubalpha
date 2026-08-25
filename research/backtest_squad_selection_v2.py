#!/usr/bin/env python3
"""Chronological backtest for Squad Selection v2.

Every target is projected from that club's earlier match rows only. Candidate
players are those previously observed for the club; a debuting or transferred
starter is therefore an explicit unseen-player miss rather than silent future
knowledge.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rounded(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None else None


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
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    match_ids = set()
    for row in rows:
        if row.get("team_id") is None or row.get("match_id") is None:
            continue
        by_team[int(row["team_id"])].append(row)
        match_ids.add(int(row["match_id"]))

    targets = []
    for team_id, team_rows in by_team.items():
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in team_rows:
            grouped[int(row["match_id"])].append(row)
        ordered_matches = sorted(
            grouped.items(),
            key=lambda item: str(item[1][0].get("kickoff_utc") or ""),
        )
        prior_rows: list[dict[str, Any]] = []
        for match_id, target_rows in ordered_matches:
            target_kickoff = target_rows[0].get("kickoff_utc")
            actual_starters = [row for row in target_rows if row.get("is_starter") is True]
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
                        "team_id": team_id,
                        "team": target_rows[0].get("team"),
                        "v1_minutes_policy": score_projection(v1, target_rows),
                        "v2_probability_policy": score_projection(v2, target_rows),
                    }
                )
            prior_rows.extend(target_rows)

    targets.sort(key=lambda row: (str(row["kickoff_utc"]), row["match_id"], row["team_id"]))
    v1_summary = summarize(targets, "v1_minutes_policy")
    v2_summary = summarize(targets, "v2_probability_policy")
    development_share = float(
        config.get("selection", {}).get("tuning", {}).get("development_share", 0.6)
    )
    development_cut = max(1, min(len(targets) - 1, int(len(targets) * development_share)))
    development = targets[:development_cut]
    holdout = targets[development_cut:]
    development_v1 = summarize(development, "v1_minutes_policy")
    development_v2 = summarize(development, "v2_probability_policy")
    holdout_v1 = summarize(holdout, "v1_minutes_policy")
    holdout_v2 = summarize(holdout, "v2_probability_policy")
    eligible_sides_by_match: dict[int, int] = defaultdict(int)
    for row in targets:
        eligible_sides_by_match[row["match_id"]] += 1
    matches_both_sides = sum(value == 2 for value in eligible_sides_by_match.values())
    xi_improvement = float(holdout_v2["xi_hit_rate"] or 0) - float(
        holdout_v1["xi_hit_rate"] or 0
    )
    minute_improvement = float(holdout_v1["expected_minutes_mae"] or 0) - float(
        holdout_v2["expected_minutes_mae"] or 0
    )
    activation_passed = xi_improvement > 0 and minute_improvement >= 0
    full_xi_improvement = float(v2_summary["xi_hit_rate"] or 0) - float(
        v1_summary["xi_hit_rate"] or 0
    )
    report = {
        "version": config["version"],
        "status": "activate" if activation_passed else "retain_v1",
        "source": args.player_match_rows.name,
        "method": {
            "chronological": True,
            "future_rows_used": False,
            "candidate_pool": "players previously observed for that club",
            "unseen_target_starters_scored_as_misses": True,
            "evidence_window_matches": int(config["recent_evidence"]["maximum_matches"]),
            "baseline": "v1-style recency-weighted minutes plus latest exact shape, on the same candidates and evidence window",
            "development_share": development_share,
            "holdout_share": round(1.0 - development_share, 3),
            "activation_metrics_use_holdout_only": True,
        },
        "coverage": {
            "source_rows": len(rows),
            "source_matches": len(match_ids),
            "source_teams": len(by_team),
            "evaluated_team_projections": len(targets),
            "evaluated_matches_with_both_sides": matches_both_sides,
        },
        "v1_minutes_policy": v1_summary,
        "v2_probability_policy": v2_summary,
        "chronological_development": {
            "target_count": len(development),
            "v1_minutes_policy": development_v1,
            "v2_probability_policy": development_v2,
        },
        "chronological_holdout": {
            "target_count": len(holdout),
            "v1_minutes_policy": holdout_v1,
            "v2_probability_policy": holdout_v2,
            "delta_v2_minus_v1": {
                "xi_hit_rate": rounded(xi_improvement),
                "mean_xi_hits_of_11": rounded(
                    float(holdout_v2["mean_xi_hits_of_11"] or 0)
                    - float(holdout_v1["mean_xi_hits_of_11"] or 0)
                ),
                "expected_minutes_mae": rounded(
                    float(holdout_v2["expected_minutes_mae"] or 0)
                    - float(holdout_v1["expected_minutes_mae"] or 0)
                ),
                "formation_accuracy": rounded(
                    float(holdout_v2["formation_accuracy"] or 0)
                    - float(holdout_v1["formation_accuracy"] or 0)
                ),
            },
        },
        "delta_v2_minus_v1": {
            "xi_hit_rate": rounded(full_xi_improvement),
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
        },
        "activation_gate": {
            "requires_higher_xi_hit_rate": True,
            "requires_no_worse_expected_minutes_mae": True,
            "evaluated_on": "final_40_percent_chronological_holdout",
            "passed": activation_passed,
            "decision": "promote_v2" if activation_passed else "keep_v1_and_iterate",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
