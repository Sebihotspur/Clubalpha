#!/usr/bin/env python3
"""Build a dated projected-XI Player Quality table for the Premier League."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_player_stats,
    league_matches,
    normalize_fixture,
    team_squad,
)
from clubalpha.role_aware_alpha import attach_role_aware_alpha  # noqa: E402
from clubalpha.squad_selection_v2 import project_team_selection  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def display_grade(score: float) -> str:
    """A display label only; never an input to another model."""

    if score >= 75:
        return "S"
    if score >= 65:
        return "A+"
    if score >= 58:
        return "A"
    if score >= 52:
        return "B+"
    if score >= 46:
        return "B"
    if score >= 40:
        return "C+"
    if score >= 30:
        return "C"
    return "D"


def coverage_confidence(coverage: float) -> str:
    if coverage >= 0.95:
        return "high"
    if coverage >= 0.85:
        return "medium"
    return "low"


def normalized_squad(
    client: FotMobClient, team_id: int, team: str
) -> list[dict[str, Any]]:
    return [
        {
            "team_id": team_id,
            "team": team,
            "player_id": int(member["id"]),
            "player": member.get("name"),
            "squad_group": member.get("squadGroup"),
            "position": member.get("positionIdsDesc"),
            "injury": member.get("injury"),
        }
        for member in team_squad(client.team(team_id))
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--season", default="2026/2027")
    parser.add_argument("--league-id", type=int, default=47)
    parser.add_argument("--foundation-dir", type=Path, required=True)
    parser.add_argument("--grades", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/squad-selection-v2.json"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=Path("/private/tmp/clubalpha-fotmob-current")
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    client = FotMobClient(
        args.cache_dir,
        refresh=args.refresh,
        request_interval=0.12,
    )
    league = client.league(args.league_id, args.season)
    fixtures = []
    team_names: dict[int, str] = {}
    for source in league_matches(league):
        fixture = normalize_fixture(source, source_scope="premier_league_current")
        fixture["competition_id"] = args.league_id
        fixture["competition"] = "Premier League"
        fixtures.append(fixture)
        team_names[int(fixture["home_team_id"])] = fixture["home_team"]
        team_names[int(fixture["away_team_id"])] = fixture["away_team"]
    team_ids = set(team_names)

    current_rows = []
    for fixture in fixtures:
        if not fixture["finished"] or str(fixture["kickoff_utc"])[:10] > args.as_of:
            continue
        for row in flatten_match_player_stats(client.match(int(fixture["match_id"]))):
            if int(row.get("team_id") or -1) not in team_ids:
                continue
            current_rows.append(
                {
                    **row,
                    "kickoff_utc": fixture["kickoff_utc"],
                    "competition_id": args.league_id,
                    "competition": "Premier League",
                    "selection_source": "current_season",
                }
            )

    squads: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for team_id in sorted(team_ids):
        squads[team_id] = normalized_squad(client, team_id, team_names[team_id])

    history: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in load_jsonl(args.foundation_dir / "historical_match_player_stats.jsonl"):
        team_id = int(row.get("team_id") or -1)
        if team_id in team_ids:
            history[team_id].append({**row, "selection_source": "previous_season"})
    for row in load_jsonl(args.foundation_dir / "preseason_match_player_stats.jsonl"):
        team_id = int(row.get("team_id") or -1)
        if team_id in team_ids:
            history[team_id].append({**row, "selection_source": "preseason"})
    for row in current_rows:
        history[int(row["team_id"])].append(row)

    next_fixture = {}
    for team_id in team_ids:
        candidates = [
            fixture
            for fixture in fixtures
            if not fixture["finished"]
            and str(fixture["kickoff_utc"])[:10] >= args.as_of
            and team_id
            in {int(fixture["home_team_id"]), int(fixture["away_team_id"])}
        ]
        if candidates:
            next_fixture[team_id] = min(
                candidates, key=lambda fixture: fixture["kickoff_utc"]
            )

    grades = load_jsonl(args.grades)
    config = load_json(args.config)
    clubs = []
    for team_id in sorted(next_fixture, key=lambda item: team_names[item]):
        fixture = next_fixture[team_id]
        side = "home" if int(fixture["home_team_id"]) == team_id else "away"
        opponent = fixture["away_team"] if side == "home" else fixture["home_team"]
        projection = project_team_selection(
            history[team_id],
            squads[team_id],
            fixture["kickoff_utc"],
            args.league_id,
            config,
            team_id=team_id,
            team=team_names[team_id],
        )
        projection = attach_role_aware_alpha(projection, grades)
        aggregates = projection["role_aware_alpha"]["team_aggregates"]
        xi_ids = {
            int(row["player_id"]) for row in projection["predicted_starting_xi"]
        }
        expected_xi = []
        for row in projection["players"]:
            if int(row["player_id"]) not in xi_ids:
                continue
            pillars = row.get("alpha_pillars") or {}
            expected_xi.append(
                {
                    "player_id": row["player_id"],
                    "player": row["player"],
                    "role": row["selection_role"],
                    "expected_minutes": row["expected_minutes"],
                    "start_frequency": row["start_probability"],
                    "alpha_ability_z": row.get("alpha_ability_z"),
                    "scoring_threat_z": (pillars.get("scoring_threat") or {}).get("z"),
                    "chance_creation_z": (pillars.get("chance_creation") or {}).get("z"),
                    "defensive_prevention_z": (
                        pillars.get("defensive_prevention") or {}
                    ).get("z"),
                }
            )
        role_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
        expected_xi.sort(
            key=lambda row: (role_order[row["role"]], -row["expected_minutes"])
        )
        statuses: dict[str, list[str]] = defaultdict(list)
        for row in projection["players"]:
            if row["availability_status"] != "available":
                statuses[row["availability_status"]].append(row["player"])
        clubs.append(
            {
                "team_id": team_id,
                "team": team_names[team_id],
                "next_fixture": {
                    "match_id": fixture["match_id"],
                    "kickoff_utc": fixture["kickoff_utc"],
                    "venue": side,
                    "opponent": opponent,
                },
                "formation": projection["shape_projection"]["formation"],
                "alpha": {
                    key: {"z": value["z"], "coverage": value["coverage"]}
                    for key, value in aggregates.items()
                },
                "expected_xi": expected_xi,
                "availability": dict(statuses),
                "evidence": projection["evidence"],
                "quality_flags": projection["quality_flags"],
                "projection_ready": projection["decision_boundaries"][
                    "projection_ready"
                ],
            }
        )

    alpha_values = [
        float(club["alpha"]["overall_alpha_ability"]["z"]) for club in clubs
    ]
    league_mean = statistics.mean(alpha_values)
    league_sd = statistics.stdev(alpha_values)
    for club in clubs:
        relative_z = (
            float(club["alpha"]["overall_alpha_ability"]["z"]) - league_mean
        ) / league_sd
        score = max(0.0, min(100.0, 50.0 + 15.0 * relative_z))
        club["league_relative_strength_index"] = round(score, 1)
        club["display_grade"] = display_grade(score)
        coverage = float(club["alpha"]["overall_alpha_ability"]["coverage"])
        club["grade_confidence"] = coverage_confidence(coverage)
        club["grade_provisional"] = coverage < 0.95
    clubs.sort(
        key=lambda club: (
            -float(club["alpha"]["overall_alpha_ability"]["z"]),
            club["team"],
        )
    )
    for rank, club in enumerate(clubs, 1):
        club["rank"] = rank

    report = {
        "snapshot_version": (
            f"clubalpha_premier_league_projected_xi_alpha_{args.as_of.replace('-', '_')}"
        ),
        "as_of": args.as_of,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": (
            "FotMob current squads, injuries, current-season declared lineups, "
            "preseason detail, and 2025/26 match history"
        ),
        "selection_version": config["version"],
        "player_quality_version": "clubalpha_player_quality_v2",
        "method": {
            "primary_grade": (
                "990-minute projected-squad weighted locked Alpha Ability z"
            ),
            "transition_source_weights": config["recent_evidence"][
                "source_weights"
            ],
            "strength_index": (
                "50 + 15 * within-snapshot z-score of team Alpha, capped 0-100; "
                "display only"
            ),
            "grade_confidence": (
                "high at 95% expected-minute Alpha coverage, medium at 85%, "
                "low below 85%"
            ),
            "not_in_grade": [
                "club_form",
                "historical_fixture_matchup",
                "opponent",
                "market_price",
            ],
        },
        "league_distribution": {
            "mean_team_alpha_z": round(league_mean, 6),
            "sample_sd": round(league_sd, 6),
        },
        "clubs": clubs,
        "decision_boundaries": {
            "full_fixture_prediction": False,
            "market_probability": False,
            "capital_ready": False,
            "selection_frequencies_calibrated": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for club in clubs:
        alpha = club["alpha"]
        print(
            club["rank"],
            club["team"],
            club["display_grade"],
            club["league_relative_strength_index"],
            alpha["overall_alpha_ability"]["z"],
            alpha["attacking_unit_alpha_ability"]["z"],
            alpha["defensive_unit_alpha_ability"]["z"],
            alpha["scoring_threat"]["z"],
            alpha["chance_creation"]["z"],
            alpha["defensive_prevention"]["z"],
            alpha["overall_alpha_ability"]["coverage"],
        )


if __name__ == "__main__":
    main()
