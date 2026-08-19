#!/usr/bin/env python3
"""Pull Clubalpha's free PL/UCL/preseason foundation from FotMob.

Raw responses are cached under data/cache/fotmob. Normalized datasets are
written under data/processed/foundation. Both are reproducible and ignored by
git; the compact coverage audit is written to reports/ and may be committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_player_stats,
    league_matches,
    league_table_teams,
    normalize_fixture,
    normalize_name,
    normalize_stat_rows,
    team_fixtures,
    team_squad,
)


MATCH_METRIC_AUDIT = {
    "minutes": ["minutes_played"],
    "goals": ["goals"],
    "assists": ["assists"],
    "xg": ["expected_goals"],
    "xa": ["expected_assists"],
    "shots_on_target": ["ShotsOnTarget"],
    "chances_created": ["chances_created"],
    "box_touches": ["touches_opp_box"],
    "successful_dribbles": ["dribbles_succeeded"],
    "errors_leading_to_goal": ["errors_led_to_goal"],
    "tackles": ["matchstats.headers.tackles"],
    "aerial_duels_won": ["aerials_won"],
    "ground_duels_won": ["ground_duels_won"],
    "interceptions": ["interceptions"],
    "dribbled_past": ["dribbled_past"],
    "clearances": ["clearances"],
    "blocks": ["blocked_shots", "shot_blocks"],
    "accurate_passes": ["accurate_passes"],
    "top_speed": ["physical_metrics_topspeed"],
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


def iso_day(timestamp: str | None) -> str | None:
    return str(timestamp)[:10] if timestamp else None


def fixture_in_window(row: dict[str, Any], start: str, end: str) -> bool:
    day = iso_day((row.get("status") or {}).get("utcTime") or row.get("matchDate"))
    return bool(day and start <= day <= end)


def match_metric_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    competitions: dict[str, dict[str, Any]] = {}
    for row in rows:
        competition = row.get("competition") or "Unknown"
        bucket = competitions.setdefault(
            competition,
            {
                "match_ids": set(),
                "metric_match_ids": {name: set() for name in MATCH_METRIC_AUDIT},
            },
        )
        bucket["match_ids"].add(row["match_id"])
        metrics = row.get("metrics") or {}
        for canonical, aliases in MATCH_METRIC_AUDIT.items():
            if any((metrics.get(alias) or {}).get("value") is not None for alias in aliases):
                bucket["metric_match_ids"][canonical].add(row["match_id"])

    output: dict[str, Any] = {}
    for competition, bucket in sorted(competitions.items()):
        total = len(bucket["match_ids"])
        output[competition] = {
            "matches_with_any_player_stats": total,
            "metrics": {
                metric: {
                    "matches_with_value": len(match_ids),
                    "pct_of_detailed_matches": round(100 * len(match_ids) / total, 1) if total else 0.0,
                }
                for metric, match_ids in bucket["metric_match_ids"].items()
            },
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
            f"stat_{competition['fotmob_id']}_{competition['season'].replace('/', '-')}_{metric}",
        )
        rows.extend(
            normalize_stat_rows(
                payload,
                competition_id=int(competition["fotmob_id"]),
                competition=competition["name"],
                season=competition["season"],
            )
        )
    return rows, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/foundation.json")
    parser.add_argument("--ucl", type=Path, default=ROOT / "config/ucl-2026-27.json")
    parser.add_argument("--as-of", default=None, help="Inclusive YYYY-MM-DD snapshot date.")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached responses.")
    parser.add_argument("--skip-match-details", action="store_true")
    parser.add_argument("--skip-historical-match-details", action="store_true")
    parser.add_argument("--request-interval", type=float, default=0.25)
    args = parser.parse_args()

    config = load_json(args.config)
    ucl = load_json(args.ucl)
    as_of = args.as_of or date.today().isoformat()
    cache_dir = ROOT / "data/cache/fotmob"
    output_dir = ROOT / "data/processed/foundation"
    client = FotMobClient(
        cache_dir,
        refresh=args.refresh,
        request_interval=args.request_interval,
    )

    print("[1/7] Competition snapshots")
    league_payloads: dict[str, dict[str, Any]] = {}
    fixture_index: dict[int, dict[str, Any]] = {}
    historical_match_ids: set[int] = set()
    current_pl_teams: dict[int, dict[str, Any]] = {}
    for competition in config["competitions"]:
        payload = client.league(int(competition["fotmob_id"]), competition["season"])
        selected = (payload.get("details") or {}).get("selectedSeason")
        if selected != competition["season"]:
            raise RuntimeError(
                f"FotMob returned {selected!r} for {competition['key']}; expected {competition['season']!r}"
            )
        league_payloads[competition["key"]] = payload
        for match in league_matches(payload):
            normalized = normalize_fixture(match, source_scope=competition["key"])
            normalized["competition_id"] = int(competition["fotmob_id"])
            normalized["competition"] = competition["name"]
            fixture_index[normalized["match_id"]] = normalized
            if competition.get("pull_stats") and normalized["finished"]:
                historical_match_ids.add(normalized["match_id"])
        if competition["key"] == "premier_league_current":
            for row in league_table_teams(payload):
                current_pl_teams[int(row["id"])] = {
                    "team_id": int(row["id"]),
                    "name": row.get("name"),
                    "short_name": row.get("shortName"),
                    "premier_league_2026_27": True,
                    "ucl_status": None,
                }

    print("[2/7] UCL direct qualifiers and play-off field")
    team_index = dict(current_pl_teams)
    unresolved: list[str] = []
    for club in ucl["direct_qualifiers"]:
        requested_names = [club["name"], *(club.get("aliases") or [])]
        existing = next(
            (
                row
                for row in team_index.values()
                if normalize_name(row.get("name")) in {normalize_name(name) for name in requested_names}
            ),
            None,
        )
        hit = existing or client.resolve_team(club["name"], club.get("aliases") or [])
        if not hit:
            unresolved.append(club["name"])
            continue
        team_id = int(hit.get("id") or hit.get("team_id"))
        record = team_index.setdefault(
            team_id,
            {
                "team_id": team_id,
                "name": hit.get("name"),
                "short_name": None,
                "premier_league_2026_27": False,
                "ucl_status": None,
            },
        )
        record["ucl_status"] = "direct_league_phase"

    for day in config.get("ucl_qualification_dates") or []:
        daily = client.matches_on(day.replace("-", ""))
        for league in daily.get("leagues") or []:
            if normalize_name(league.get("name")) != "champions league qualification":
                continue
            for match in league.get("matches") or []:
                normalized = normalize_fixture(
                    {**match, "leagueId": league.get("primaryId") or league.get("id"), "leagueName": league.get("name")},
                    source_scope="champions_league_qualification_2026_27",
                )
                fixture_index[normalized["match_id"]] = normalized
                for side in ("home", "away"):
                    source_team = match.get(side) or {}
                    if not source_team.get("id"):
                        continue
                    team_id = int(source_team["id"])
                    record = team_index.setdefault(
                        team_id,
                        {
                            "team_id": team_id,
                            "name": source_team.get("name"),
                            "short_name": source_team.get("shortName"),
                            "premier_league_2026_27": False,
                            "ucl_status": None,
                        },
                    )
                    if not record.get("ucl_status"):
                        record["ucl_status"] = "playoff_contender"

    print(f"[3/7] Team pages, squads, and preseason registry ({len(team_index)} clubs)")
    squad_rows: list[dict[str, Any]] = []
    preseason_match_ids: set[int] = set()
    team_errors: list[dict[str, Any]] = []
    for number, team_id in enumerate(sorted(team_index), 1):
        print(f"  team {number:02d}/{len(team_index):02d}: {team_index[team_id]['name']}")
        try:
            payload = client.team(team_id)
        except RuntimeError as exc:
            team_errors.append({"team_id": team_id, "error": str(exc)})
            continue
        details = payload.get("details") or {}
        team_index[team_id]["name"] = details.get("name") or team_index[team_id]["name"]
        team_index[team_id]["country"] = details.get("country")
        team_index[team_id]["primary_league_id"] = details.get("primaryLeagueId")
        team_index[team_id]["primary_league"] = details.get("primaryLeagueName")
        members = team_squad(payload)
        team_index[team_id]["squad_players"] = len(members)
        for member in members:
            squad_rows.append(
                {
                    "team_id": team_id,
                    "team": team_index[team_id]["name"],
                    "player_id": int(member["id"]),
                    "player": member.get("name"),
                    "squad_group": member.get("squadGroup"),
                    "position": member.get("positionIdsDesc"),
                    "shirt_number": member.get("shirtNumber"),
                    "country_code": member.get("ccode"),
                    "age": member.get("age"),
                    "date_of_birth": member.get("dateOfBirth"),
                    "height_cm": member.get("height"),
                    "injury": member.get("injury"),
                }
            )
        for match in team_fixtures(payload):
            tournament_name = str((match.get("tournament") or {}).get("name") or "")
            if tournament_name not in config["preseason"]["competition_names"]:
                continue
            if not fixture_in_window(match, config["preseason"]["from"], as_of):
                continue
            normalized = normalize_fixture(match, source_scope="preseason_2026")
            fixture_index[normalized["match_id"]] = normalized
            if normalized["finished"]:
                preseason_match_ids.add(normalized["match_id"])

    print(f"[4/7] Preseason player-match detail ({len(preseason_match_ids)} matches)")
    match_player_rows: list[dict[str, Any]] = []
    match_detail_errors: list[dict[str, Any]] = []
    if not args.skip_match_details:
        for number, match_id in enumerate(sorted(preseason_match_ids), 1):
            if number == 1 or number % 10 == 0 or number == len(preseason_match_ids):
                print(f"  match {number:03d}/{len(preseason_match_ids):03d}")
            try:
                match_player_rows.extend(flatten_match_player_stats(client.match(match_id)))
            except RuntimeError as exc:
                match_detail_errors.append({"match_id": match_id, "error": str(exc)})

    print(f"[5/7] Historical player-match detail ({len(historical_match_ids)} matches)")
    historical_match_player_rows: list[dict[str, Any]] = []
    historical_match_detail_errors: list[dict[str, Any]] = []
    if not args.skip_historical_match_details:
        for number, match_id in enumerate(sorted(historical_match_ids), 1):
            if number == 1 or number % 25 == 0 or number == len(historical_match_ids):
                print(f"  match {number:03d}/{len(historical_match_ids):03d}")
            try:
                historical_match_player_rows.extend(flatten_match_player_stats(client.match(match_id)))
            except RuntimeError as exc:
                historical_match_detail_errors.append({"match_id": match_id, "error": str(exc)})

    print("[6/7] Previous-season PL and UCL leaderboards")
    player_stat_rows: list[dict[str, Any]] = []
    team_stat_rows: list[dict[str, Any]] = []
    missing_stats: dict[str, dict[str, list[str]]] = {}
    for competition in config["competitions"]:
        if not competition.get("pull_stats"):
            continue
        payload = league_payloads[competition["key"]]
        player_rows, missing_player = pull_stat_rows(
            client, competition, payload, set(config["player_metrics"])
        )
        team_rows, missing_team = pull_stat_rows(
            client, competition, payload, set(config["team_metrics"])
        )
        player_stat_rows.extend(player_rows)
        team_stat_rows.extend(team_rows)
        missing_stats[competition["key"]] = {
            "player": missing_player,
            "team": missing_team,
        }

    print("[7/7] Normalized datasets and coverage audit")
    teams = sorted(team_index.values(), key=lambda row: (row.get("name") or "", row["team_id"]))
    fixtures = sorted(
        fixture_index.values(),
        key=lambda row: (row.get("kickoff_utc") or "", row["match_id"]),
    )
    preseason_fixtures = [row for row in fixtures if row.get("source_scope") == "preseason_2026"]
    finished_preseason_ids = {
        row["match_id"] for row in preseason_fixtures if row.get("finished")
    }
    detailed_preseason_ids = {row["match_id"] for row in match_player_rows}
    missing_preseason_detail_ids = sorted(finished_preseason_ids - detailed_preseason_ids)
    detailed_historical_ids = {row["match_id"] for row in historical_match_player_rows}
    missing_historical_detail_ids = sorted(historical_match_ids - detailed_historical_ids)
    teams_without_squad = [
        {"team_id": row["team_id"], "name": row.get("name"), "ucl_status": row.get("ucl_status")}
        for row in teams
        if not row.get("squad_players")
    ]
    write_json(output_dir / "teams.json", teams)
    counts = {
        "teams": len(teams),
        "pl_teams": sum(1 for row in teams if row.get("premier_league_2026_27")),
        "ucl_direct_qualifiers": sum(1 for row in teams if row.get("ucl_status") == "direct_league_phase"),
        "ucl_playoff_contenders": sum(1 for row in teams if row.get("ucl_status") == "playoff_contender"),
        "teams_without_squad": len(teams_without_squad),
        "squad_rows": write_jsonl(output_dir / "squads.jsonl", squad_rows),
        "fixtures": write_jsonl(output_dir / "fixtures.jsonl", fixtures),
        "preseason_fixtures": len(preseason_fixtures),
        "preseason_finished_fixtures": len(finished_preseason_ids),
        "preseason_matches_with_player_stats": len(detailed_preseason_ids),
        "preseason_matches_without_player_stats": len(missing_preseason_detail_ids),
        "preseason_player_detail_coverage_pct": round(
            100 * len(detailed_preseason_ids) / len(finished_preseason_ids), 1
        ) if finished_preseason_ids else 0.0,
        "preseason_match_player_rows": write_jsonl(
            output_dir / "preseason_match_player_stats.jsonl", match_player_rows
        ),
        "historical_finished_fixtures": len(historical_match_ids),
        "historical_matches_with_player_stats": len(detailed_historical_ids),
        "historical_matches_without_player_stats": len(missing_historical_detail_ids),
        "historical_player_detail_coverage_pct": round(
            100 * len(detailed_historical_ids) / len(historical_match_ids), 1
        ) if historical_match_ids else 0.0,
        "historical_match_player_rows": write_jsonl(
            output_dir / "historical_match_player_stats.jsonl", historical_match_player_rows
        ),
        "season_player_stat_rows": write_jsonl(
            output_dir / "season_player_stats.jsonl", player_stat_rows
        ),
        "season_team_stat_rows": write_jsonl(output_dir / "season_team_stats.jsonl", team_stat_rows),
    }
    source_manifest = {
        "source": "FotMob public web data",
        "source_status": "unofficial_undocumented",
        "retrieved_as_of": as_of,
        "web_base": "https://www.fotmob.com/api/data",
        "stats_base": "https://data.fotmob.com/stats",
        "ucl_registry_source": ucl["source"],
        "raw_cache": str(cache_dir.relative_to(ROOT)),
        "processed_output": str(output_dir.relative_to(ROOT)),
    }
    coverage = {
        "as_of": as_of,
        "counts": counts,
        "unresolved_ucl_direct_qualifiers": unresolved,
        "team_errors": team_errors,
        "teams_without_squad": teams_without_squad,
        "match_detail_errors": match_detail_errors,
        "historical_match_detail_errors": historical_match_detail_errors,
        "preseason_matches_without_player_stats_sample": missing_preseason_detail_ids[:20],
        "historical_matches_without_player_stats_sample": missing_historical_detail_ids[:20],
        "match_metric_coverage": {
            "historical": match_metric_coverage(historical_match_player_rows),
            "preseason": match_metric_coverage(match_player_rows),
        },
        "missing_requested_stats": missing_stats,
        "warnings": [
            "FotMob is an undocumented source; endpoint and field-shape tests are required.",
            "The 2026/27 UCL field remains provisional until seven play-off winners are known.",
            "A listed preseason fixture may have no player detail when FotMob coverage is incomplete.",
            "Metric presence counts show matches with at least one explicit value; an omitted zero may appear as missing.",
        ],
    }
    write_json(output_dir / "source_manifest.json", source_manifest)
    write_json(output_dir / "coverage.json", coverage)
    write_json(ROOT / "reports/foundation-coverage.json", coverage)

    print(json.dumps(counts, indent=2))
    return 0 if not unresolved and not team_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
