#!/usr/bin/env python3
"""Validate and append one observed result to a frozen round-robin ledger."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.round_robin_archive import load_jsonl, validate_results  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ROOT / "artifacts/round_robin/2026-08-25",
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--home-team-id", type=int, required=True)
    parser.add_argument("--away-team-id", type=int, required=True)
    parser.add_argument("--kickoff-utc", required=True)
    parser.add_argument("--home-goals", type=int, required=True)
    parser.add_argument("--away-goals", type=int, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-match-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    predictions_path = args.archive_dir / "predictions.jsonl"
    results_path = args.archive_dir / "results.jsonl"
    manifest_path = args.archive_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("archive must be frozen before results are appended")
    predictions = load_jsonl(predictions_path)
    outcome = (
        "home_win"
        if args.home_goals > args.away_goals
        else "away_win" if args.away_goals > args.home_goals else "draw"
    )
    result = {
        "result_version": "clubalpha_round_robin_result_v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": args.season,
        "home_team_id": args.home_team_id,
        "away_team_id": args.away_team_id,
        "kickoff_utc": args.kickoff_utc,
        "final_home_goals": args.home_goals,
        "final_away_goals": args.away_goals,
        "outcome": outcome,
        "source": args.source,
        "source_match_id": args.source_match_id,
    }
    with results_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = [json.loads(line) for line in handle if line.strip()]
        validate_results(predictions, [*existing, result])
        handle.seek(0, 2)
        handle.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    print(
        f"Appended {args.season}|{args.home_team_id}|{args.away_team_id} "
        f"({args.home_goals}-{args.away_goals})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
