#!/usr/bin/env python3
"""Pull five cached PL/UCL seasons for historical matchup modelling."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.deep_history import (  # noqa: E402
    competition_seasons,
    dedupe_fixtures,
    normalize_season_fixtures,
)
from clubalpha.fotmob import FotMobClient, flatten_match_team_stats  # noqa: E402


TEAM_METRICS = [
    "goals",
    "expected_goals",
    "shots_on_target",
    "big_chances",
    "total_shots",
    "touches_opp_box",
    "expected_goals_open_play",
    "expected_goals_set_play",
]


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
    output: dict[str, Any] = {}
    for competition in sorted({str(row.get("competition") or "Unknown") for row in rows}):
        members = [row for row in rows if str(row.get("competition") or "Unknown") == competition]
        output[competition] = {
            metric: {
                "team_match_rows_with_value": sum(
                    row.get(f"{metric}_for") is not None for row in members
                ),
                "team_match_rows": len(members),
                "pct": round(
                    100
                    * sum(row.get(f"{metric}_for") is not None for row in members)
                    / len(members),
                    1,
                )
                if members
                else 0.0,
            }
            for metric in TEAM_METRICS
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/deep-history.json")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/cache/fotmob")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "data/processed/deep_history"
    )
    parser.add_argument(
        "--audit", type=Path, default=ROOT / "reports/deep-history-coverage.json"
    )
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-match-details", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--request-interval", type=float, default=None)
    args = parser.parse_args()

    config = load_json(args.config)
    as_of = args.as_of or date.today().isoformat()
    workers = args.workers or int(config["collection"]["workers"])
    request_interval = (
        args.request_interval
        if args.request_interval is not None
        else float(config["collection"]["request_interval_seconds"])
    )
    if workers < 1 or workers > 6:
        raise SystemExit("--workers must be between 1 and 6")

    competitions = competition_seasons(config)
    client = FotMobClient(
        args.cache_dir,
        refresh=args.refresh,
        request_interval=request_interval,
    )
    fixture_sets: list[list[dict[str, Any]]] = []
    competition_audit: list[dict[str, Any]] = []
    competition_errors: list[dict[str, Any]] = []

    print(f"[1/3] Competition-season registries ({len(competitions)})")
    for number, competition in enumerate(competitions, 1):
        print(
            f"  season {number:02d}/{len(competitions):02d}: "
            f"{competition['name']} {competition['season']}"
        )
        try:
            payload = client.league(competition["fotmob_id"], competition["season"])
            fixtures = normalize_season_fixtures(payload, competition, as_of)
            fixture_sets.append(fixtures)
            competition_audit.append(
                {
                    **competition,
                    "finished_fixtures": len(fixtures),
                    "earliest_kickoff_utc": min(
                        (row.get("kickoff_utc") for row in fixtures), default=None
                    ),
                    "latest_kickoff_utc": max(
                        (row.get("kickoff_utc") for row in fixtures), default=None
                    ),
                }
            )
        except RuntimeError as exc:
            competition_errors.append({**competition, "error": str(exc)})

    fixtures = dedupe_fixtures(fixture_sets)
    fixtures_by_id = {int(row["match_id"]): row for row in fixtures}
    match_ids = sorted(fixtures_by_id)
    match_rows: list[dict[str, Any]] = []
    detail_errors: list[dict[str, Any]] = []
    detailed_ids: set[int] = set()

    print(f"[2/3] Team match detail ({len(match_ids)} matches)")
    if not args.skip_match_details:
        worker_state = threading.local()

        def fetch_match(match_id: int) -> tuple[int, list[dict[str, Any]], str | None]:
            worker_client = getattr(worker_state, "client", None)
            if worker_client is None:
                worker_client = FotMobClient(
                    args.cache_dir,
                    refresh=args.refresh,
                    request_interval=request_interval,
                )
                worker_state.client = worker_client
            try:
                payload = worker_client.match(match_id)
                return (
                    match_id,
                    flatten_match_team_stats(payload, fixtures_by_id[match_id]),
                    None,
                )
            except RuntimeError as exc:
                return match_id, [], str(exc)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(fetch_match, match_ids)
            for number, (match_id, rows, error) in enumerate(results, 1):
                if error:
                    detail_errors.append({"match_id": match_id, "error": error})
                else:
                    detailed_ids.add(match_id)
                    match_rows.extend(rows)
                if number == 1 or number % 100 == 0 or number == len(match_ids):
                    print(f"  match {number:04d}/{len(match_ids):04d}")

    print("[3/3] Normalized datasets and coverage audit")
    missing_ids = sorted(set(match_ids) - detailed_ids) if not args.skip_match_details else []
    counts = {
        "competition_seasons": len(competitions),
        "finished_fixtures": write_jsonl(args.output_dir / "fixtures.jsonl", fixtures),
        "matches_with_team_detail": len(detailed_ids),
        "matches_without_team_detail": len(missing_ids),
        "team_detail_coverage_pct": round(100 * len(detailed_ids) / len(match_ids), 1)
        if match_ids and not args.skip_match_details
        else None,
        "team_match_rows": write_jsonl(
            args.output_dir / "match_team_stats.jsonl", match_rows
        ),
    }
    season_counts = Counter(
        (str(row.get("competition")), str(row.get("season"))) for row in fixtures
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "version": config["version"],
        "generated_at_utc": generated_at,
        "as_of": as_of,
        "source": config["source"],
        "source_status": "unofficial_undocumented",
        "sampling_policy": "Complete team-match detail for five PL and UCL seasons; no historical player rows",
        "counts": counts,
    }
    audit = {
        **manifest,
        "competition_seasons": competition_audit,
        "fixture_counts": {
            f"{competition} {season}": count
            for (competition, season), count in sorted(season_counts.items())
        },
        "metric_coverage": metric_coverage(match_rows),
        "competition_errors": competition_errors,
        "match_detail_errors": detail_errors,
        "missing_match_detail_sample": missing_ids[:30],
        "warnings": [
            "The deep archive contains team-match context only; Player Quality continues to use its separately versioned player evidence.",
            "FotMob is an undocumented source, so every season and match response is cached and audited.",
            "Older history must be decayed and cannot be interpreted as current team strength.",
        ],
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "coverage.json", audit)
    write_json(args.audit, audit)
    print(json.dumps(counts, indent=2))
    return 0 if not competition_errors and not detail_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
