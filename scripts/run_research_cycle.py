#!/usr/bin/env python3
"""Run result collection, backtesting, and cumulative research learning."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "config/research-loop-2026-27.json",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached FotMob responses instead of refreshing the latest cycle.",
    )
    return parser.parse_args()


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    cycles = registry.get("cycles") or []
    if not cycles:
        raise ValueError("research cycle registry contains no cycles")
    latest = cycles[-1]
    archive = ROOT / latest["contextual_archive"]
    collect = [
        sys.executable,
        str(ROOT / "scripts/collect_contextual_results.py"),
        "--archive-dir",
        str(archive),
        "--season",
        str(registry["season"]),
    ]
    if args.use_cache:
        collect.append("--use-cache")
    run(collect)
    run(
        [
            sys.executable,
            str(ROOT / "research/backtest_contextual_interaction_v1.py"),
            "--archive-dir",
            str(archive),
            "--lineup-snapshot",
            str(ROOT / latest["lineup_snapshot"]),
            "--base-predictions",
            str(ROOT / latest["base_predictions"]),
            "--goal-model-artifact",
            str(ROOT / latest["goal_model_artifact"]),
            "--output",
            str(ROOT / f"reports/contextual-interaction-v1-backtest-{args.as_of}.json"),
        ]
    )
    run(
        [
            sys.executable,
            str(ROOT / "research/run_research_loop_v1.py"),
            "--as-of",
            args.as_of,
            "--registry",
            str(args.registry),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
