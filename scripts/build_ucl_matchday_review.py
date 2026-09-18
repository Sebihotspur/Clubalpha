#!/usr/bin/env python3
"""Build a no-leakage UCL matchday research review for the website.

This is an observational artifact. It summarizes completed FotMob match cards,
attaches the already-locked Player Alpha grades, and deliberately refuses to
manufacture a retroactive prediction score.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import (  # noqa: E402
    flatten_match_player_stats,
    flatten_match_team_stats,
    normalize_fixture,
    team_fixtures,
)
from clubalpha.role_aware_alpha import build_role_aware_alpha  # noqa: E402


FOUNDATION_DIR = ROOT / "data/processed/foundation"
GRADES_PATH = ROOT / "data/processed/player_quality_v2/player_grades.jsonl"
CACHE_DIR = ROOT / "data/cache/fotmob"
DEFAULT_OUTPUT = ROOT / "reports/ucl-matchday-1-review.json"
DYNAMICS_PATH = ROOT / "data/processed/club_dynamics/club_dynamics.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def metric(row: dict[str, Any], key: str) -> float | None:
    value = ((row.get("metrics") or {}).get(key) or {}).get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def outcome(home: float, away: float) -> str:
    if home > away:
        return "home_win"
    if away > home:
        return "away_win"
    return "draw"


def observed_routes(row: dict[str, Any]) -> list[str]:
    """Describe measured attacking routes without turning them into model weight."""

    routes: list[str] = []
    xg_for = float(row.get("expected_goals_for") or 0.0)
    xg_against = float(row.get("expected_goals_against") or 0.0)
    possession = float(row.get("possession_pct_for") or 0.0)
    box_touches = float(row.get("touches_opp_box_for") or 0.0)
    big_chances = float(row.get("big_chances_for") or 0.0)
    set_piece_xg = float(row.get("expected_goals_set_play_for") or 0.0)
    crosses = float(row.get("crosses_attempted_est_for") or 0.0)
    if box_touches >= 25 and (xg_for >= 1.5 or big_chances >= 4):
        routes.append("box_pressure")
    if set_piece_xg >= 0.5:
        routes.append("set_piece")
    if crosses >= 18:
        routes.append("wide_delivery")
    if possession <= 45 and xg_for > xg_against:
        routes.append("direct_transition")
    if possession >= 58 and xg_for > xg_against:
        routes.append("territorial_control")
    return routes or ["balanced_or_unresolved"]


def style_identity(row: dict[str, Any] | None) -> dict[str, Any]:
    style = (row or {}).get("style") or {}
    return {
        "descriptors": [item.get("descriptor") for item in style.get("identity") or []],
        "coverage": style.get("coverage"),
    }


def pl_team_read(row: dict[str, Any], dynamics: dict[int, dict[str, Any]]) -> dict[str, Any]:
    xg_diff = round(
        float(row.get("expected_goals_for") or 0.0)
        - float(row.get("expected_goals_against") or 0.0),
        2,
    )
    result = outcome(float(row["goals_for"]), float(row["goals_against"]))
    if xg_diff >= 1.5:
        evidence = "strong_process_reinforcement"
    elif xg_diff >= 0.5:
        evidence = "process_supported"
    elif xg_diff > -0.5:
        evidence = "mixed_process"
    else:
        evidence = "process_warning"
    return {
        "team_id": int(row["team_id"]),
        "team": row.get("team"),
        "opponent": row.get("opponent"),
        "venue": row.get("venue"),
        "result": result,
        "score": f"{int(row['goals_for'])}-{int(row['goals_against'])}",
        "xg_for": row.get("expected_goals_for"),
        "xg_against": row.get("expected_goals_against"),
        "xg_difference": xg_diff,
        "possession_pct": row.get("possession_pct_for"),
        "box_touches": row.get("touches_opp_box_for"),
        "big_chances": row.get("big_chances_for"),
        "observed_routes": observed_routes(row),
        "club_style_identity": style_identity(dynamics.get(int(row["team_id"]))),
        "evidence_class": evidence,
    }


def selection_role(grade: dict[str, Any] | None, row: dict[str, Any]) -> str:
    if row.get("is_goalkeeper"):
        return "GK"
    position = str((grade or {}).get("scoring_position") or "")
    if position in {"CB", "FB"}:
        return "DEF"
    if position == "CM":
        return "MID"
    return "FWD"


def attach_alpha(
    player_rows: list[dict[str, Any]], grades: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grade_by_id = {int(row["player_id"]): row for row in grades}
    projected = []
    for row in player_rows:
        grade = grade_by_id.get(int(row["player_id"]))
        projected.append(
            {
                "player_id": int(row["player_id"]),
                "player": row.get("player"),
                "expected_minutes": metric(row, "minutes_played") or 0.0,
                "selection_role": selection_role(grade, row),
            }
        )
    context = build_role_aware_alpha(grades, projected)
    alpha_by_id = {int(row["player_id"]): row for row in context["players"]}
    enriched = []
    for row in player_rows:
        alpha = alpha_by_id[int(row["player_id"])]
        enriched.append(
            {
                "match_id": int(row["match_id"]),
                "team_id": int(row["team_id"]),
                "team": row.get("team"),
                "player_id": int(row["player_id"]),
                "player": row.get("player"),
                "minutes": metric(row, "minutes_played") or 0.0,
                "rating": metric(row, "rating_title"),
                "goals": int(metric(row, "goals") or 0),
                "assists": int(metric(row, "assists") or 0),
                "xg": metric(row, "expected_goals"),
                "xa": metric(row, "expected_assists"),
                "chances_created": metric(row, "chances_created"),
                "alpha_available": bool(alpha.get("alpha_available")),
                "alpha_ability_z": alpha.get("alpha_ability_z"),
                "alpha_position": alpha.get("alpha_position"),
                "pillars": {
                    key: (alpha.get("pillars", {}).get(key) or {}).get("z")
                    for key in (
                        "scoring_threat",
                        "chance_creation",
                        "defensive_prevention",
                    )
                },
            }
        )
    return enriched, context


def correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    xs = [row[0] for row in pairs]
    ys = [row[1] for row in pairs]
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator = math.sqrt(
        sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
    )
    return round(numerator / denominator, 3) if denominator else None


def competition_watch(
    match_id: int, grades: list[dict[str, Any]]
) -> dict[str, Any] | None:
    match_path = CACHE_DIR / f"match_{match_id}.json"
    team_path = CACHE_DIR / "team_8455.json"
    if not match_path.exists() or not team_path.exists():
        return None
    team_payload = load_json(team_path)
    fixture_source = next(
        (row for row in team_fixtures(team_payload) if int(row["id"]) == match_id),
        None,
    )
    if fixture_source is None:
        return None
    fixture = normalize_fixture(fixture_source, source_scope="cross_competition_watch")
    match_payload = load_json(match_path)
    team_rows = flatten_match_team_stats(match_payload, fixture)
    player_rows = flatten_match_player_stats(match_payload, fixture)
    enriched, _ = attach_alpha(player_rows, grades)
    home = next(row for row in team_rows if row["venue"] == "home")
    away = next(row for row in team_rows if row["venue"] == "away")
    top_players = sorted(
        (row for row in enriched if row["rating"] is not None),
        key=lambda row: float(row["rating"]),
        reverse=True,
    )[:5]
    return {
        "status": "research_only_not_in_pl_or_ucl_ledger",
        "competition": fixture["competition"],
        "match_id": match_id,
        "kickoff_utc": fixture["kickoff_utc"],
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "score": fixture["score"],
        "xg": {"home": home["expected_goals_for"], "away": away["expected_goals_for"]},
        "team_stats": {
            "home": {
                "shots_on_target": home["shots_on_target_for"],
                "big_chances": home["big_chances_for"],
                "box_touches": home["touches_opp_box_for"],
                "possession_pct": home["possession_pct_for"],
                "set_piece_xg": home["expected_goals_set_play_for"],
            },
            "away": {
                "shots_on_target": away["shots_on_target_for"],
                "big_chances": away["big_chances_for"],
                "box_touches": away["touches_opp_box_for"],
                "possession_pct": away["possession_pct_for"],
                "set_piece_xg": away["expected_goals_set_play_for"],
            },
        },
        "top_players": top_players,
        "model_read": (
            "Chelsea won 6-3 from a virtually even xG contest. The finishing is useful player-role "
            "evidence, but 2.42 xG conceded, 36 Leeds box touches, and 1.46 set-piece xG conceded "
            "are the more repeatable warning signals."
        ),
    }


def build(matchday: int, start_date: str, end_date: str) -> dict[str, Any]:
    fixtures = load_jsonl(FOUNDATION_DIR / "fixtures.jsonl")
    team_rows = load_jsonl(FOUNDATION_DIR / "current_match_team_stats.jsonl")
    player_rows = load_jsonl(FOUNDATION_DIR / "current_match_player_stats.jsonl")
    teams = load_json(FOUNDATION_DIR / "teams.json")
    grades = load_jsonl(GRADES_PATH)
    dynamics = load_jsonl(DYNAMICS_PATH) if DYNAMICS_PATH.exists() else []
    dynamics_by_team = {int(row["team_id"]): row for row in dynamics}

    ucl_schedule = sorted(
        (
            row
            for row in fixtures
            if row.get("source_scope") == "champions_league_current"
            and start_date <= str(row.get("kickoff_utc") or "")[:10] <= end_date
        ),
        key=lambda row: (str(row.get("kickoff_utc") or ""), int(row["match_id"])),
    )
    match_ids = {int(row["match_id"]) for row in ucl_schedule}
    completed = [row for row in ucl_schedule if row.get("finished")]
    completed_ids = {int(row["match_id"]) for row in completed}
    ucl_team_rows = [row for row in team_rows if int(row["match_id"]) in completed_ids]
    ucl_player_rows = [row for row in player_rows if int(row["match_id"]) in completed_ids]
    team_by_match = defaultdict(list)
    for row in ucl_team_rows:
        team_by_match[int(row["match_id"])].append(row)

    matches = []
    xg_winner_alignment = 0
    for fixture in ucl_schedule:
        match_id = int(fixture["match_id"])
        item = {
            "match_id": match_id,
            "kickoff_utc": fixture.get("kickoff_utc"),
            "home_team": fixture.get("home_team"),
            "away_team": fixture.get("away_team"),
            "status": "completed" if match_id in completed_ids else "pending",
        }
        if match_id in completed_ids:
            home = next(row for row in team_by_match[match_id] if row["venue"] == "home")
            away = next(row for row in team_by_match[match_id] if row["venue"] == "away")
            score_outcome = outcome(home["goals_for"], away["goals_for"])
            xg_outcome = outcome(home["expected_goals_for"], away["expected_goals_for"])
            aligned = score_outcome == xg_outcome
            xg_winner_alignment += int(aligned)
            item.update(
                {
                    "score": {
                        "home": int(home["goals_for"]),
                        "away": int(away["goals_for"]),
                    },
                    "xg": {
                        "home": home["expected_goals_for"],
                        "away": away["expected_goals_for"],
                    },
                    "team_stats": {
                        "home": {
                            "shots_on_target": home["shots_on_target_for"],
                            "big_chances": home["big_chances_for"],
                            "box_touches": home["touches_opp_box_for"],
                            "possession_pct": home["possession_pct_for"],
                            "open_play_xg": home["expected_goals_open_play_for"],
                            "set_piece_xg": home["expected_goals_set_play_for"],
                            "crosses_completed": home["crosses_completed_for"],
                            "crosses_attempted_est": home["crosses_attempted_est_for"],
                        },
                        "away": {
                            "shots_on_target": away["shots_on_target_for"],
                            "big_chances": away["big_chances_for"],
                            "box_touches": away["touches_opp_box_for"],
                            "possession_pct": away["possession_pct_for"],
                            "open_play_xg": away["expected_goals_open_play_for"],
                            "set_piece_xg": away["expected_goals_set_play_for"],
                            "crosses_completed": away["crosses_completed_for"],
                            "crosses_attempted_est": away["crosses_attempted_est_for"],
                        },
                    },
                    "archetype_context": {
                        "home": {
                            "club_style_identity": style_identity(
                                dynamics_by_team.get(int(fixture["home_team_id"]))
                            ),
                            "observed_routes": observed_routes(home),
                        },
                        "away": {
                            "club_style_identity": style_identity(
                                dynamics_by_team.get(int(fixture["away_team_id"]))
                            ),
                            "observed_routes": observed_routes(away),
                        },
                        "verdict": (
                            "process_backed_result" if aligned else "variance_watch"
                        ),
                    },
                    "result": score_outcome,
                    "xg_result": xg_outcome,
                    "score_xg_aligned": aligned,
                    "goal_residual": round(
                        home["goals_for"]
                        + away["goals_for"]
                        - home["expected_goals_for"]
                        - away["expected_goals_for"],
                        2,
                    ),
                }
            )
        matches.append(item)

    enriched_players, alpha_context = attach_alpha(ucl_player_rows, grades)
    rated = [
        row for row in enriched_players if row["rating"] is not None and row["minutes"] >= 30
    ]
    alpha_rated = [
        row for row in rated if row["alpha_available"] and row["alpha_ability_z"] is not None
    ]
    pairs = [(float(row["alpha_ability_z"]), float(row["rating"])) for row in alpha_rated]
    ranked_alpha = sorted(alpha_rated, key=lambda row: float(row["alpha_ability_z"]))
    quartile_size = max(1, len(ranked_alpha) // 4) if ranked_alpha else 0
    bottom = ranked_alpha[:quartile_size]
    top = ranked_alpha[-quartile_size:] if quartile_size else []

    minutes_by_team: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in enriched_players:
        minutes_by_team[row["team_id"]][0] += float(row["minutes"])
        if row["alpha_available"]:
            minutes_by_team[row["team_id"]][1] += float(row["minutes"])
    team_names = {int(row["team_id"]): row.get("name") for row in teams}
    coverage_by_team = sorted(
        (
            {
                "team_id": team_id,
                "team": team_names.get(team_id),
                "actual_minutes": round(values[0], 1),
                "alpha_minutes": round(values[1], 1),
                "coverage": round(values[1] / values[0], 4) if values[0] else 0.0,
            }
            for team_id, values in minutes_by_team.items()
        ),
        key=lambda row: (row["coverage"], str(row["team"])),
    )

    scorer_rows = [row for row in enriched_players if row["goals"] > 0]
    mapped_scorers = [row for row in scorer_rows if row["alpha_available"]]
    positive_threat = [
        row
        for row in mapped_scorers
        if row["pillars"].get("scoring_threat") is not None
        and float(row["pillars"]["scoring_threat"]) > 0
    ]

    pl_ids = {
        int(row["team_id"]) for row in teams if row.get("premier_league_2026_27")
    }
    pl_rows = [row for row in ucl_team_rows if int(row["team_id"]) in pl_ids]
    pl_wins = sum(float(row["goals_for"]) > float(row["goals_against"]) for row in pl_rows)
    completed_goal_rows = [
        row for row in ucl_team_rows if str(row.get("venue")) == "home"
    ]
    home_wins = sum(row["goals_for"] > row["goals_against"] for row in completed_goal_rows)
    draws = sum(row["goals_for"] == row["goals_against"] for row in completed_goal_rows)
    away_wins = len(completed_goal_rows) - home_wins - draws
    total_goals = sum(row["goals_for"] + row["goals_against"] for row in completed_goal_rows)
    total_xg = sum(
        row["expected_goals_for"] + row["expected_goals_against"]
        for row in completed_goal_rows
    )
    process_winners = [
        row
        for row in ucl_team_rows
        if row["goals_for"] > row["goals_against"]
        and row["expected_goals_for"] > row["expected_goals_against"]
    ]
    lower_possession_process_winners = sorted(
        row["team"]
        for row in process_winners
        if float(row.get("possession_pct_for") or 0.0) < 50.0
    )
    set_piece_spikes = sorted(
        (
            {
                "team": row["team"],
                "opponent": row["opponent"],
                "set_piece_xg": row["expected_goals_set_play_for"],
            }
            for row in ucl_team_rows
            if float(row.get("expected_goals_set_play_for") or 0.0) >= 0.75
        ),
        key=lambda row: float(row["set_piece_xg"]),
        reverse=True,
    )
    variance_matches = [
        {
            "match_id": row["match_id"],
            "fixture": f"{row['home_team']} vs {row['away_team']}",
            "result": row["result"],
            "xg_result": row["xg_result"],
        }
        for row in matches
        if row.get("status") == "completed" and not row.get("score_xg_aligned")
    ]
    pl_team_reads = sorted(
        (pl_team_read(row, dynamics_by_team) for row in pl_rows),
        key=lambda row: str(row["team"]),
    )

    report = {
        "version": "clubalpha_ucl_matchday_review_v1",
        "competition": "Champions League",
        "season": "2026/2027",
        "matchday": matchday,
        "as_of": date.today().isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if len(completed) == len(ucl_schedule) else "in_progress",
        "scope": {
            "scheduled_matches": len(ucl_schedule),
            "completed_matches": len(completed),
            "pending_matches": len(ucl_schedule) - len(completed),
            "start_date": start_date,
            "end_date": end_date,
        },
        "integrity": {
            "predictions_frozen_before_kickoff": False,
            "retroactive_hit_rate_created": False,
            "pl_and_ucl_calibration_separate": True,
            "player_alpha_formula_changed": False,
            "foundation_weights_changed": False,
            "capital_deployment_ready": False,
        },
        "aggregate": {
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "goals": int(total_goals),
            "goals_per_match": round(total_goals / len(completed), 2) if completed else None,
            "total_xg": round(total_xg, 2),
            "xg_per_match": round(total_xg / len(completed), 2) if completed else None,
            "goals_minus_xg": round(total_goals - total_xg, 2),
            "over_2_5": sum(
                row["goals_for"] + row["goals_against"] > 2
                for row in completed_goal_rows
            ),
            "btts": sum(
                row["goals_for"] > 0 and row["goals_against"] > 0
                for row in completed_goal_rows
            ),
            "score_xg_winner_alignment": xg_winner_alignment,
        },
        "player_alpha": {
            "player_match_rows": len(enriched_players),
            "actual_minute_coverage": alpha_context["coverage"][
                "alpha_expected_minute_coverage"
            ],
            "rating_sample_minimum_minutes": 30,
            "rating_alpha_pairs": len(pairs),
            "rating_alpha_correlation": correlation(pairs),
            "top_alpha_quartile_average_rating": (
                round(statistics.mean(float(row["rating"]) for row in top), 3)
                if top
                else None
            ),
            "bottom_alpha_quartile_average_rating": (
                round(statistics.mean(float(row["rating"]) for row in bottom), 3)
                if bottom
                else None
            ),
            "mapped_scorers": len(mapped_scorers),
            "mapped_scorers_with_positive_scoring_threat": len(positive_threat),
            "positive_scoring_threat_rate": (
                round(len(positive_threat) / len(mapped_scorers), 4)
                if mapped_scorers
                else None
            ),
            "lowest_team_coverage": coverage_by_team[:6],
            "top_match_ratings": sorted(
                (row for row in enriched_players if row["rating"] is not None),
                key=lambda row: float(row["rating"]),
                reverse=True,
            )[:12],
        },
        "premier_league_clubs": {
            "completed_matches": len(pl_rows),
            "wins": pl_wins,
            "xg_for": round(sum(row["expected_goals_for"] for row in pl_rows), 2),
            "xg_against": round(sum(row["expected_goals_against"] for row in pl_rows), 2),
            "team_rows": sorted(pl_rows, key=lambda row: str(row.get("team"))),
            "research_reads": pl_team_reads,
        },
        "tactical_archetype_lessons": {
            "result_process_alignment": {
                "aligned_matches": xg_winner_alignment,
                "completed_matches": len(completed),
                "variance_watch": variance_matches,
            },
            "lower_possession_process_winners": lower_possession_process_winners,
            "set_piece_xg_spikes": set_piece_spikes,
            "measured_route_policy": (
                "Observed route tags use match-card box pressure, set-piece xG, wide delivery, "
                "possession and xG only. They describe the match and do not change model weight."
            ),
            "high_pressing_status": (
                "Not promoted from this review because current match-card pressure coverage is incomplete."
            ),
        },
        "coverage_queue": {
            "alpha_minute_coverage": alpha_context["coverage"][
                "alpha_expected_minute_coverage"
            ],
            "priority_teams": coverage_by_team[:6],
            "zero_coverage_teams": [
                row for row in coverage_by_team if row["coverage"] == 0.0
            ],
            "action": (
                "Resolve transferred-player and foreign-league identity gaps before Matchday 2; "
                "missing Alpha remains neutral rather than imputed."
            ),
        },
        "matches": matches,
        "cross_competition_watch": competition_watch(6099342, grades),
        "learning_policy": [
            "Completed UCL evidence may update shared team form, style, lineup and player-role research.",
            "UCL and Premier League ledgers and calibration remain separate.",
            "One matchday cannot rewrite Player Alpha, the 60/30/10 foundation, or goal baselines.",
            "The first honest UCL prediction hit rate begins with a slate frozen before Matchday 2.",
        ],
        "conservative_recommendations": [
            "Retain the locked Player Alpha formula and 60/30/10 foundation weights.",
            "Treat 69 goals from 60.05 xG as finishing heat until a larger UCL sample confirms it.",
            "Feed team process, lineup minutes and observed routes into shared research, not the PL ledger.",
            "Freeze the first UCL probabilities before Matchday 2 and calibrate UCL separately.",
            "Close zero-coverage Alpha identities before using player-prop research for those clubs.",
        ],
    }
    if match_ids != {int(row["match_id"]) for row in matches}:
        raise ValueError("UCL matchday review lost a scheduled fixture")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matchday", type=int, default=1)
    parser.add_argument("--start-date", default="2026-09-08")
    parser.add_argument("--end-date", default="2026-09-10")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.matchday, args.start_date, args.end_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "completed": report["scope"]["completed_matches"],
                "scheduled": report["scope"]["scheduled_matches"],
                "player_alpha_minute_coverage": report["player_alpha"][
                    "actual_minute_coverage"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
