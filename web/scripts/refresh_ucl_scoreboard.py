#!/usr/bin/env python3
"""Capture the public UCL scoreboard for display only, never as forecasts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import FotMobClient, league_matches, normalize_fixture  # noqa: E402


def scoreboard(rows, *, matchday, season, captured_at):
    matches = []
    for raw in rows:
        row = normalize_fixture(raw, source_scope="champions_league_current")
        if str(row["round"]) != str(matchday):
            continue
        matches.append({
            **{key: row[key] for key in (
                "match_id", "kickoff_utc", "home_team", "away_team",
            )},
            "status": (
                "postponed" if row["cancelled"] else
                "final" if row["finished"] else
                "in_progress" if row["started"] else "scheduled"
            ),
            "score": row["score"] if row["finished"] else None,
        })
    if len(matches) != 18 or len({row["match_id"] for row in matches}) != 18:
        raise ValueError("expected 18 unique league-phase fixtures")
    if any(not row["kickoff_utc"] or not row["home_team"] or not row["away_team"] or
           (row["status"] == "final" and not row["score"]) for row in matches):
        raise ValueError("incomplete UCL scoreboard")
    return {
        "competition": "Champions League",
        "season": season,
        "matchday": matchday,
        "captured_at_utc": captured_at,
        "source_url": "https://www.fotmob.com/leagues/42/matches/champions-league",
        "fixtures": sorted(matches, key=lambda row: (row["kickoff_utc"], row["home_team"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matchday", type=int, choices=range(1, 9), required=True)
    parser.add_argument("--season", default="2026/2027")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new dated capture path; existing snapshots are immutable")
    with TemporaryDirectory(prefix="clubalpha-ucl-scoreboard-") as cache:
        raw = FotMobClient(Path(cache), refresh=True).league(42, args.season)
    payload = scoreboard(
        league_matches(raw),
        matchday=args.matchday,
        season=args.season,
        captured_at=datetime.now(timezone.utc).isoformat(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Matchday {args.matchday}: {sum(row['status'] == 'final' for row in payload['fixtures'])}/18 final")


if __name__ == "__main__":
    main()
