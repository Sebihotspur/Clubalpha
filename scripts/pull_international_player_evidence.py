#!/usr/bin/env python3
"""Collect national-team results and stats for Clubalpha-covered players."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_player_stats,
    flatten_match_team_stats,
    normalize_fixture,
)
from clubalpha.international_evidence import (  # noqa: E402
    SUM_METRICS,
    enrich_player_match,
    is_national_team_competition,
    metric_value,
    summarize_player_matches,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in materialized
        ),
        encoding="utf-8",
    )
    return len(materialized)


def covered_players(squads: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    players: dict[int, dict[str, Any]] = {}
    for row in squads:
        player_id = int(row["player_id"])
        player = players.setdefault(
            player_id,
            {
                "player": row.get("player"),
                "clubs": set(),
                "positions": set(),
            },
        )
        if row.get("team"):
            player["clubs"].add(str(row["team"]))
        if row.get("position"):
            player["positions"].add(str(row["position"]))
    return players


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", default="2026-09-21")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument(
        "--squads",
        type=Path,
        default=ROOT / "data/processed/foundation/squads.jsonl",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data/cache/fotmob/international",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/international_current",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/international-player-evidence-v1-audit.json",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--request-interval", type=float, default=0.12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from_date = date.fromisoformat(args.from_date)
    as_of = date.fromisoformat(args.as_of)
    if from_date > as_of:
        raise ValueError("from-date must not be after as-of")

    squad_rows = load_jsonl(args.squads)
    players = covered_players(squad_rows)
    client = FotMobClient(
        args.cache_dir,
        refresh=args.refresh,
        request_interval=args.request_interval,
    )

    fixture_index: dict[int, dict[str, Any]] = {}
    included_leagues: Counter[str] = Counter()
    excluded_international_leagues: Counter[str] = Counter()
    day = from_date
    queried_days = 0
    print(f"[1/4] Scan international fixtures {from_date} through {as_of}", flush=True)
    while day <= as_of:
        payload = client.matches_on(day.strftime("%Y%m%d"))
        queried_days += 1
        for league in payload.get("leagues") or []:
            if str(league.get("ccode") or "").upper() != "INT":
                continue
            if not is_national_team_competition(league):
                excluded_international_leagues[str(league.get("name") or "unknown")] += len(
                    league.get("matches") or []
                )
                continue
            for match in league.get("matches") or []:
                status = match.get("status") or {}
                if not status.get("finished") or status.get("cancelled"):
                    continue
                source = {
                    **match,
                    "leagueId": league.get("id"),
                    "parentLeagueId": league.get("primaryId")
                    or league.get("parentLeagueId"),
                    "leagueName": league.get("name"),
                }
                fixture = normalize_fixture(source, source_scope="international_current")
                fixture["competition"] = league.get("name")
                fixture["season"] = "2026/2027"
                fixture_index[int(fixture["match_id"])] = fixture
                included_leagues[str(league.get("name") or "unknown")] += 1
        day += timedelta(days=1)

    print(f"[2/4] Fetch {len(fixture_index)} completed international match cards", flush=True)
    player_matches: list[dict[str, Any]] = []
    team_rows_by_match: dict[int, list[dict[str, Any]]] = {}
    detail_errors: list[dict[str, Any]] = []
    matches_with_player_detail = 0
    for number, match_id in enumerate(sorted(fixture_index), 1):
        if number == 1 or number % 20 == 0 or number == len(fixture_index):
            print(f"  match {number:03d}/{len(fixture_index):03d}", flush=True)
        try:
            payload = client.match(match_id)
        except RuntimeError as exc:
            detail_errors.append({"match_id": match_id, "error": str(exc)})
            continue
        fixture = fixture_index[match_id]
        all_player_rows = flatten_match_player_stats(payload, fixture)
        if all_player_rows:
            matches_with_player_detail += 1
        matched = [row for row in all_player_rows if int(row["player_id"]) in players]
        for row in matched:
            player_matches.append(
                enrich_player_match(row, fixture, players[int(row["player_id"])])
            )
        if matched:
            team_rows_by_match[match_id] = flatten_match_team_stats(payload, fixture)

    summaries = summarize_player_matches(player_matches)
    matched_ids = {int(row["match_id"]) for row in player_matches}
    matched_fixtures = [fixture_index[match_id] for match_id in sorted(matched_ids)]
    matched_team_rows = [
        row
        for match_id in sorted(matched_ids)
        for row in team_rows_by_match.get(match_id, [])
    ]

    print("[3/4] Write normalized international evidence", flush=True)
    write_jsonl(args.output_dir / "fixtures.jsonl", matched_fixtures)
    write_jsonl(args.output_dir / "player_match_stats.jsonl", player_matches)
    write_jsonl(args.output_dir / "player_window_summary.jsonl", summaries)
    write_jsonl(args.output_dir / "match_team_stats.jsonl", matched_team_rows)
    manifest = {
        "version": "clubalpha_international_player_evidence_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "from_date": from_date.isoformat(),
        "as_of": as_of.isoformat(),
        "source": "FotMob public web match feeds",
        "source_scope": "international_current",
        "covered_player_universe": len(players),
        "model_policy": {
            "automatic_weight": 0,
            "allowed_uses": [
                "workload",
                "availability_review",
                "role_and_position_review",
                "recent_condition_context",
                "projected_xi_review",
            ],
            "prohibited_automatic_uses": [
                "club_form_reweighting",
                "player_alpha_regrading",
                "fixture_probability_override",
            ],
        },
    }
    write_json(args.output_dir / "manifest.json", manifest)

    club_players: dict[str, set[int]] = defaultdict(set)
    for row in summaries:
        for club in row.get("covered_clubs") or []:
            club_players[str(club)].add(int(row["player_id"]))
    metric_coverage = {}
    for metric in ("minutes_played", "rating_title", *SUM_METRICS):
        present = sum(metric_value(row, metric) is not None for row in player_matches)
        metric_coverage[metric] = {
            "rows_with_value": present,
            "player_match_rows": len(player_matches),
            "pct": round(100 * present / len(player_matches), 1) if player_matches else 0.0,
        }

    attacking = sorted(
        summaries,
        key=lambda row: (
            -float(row["totals"]["goals"] + row["totals"]["assists"]),
            -float(row["totals"]["expected_goals"] + row["totals"]["expected_assists"]),
            -float(row["minutes"]),
        ),
    )
    creative = sorted(
        summaries,
        key=lambda row: (
            -float(row["totals"]["chances_created"]),
            -float(row["totals"]["passes_into_final_third"]),
            -float(row["minutes"]),
        ),
    )
    audit = {
        **manifest,
        "counts": {
            "queried_days": queried_days,
            "candidate_completed_matches": len(fixture_index),
            "matches_with_player_detail": matches_with_player_detail,
            "matches_with_covered_players": len(matched_ids),
            "covered_player_match_rows": len(player_matches),
            "covered_players_with_appearances": len(summaries),
            "covered_clubs_with_internationals": len(club_players),
            "detail_errors": len(detail_errors),
        },
        "included_leagues": dict(sorted(included_leagues.items())),
        "excluded_international_leagues": dict(
            sorted(excluded_international_leagues.items())
        ),
        "players_with_appearances_by_club": {
            club: len(player_ids) for club, player_ids in sorted(club_players.items())
        },
        "metric_coverage": metric_coverage,
        "high_workload_players": [
            {
                "player": row["player"],
                "covered_clubs": row["covered_clubs"],
                "minutes": row["minutes"],
                "appearances": row["appearances"],
                "last_kickoff_utc": row["last_kickoff_utc"],
            }
            for row in summaries
            if row["workload_band"] == "high"
        ][:30],
        "attacking_leaders": [
            {
                "player": row["player"],
                "covered_clubs": row["covered_clubs"],
                "minutes": row["minutes"],
                "goals": row["totals"]["goals"],
                "assists": row["totals"]["assists"],
                "xg": row["totals"]["expected_goals"],
                "xa": row["totals"]["expected_assists"],
            }
            for row in attacking[:20]
        ],
        "creative_leaders": [
            {
                "player": row["player"],
                "covered_clubs": row["covered_clubs"],
                "minutes": row["minutes"],
                "chances_created": row["totals"]["chances_created"],
                "passes_into_final_third": row["totals"]["passes_into_final_third"],
                "line_breaking_passes": row["totals"]["line_breaking_passes"],
            }
            for row in creative[:20]
        ],
        "detail_errors": detail_errors,
        "warnings": [
            "The current international window is incomplete until October 6.",
            "National-team evidence has zero automatic model weight.",
            "Missing FotMob match metrics remain missing rather than being converted to zero in raw rows.",
            "Only covered players with a published match-stat card appear in the normalized player ledger.",
        ],
    }
    write_json(args.audit, audit)
    print("[4/4] International evidence audit", flush=True)
    print(json.dumps(audit["counts"], indent=2), flush=True)
    return 0 if not detail_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

