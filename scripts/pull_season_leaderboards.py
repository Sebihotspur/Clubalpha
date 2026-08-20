#!/usr/bin/env python3
"""Pull full season leaderboards for the domestic competitions.

The domestic-history collector fetches two leaderboards per league — goals as a
reconciliation fallback and possessions won in the attacking third — and filters
even those to target clubs. That leaves every squad player whose previous club
sits outside the PL/UCL universe with no evidence at all.

FotMob publishes 52 to 66 leaderboards per league covering the whole division,
so the shortfall closes in a few hundred cached requests rather than the many
thousands of match fetches a fixture-level backfill would need.

Rows are kept only for players in the current squads. This is a player-centric
pull, not a league dump: collecting every player in twenty-one divisions would
add tens of thousands of rows that can never be graded.

Season aggregates are weaker evidence than match detail — no shot maps, no duel
percentages, no box touches — so rows are written to their own layer and
labelled, never blended into the match-detail sample unmarked.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.domestic_history import build_domestic_competitions  # noqa: E402
from clubalpha.fotmob import FotMobClient, normalize_stat_rows  # noqa: E402
from clubalpha.player_quality_v2 import scoring_position  # noqa: E402


# Player-level leaderboards that feed a v2 formula, plus the minutes and
# identity fields every per-90 rate needs. Team-level boards are excluded.
WANTED_METRICS = [
    "mins_played",
    "rating",
    "goals",
    "goal_assist",
    "total_att_assist",
    "big_chance_created",
    "ontarget_scoring_att",
    "total_scoring_att",
    "won_contest",
    "total_tackle",
    "interception",
    "effective_clearance",
    "outfielder_block",
    "ball_recovery",
    "accurate_pass",
    "accurate_long_balls",
    "poss_won_att_3rd",
    "defensive_contributions",
    "expected_goals",
    "expected_assists",
    "saves",
    "_save_percentage",
    "_goals_prevented",
    "goals_conceded",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(materialized)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/domestic-history.json")
    parser.add_argument("--foundation-dir", type=Path, default=ROOT / "data/processed/foundation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/season_leaderboards")
    parser.add_argument("--audit", type=Path, default=ROOT / "reports/season-leaderboard-coverage.json")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--request-interval", type=float, default=0.25)
    parser.add_argument("--league-id", type=int, action="append", dest="league_ids")
    args = parser.parse_args()

    teams_path = args.foundation_dir / "teams.json"
    squads_path = args.foundation_dir / "squads.jsonl"
    for path in (teams_path, squads_path):
        if not path.exists():
            raise SystemExit(f"Missing {path}; run pull_fotmob_foundation.py first.")

    config = load_json(args.config)
    teams = load_json(teams_path)
    squads = load_jsonl(squads_path)

    wanted_players = {
        int(squad["player_id"])
        for squad in squads
        if scoring_position(squad.get("position"), squad.get("squad_group"))
    }
    print(f"[1/3] {len(wanted_players)} current squad players in scope")

    competitions = build_domestic_competitions(teams, config)
    if args.league_ids:
        keep = set(args.league_ids)
        competitions = [row for row in competitions if row["league_id"] in keep]

    client = FotMobClient(
        ROOT / "data/cache/fotmob",
        refresh=args.refresh,
        request_interval=args.request_interval,
    )

    print(f"[2/3] Fetch leaderboards for {len(competitions)} competitions")
    rows: list[dict[str, Any]] = []
    competition_audit: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    requests = 0

    for number, competition in enumerate(competitions, 1):
        league_id = competition["league_id"]
        season = competition["season"]
        print(f"  {number:02d}/{len(competitions):02d}: {competition['league_name']}")
        try:
            league_payload = client.league(league_id, season)
            manifest = client.season_stats_manifest(league_payload, season)
        except (RuntimeError, ValueError) as exc:
            errors.append(
                {"league_id": league_id, "league": competition["league_name"], "stage": "manifest", "error": str(exc)}
            )
            continue

        available = {
            row.get("StatName"): row
            for row in manifest.get("TopLists") or []
            if row.get("StatName") and row.get("StatLocation")
        }
        fetched: list[str] = []
        missing: list[str] = []
        kept_here = 0

        for metric in WANTED_METRICS:
            metadata = available.get(metric)
            if not metadata:
                missing.append(metric)
                continue
            try:
                payload = client.stat_leaderboard(
                    metadata["StatLocation"],
                    f"season_lb_{league_id}_{season.replace('/', '-')}_{metric}",
                )
                requests += 1
            except (RuntimeError, ValueError) as exc:
                errors.append(
                    {"league_id": league_id, "league": competition["league_name"], "metric": metric, "error": str(exc)}
                )
                continue
            normalized = normalize_stat_rows(
                payload,
                competition_id=league_id,
                competition=competition["league_name"],
                season=season,
            )
            # Player-centric: only squad players we might actually grade.
            for row in normalized:
                if row.get("participant_id") in wanted_players:
                    rows.append({**row, "source_scope": "season_leaderboard"})
                    kept_here += 1
            fetched.append(metric)

        competition_audit.append(
            {
                "league_id": league_id,
                "league": competition["league_name"],
                "season": season,
                "leaderboards_available": len(available),
                "metrics_fetched": len(fetched),
                "metrics_missing": missing,
                "squad_player_rows": kept_here,
            }
        )

    print("[3/3] Write dataset and coverage audit")
    by_player: dict[int, set[str]] = defaultdict(set)
    minutes_by_player: dict[int, float] = {}
    for row in rows:
        pid = int(row["participant_id"])
        by_player[pid].add(str(row.get("metric")))
        if row.get("metric") == "mins_played":
            try:
                minutes_by_player[pid] = float(row.get("value") or 0.0)
            except (TypeError, ValueError):
                pass

    counts = {
        "rows": write_jsonl(args.output_dir / "season_player_stats.jsonl", rows),
        "competitions": len(competition_audit),
        "leaderboard_requests": requests,
        "squad_players_covered": len(by_player),
        "squad_players_with_minutes": len(minutes_by_player),
        "squad_players_with_700_plus_minutes": sum(
            1 for value in minutes_by_player.values() if value >= 700
        ),
    }

    audit = {
        "version": "season_leaderboard_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "FotMob public web data",
        "source_status": "unofficial_undocumented",
        "sampling_policy": (
            "Whole-division season leaderboards, retained only for players in the current "
            "2026/27 squads. Not filtered to target clubs, which is the point: the players "
            "needing this evidence played for clubs outside the universe."
        ),
        "evidence_tier": "season_aggregate",
        "counts": counts,
        "requested_metrics": WANTED_METRICS,
        "competition_audit": competition_audit,
        "errors": errors,
        "warnings": [
            "Season aggregates are weaker than match detail: no shot maps, no duel percentages, no box touches.",
            "A leaderboard row can span two clubs for a player who transferred mid-season; provenance must stay visible.",
            "Without shot maps, non-penalty goals must come from goals minus the penalty sub-value rather than reconciled events.",
            "These rows live in their own layer and must never be blended into the match-detail sample unlabelled.",
        ],
    }
    write_json(args.output_dir / "coverage.json", audit)
    write_json(args.audit, audit)
    print(json.dumps(counts, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
