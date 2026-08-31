#!/usr/bin/env python3
"""Append completed FotMob results to a frozen prediction slate."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.contextual_backtest import (  # noqa: E402
    RESULT_VERSION,
    validate_contextual_results,
)
from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_team_stats,
    league_matches,
    normalize_fixture,
)
from clubalpha.round_robin_archive import load_jsonl  # noqa: E402
from clubalpha.official_shadow import score_results  # noqa: E402


TEAM_STAT_FIELDS = (
    "expected_goals",
    "expected_goals_open_play",
    "expected_goals_set_play",
    "total_shots",
    "shots_on_target",
    "big_chances",
    "touches_opp_box",
    "possession_pct",
    "passes",
    "pass_accuracy_pct",
    "opposition_half_passes",
    "crosses_completed",
    "cross_accuracy_pct",
    "long_balls_completed",
    "long_ball_accuracy_pct",
    "tackles",
    "interceptions",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ROOT / "artifacts/contextual_interaction/2026-08-26",
    )
    parser.add_argument("--league-id", type=int, default=47)
    parser.add_argument("--season", default="2026/2027")
    parser.add_argument(
        "--cache-dir", type=Path, default=ROOT / "data/cache/fotmob"
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Do not refresh FotMob league and match-detail responses.",
    )
    parser.add_argument(
        "--result-stream",
        choices=("contextual", "official"),
        default="contextual",
        help="Validate results against a contextual archive or official slate.",
    )
    return parser.parse_args()


def _lineup(payload: dict[str, Any], side: str) -> dict[str, Any]:
    lineup = ((payload.get("content") or {}).get("lineup") or {})
    team_lineup = lineup.get(f"{side}Team") or {}
    starters = [
        {
            "player_id": int(player["id"]),
            "player": player.get("name"),
            "position_id": player.get("positionId"),
        }
        for player in team_lineup.get("starters") or []
        if player.get("id") is not None
    ]
    return {
        "formation": team_lineup.get("formation"),
        "source": lineup.get("source"),
        "starter_ids": [player["player_id"] for player in starters],
        "starters": starters,
    }


def _team_stats(row: dict[str, Any]) -> dict[str, float | None]:
    return {field: row.get(f"{field}_for") for field in TEAM_STAT_FIELDS}


def _result(
    prediction: dict[str, Any],
    fixture: dict[str, Any],
    payload: dict[str, Any],
    *,
    season: str,
    recorded_at_utc: str,
) -> dict[str, Any]:
    fixture = {**fixture, "season": season}
    rows = flatten_match_team_stats(payload, fixture)
    by_team = {int(row["team_id"]): row for row in rows}
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    if home_id not in by_team or away_id not in by_team:
        raise ValueError(f"FotMob match {fixture['match_id']} has no team-stat pair")
    home = by_team[home_id]
    away = by_team[away_id]
    home_goals = int(home["goals_for"])
    away_goals = int(away["goals_for"])
    home_xg = home.get("expected_goals_for")
    away_xg = away.get("expected_goals_for")
    if home_xg is None or away_xg is None:
        raise ValueError(f"FotMob match {fixture['match_id']} has no complete xG pair")
    outcome = (
        "home_win"
        if home_goals > away_goals
        else "away_win" if away_goals > home_goals else "draw"
    )
    frozen = prediction["fixture"]
    return {
        "result_version": RESULT_VERSION,
        "recorded_at_utc": recorded_at_utc,
        "match_id": int(fixture["match_id"]),
        "season": season,
        "kickoff_utc": frozen["kickoff_utc"],
        "home_team_id": int(frozen["home_team_id"]),
        "home_team": frozen["home_team"],
        "away_team_id": int(frozen["away_team_id"]),
        "away_team": frozen["away_team"],
        "final_home_goals": home_goals,
        "final_away_goals": away_goals,
        "outcome": outcome,
        "actual_xg": {
            "home": float(home_xg),
            "away": float(away_xg),
            "total": float(home_xg) + float(away_xg),
        },
        "home_stats": _team_stats(home),
        "away_stats": _team_stats(away),
        "home_lineup": _lineup(payload, "home"),
        "away_lineup": _lineup(payload, "away"),
        "source": "FotMob",
        "source_match_id": str(fixture["match_id"]),
        "source_url": f"https://www.fotmob.com/matches/-/-#{fixture['match_id']}",
        "source_coverage_level": (payload.get("general") or {}).get(
            "coverageLevel"
        ),
    }


def main() -> int:
    args = parse_args()
    predictions_path = args.archive_dir / "predictions.jsonl"
    results_path = args.archive_dir / "results.jsonl"
    manifest_path = args.archive_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("prediction slate must be frozen before collection")
    predictions = load_jsonl(predictions_path)
    prediction_by_id = {
        int(row["fixture"]["match_id"]): row for row in predictions
    }
    client = FotMobClient(
        args.cache_dir,
        refresh=not args.use_cache,
        request_interval=0.25,
    )
    league = client.league(args.league_id, args.season)
    fixtures = {
        int(fixture["match_id"]): {**fixture, "season": args.season}
        for fixture in (
            normalize_fixture(row, source_scope="premier_league_current")
            for row in league_matches(league)
        )
        if int(fixture["match_id"]) in prediction_by_id
    }
    missing = sorted(set(prediction_by_id) - set(fixtures))
    if missing:
        raise ValueError(f"FotMob league feed is missing frozen matches: {missing}")

    recorded_at = datetime.now(timezone.utc).isoformat()
    with results_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = [json.loads(line) for line in handle if line.strip()]
        validator = (
            score_results
            if args.result_stream == "official"
            else validate_contextual_results
        )
        validator(predictions, existing)
        existing_ids = {int(row["match_id"]) for row in existing}
        additions = []
        for match_id, prediction in prediction_by_id.items():
            fixture = fixtures[match_id]
            if match_id in existing_ids or not fixture["finished"]:
                continue
            payload = client.match(match_id)
            result = _result(
                prediction,
                fixture,
                payload,
                season=args.season,
                recorded_at_utc=recorded_at,
            )
            if args.result_stream == "official":
                result["result_version"] = "official_shadow_result_v1"
            additions.append(result)
        additions.sort(key=lambda row: (row["kickoff_utc"], row["match_id"]))
        validator(predictions, [*existing, *additions])
        handle.seek(0, 2)
        for row in additions:
            handle.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    pending = sum(not fixtures[match_id]["finished"] for match_id in prediction_by_id)
    print(
        f"Appended {len(additions)} completed results; "
        f"ledger now has {len(existing) + len(additions)}/"
        f"{len(predictions)} fixtures ({pending} not finished)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
