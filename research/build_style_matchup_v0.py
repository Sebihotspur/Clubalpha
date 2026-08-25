#!/usr/bin/env python3
"""Build a frozen Premier League Style Matchup v0 research artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.style_matchup import build_style_matchup_snapshot  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_profiles(path: Path):
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    payload = load_json(path)
    return payload["profiles"] if isinstance(payload, dict) else payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--club-dynamics",
        type=Path,
        default=ROOT / "data/processed/club_dynamics/club_dynamics.jsonl",
    )
    parser.add_argument(
        "--premier-league-alpha",
        type=Path,
        default=ROOT / "reports/premier-league-alpha-snapshot-2026-08-25.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/style_matchup/2026-08-25/style-matchups.json",
    )
    parser.add_argument("--as-of", default="2026-08-25")
    args = parser.parse_args()

    profiles = load_profiles(args.club_dynamics)
    alpha = load_json(args.premier_league_alpha)
    snapshot = build_style_matchup_snapshot(profiles, alpha["clubs"], as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "snapshot_version": snapshot["snapshot_version"],
                "as_of": snapshot["as_of"],
                "teams": len(snapshot["teams"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

