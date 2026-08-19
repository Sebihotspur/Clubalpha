#!/usr/bin/env python3
"""Pull club-filtered 2025/26 domestic history for the PL/UCL universe."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.domestic_history import (  # noqa: E402
    build_domestic_competitions,
    filter_target_player_rows,
    filter_target_stat_rows,
    select_domestic_fixtures,
    target_fixture_counts,
)
from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_player_stats,
    league_matches,
    normalize_stat_rows,
)


METRIC_ALIASES = {
    "minutes": ["minutes_played"],
    "goals": ["goals"],
    "non_penalty_goals": ["non_penalty_goals"],
    "assists": ["assists"],
    "xg": ["expected_goals"],
    "non_penalty_xg": ["expected_goals_non_penalty"],
    "xa": ["expected_assists"],
    "shots_on_target": ["ShotsOnTarget"],
    "chances_created": ["chances_created"],
    "box_touches": ["touches_opp_box"],
    "successful_dribbles": ["dribbles_succeeded"],
    "errors_leading_to_goal": ["errors_led_to_goal"],
    "tackles": ["matchstats.headers.tackles"],
    "aerial_duels": ["aerials_won"],
    "ground_duels": ["ground_duels_won"],
    "interceptions": ["interceptions"],
    "dribbled_past": ["dribbled_past"],
    "clearances": ["clearances"],
    "blocks": ["blocked_shots", "shot_blocks"],
    "accurate_passes": ["accurate_passes"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def metric_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    match_ids = {row["match_id"] for row in rows}
    output: dict[str, Any] = {}
    for name, aliases in METRIC_ALIASES.items():
        covered = {
            row["match_id"]
            for row in rows
            if any(((row.get("metrics") or {}).get(alias) or {}).get("value") is not None for alias in aliases)
        }
        output[name] = {
            "matches_with_value": len(covered),
            "pct_of_detailed_matches": round(100 * len(covered) / len(match_ids), 1) if match_ids else 0.0,
        }
    return output


def pull_stat_rows(
    client: FotMobClient,
    competition: dict[str, Any],
    league_payload: dict[str, Any],
    wanted: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    manifest = client.season_stats_manifest(league_payload, competition["season"])
    available = {
        row.get("StatName"): row
        for row in manifest.get("TopLists") or []
        if row.get("StatName") and row.get("StatLocation")
    }
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for metric in sorted(wanted):
        metadata = available.get(metric)
        if not metadata:
            missing.append(metric)
            continue
        payload = client.stat_leaderboard(
            metadata["StatLocation"],
            f"domestic_stat_{competition['league_id']}_{competition['season'].replace('/', '-')}_{metric}",
        )
        normalized = normalize_stat_rows(
            payload,
            competition_id=competition["league_id"],
            competition=competition["league_name"],
            season=competition["season"],
        )
        rows.extend(filter_target_stat_rows(normalized, competition))
    return rows, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/domestic-history.json")
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=ROOT / "data/processed/foundation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/domestic_history",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/domestic-history-coverage.json",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-match-details", action="store_true")
    parser.add_argument("--skip-stats", action="store_true")
    parser.add_argument("--league-id", type=int, action="append", dest="league_ids")
    parser.add_argument("--request-interval", type=float, default=0.25)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 6:
        raise SystemExit("--workers must be between 1 and 6")

    teams_path = args.foundation_dir / "teams.json"
    if not teams_path.exists():
        raise SystemExit("Missing foundation teams.json; run pull_fotmob_foundation.py first.")
    config = load_json(args.config)
    teams = load_json(teams_path)
    competitions = build_domestic_competitions(teams, config)
    if args.league_ids:
        wanted_ids = set(args.league_ids)
        competitions = [row for row in competitions if row["league_id"] in wanted_ids]

    cache_dir = ROOT / "data/cache/fotmob"
    client = FotMobClient(
        cache_dir,
        refresh=args.refresh,
        request_interval=args.request_interval,
    )
    print(f"[1/4] Domestic competition registry ({len(competitions)} leagues)")
    fixtures_by_id: dict[int, dict[str, Any]] = {}
    match_context: dict[int, dict[str, Any]] = {}
    competition_audit: list[dict[str, Any]] = []
    player_stat_rows: list[dict[str, Any]] = []
    competition_errors: list[dict[str, Any]] = []

    print("[2/4] League fixtures and required season leaderboards")
    for number, competition in enumerate(competitions, 1):
        print(
            f"  league {number:02d}/{len(competitions):02d}: "
            f"{competition['league_name']} ({len(competition['target_teams'])} clubs)"
        )
        try:
            payload = client.league(competition["league_id"], competition["season"])
            selected_season = (payload.get("details") or {}).get("selectedSeason")
            if selected_season != competition["season"]:
                raise RuntimeError(
                    f"FotMob returned season {selected_season!r}; expected {competition['season']!r}"
                )
            fixtures = select_domestic_fixtures(payload, competition)
            finished = [row for row in fixtures if row["finished"]]
            counts = target_fixture_counts(fixtures, competition)
            for fixture in fixtures:
                fixtures_by_id[fixture["match_id"]] = fixture
            for fixture in finished:
                match_context[fixture["match_id"]] = competition

            missing_stats: list[str] = []
            if not args.skip_stats:
                try:
                    stat_rows, missing_stats = pull_stat_rows(
                        client,
                        competition,
                        payload,
                        set(config["player_metrics"]),
                    )
                    player_stat_rows.extend(stat_rows)
                except (RuntimeError, ValueError) as exc:
                    missing_stats = sorted(config["player_metrics"])
                    competition_errors.append(
                        {
                            "league_id": competition["league_id"],
                            "league": competition["league_name"],
                            "stage": "season_stats",
                            "error": str(exc),
                        }
                    )

            competition_audit.append(
                {
                    **competition,
                    "league_fixture_count": len(league_matches(payload)),
                    "selected_fixtures": len(fixtures),
                    "finished_selected_fixtures": len(finished),
                    "target_fixture_counts": {
                        str(team["team_id"]): counts.get(team["team_id"], 0)
                        for team in competition["target_teams"]
                    },
                    "target_teams_without_fixtures": [
                        team
                        for team in competition["target_teams"]
                        if counts.get(team["team_id"], 0) == 0
                    ],
                    "missing_requested_stats": missing_stats,
                }
            )
        except RuntimeError as exc:
            competition_errors.append(
                {
                    "league_id": competition["league_id"],
                    "league": competition["league_name"],
                    "stage": "league",
                    "error": str(exc),
                }
            )

    print(f"[3/4] Target-club player-match detail ({len(match_context)} matches)")
    match_player_rows: list[dict[str, Any]] = []
    detail_errors: list[dict[str, Any]] = []
    detailed_ids: set[int] = set()
    if not args.skip_match_details:
        worker_state = threading.local()

        def fetch_match(match_id: int) -> tuple[int, list[dict[str, Any]], str | None]:
            worker_client = getattr(worker_state, "client", None)
            if worker_client is None:
                worker_client = FotMobClient(
                    cache_dir,
                    refresh=args.refresh,
                    request_interval=args.request_interval,
                )
                worker_state.client = worker_client
            try:
                rows = filter_target_player_rows(
                    flatten_match_player_stats(worker_client.match(match_id)),
                    match_context[match_id],
                )
                return match_id, rows, None
            except RuntimeError as exc:
                return match_id, [], str(exc)

        match_ids = sorted(match_context)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            results = executor.map(fetch_match, match_ids)
            for number, (match_id, rows, error) in enumerate(results, 1):
                if error:
                    detail_errors.append({"match_id": match_id, "error": error})
                elif rows:
                    detailed_ids.add(match_id)
                    match_player_rows.extend(rows)
                if number == 1 or number % 25 == 0 or number == len(match_context):
                    print(f"  match {number:04d}/{len(match_context):04d}")

    print("[4/4] Normalized datasets and coverage audit")
    fixtures = sorted(fixtures_by_id.values(), key=lambda row: (row.get("kickoff_utc") or "", row["match_id"]))
    expected_ids = set(match_context)
    missing_detail_ids = sorted(expected_ids - detailed_ids) if not args.skip_match_details else []
    generated_at = datetime.now(timezone.utc).isoformat()
    for competition_row in competition_audit:
        league_id = competition_row["league_id"]
        expected_competition_ids = {
            match_id
            for match_id, context in match_context.items()
            if context["league_id"] == league_id
        }
        detailed_competition_ids = expected_competition_ids & detailed_ids
        competition_row["matches_with_target_player_stats"] = len(detailed_competition_ids)
        competition_row["matches_without_target_player_stats"] = (
            len(expected_competition_ids) - len(detailed_competition_ids)
        )
        competition_row["target_player_detail_coverage_pct"] = (
            round(100 * len(detailed_competition_ids) / len(expected_competition_ids), 1)
            if expected_competition_ids and not args.skip_match_details
            else None
        )
    counts = {
        "competitions": len(competitions),
        "target_teams": len({team["team_id"] for row in competitions for team in row["target_teams"]}),
        "selected_fixtures": write_jsonl(args.output_dir / "fixtures.jsonl", fixtures),
        "finished_selected_fixtures": len(expected_ids),
        "matches_with_target_player_stats": len(detailed_ids),
        "matches_without_target_player_stats": len(missing_detail_ids),
        "target_player_detail_coverage_pct": (
            round(100 * len(detailed_ids) / len(expected_ids), 1) if expected_ids and not args.skip_match_details else None
        ),
        "match_player_rows": write_jsonl(args.output_dir / "match_player_stats.jsonl", match_player_rows),
        "season_player_stat_rows": write_jsonl(args.output_dir / "season_player_stats.jsonl", player_stat_rows),
    }
    manifest = {
        "version": config["version"],
        "generated_at_utc": generated_at,
        "source": "FotMob public web data",
        "source_status": "unofficial_undocumented",
        "sampling_policy": "Complete domestic matches for target clubs; opponent player rows excluded",
        "competitions": competitions,
        "counts": counts,
    }
    audit = {
        **manifest,
        "competition_audit": competition_audit,
        "competition_errors": competition_errors,
        "match_detail_errors": detail_errors,
        "matches_without_target_player_stats_sample": missing_detail_ids[:30],
        "metric_coverage": metric_coverage(match_player_rows),
        "warnings": [
            "Domestic match detail is club-filtered; opponent-only rows are excluded to prevent partial-season player grades.",
            "Players transferred from a non-target club may still require a player-centric backfill.",
            "FotMob is undocumented; endpoint and field-shape tests remain required.",
        ],
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "coverage.json", audit)
    write_json(args.audit, audit)
    print(json.dumps(counts, indent=2))
    return 0 if not competition_errors and not detail_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
