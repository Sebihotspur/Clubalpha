#!/usr/bin/env python3
"""Audit whether locked Alpha grades can support the three role pillars."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.role_aware_alpha import (  # noqa: E402
    PILLAR_METRICS,
    ROLE_ALPHA_VERSION,
    _pillar_raw,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grades", type=Path, required=True)
    parser.add_argument("--minimum-reference-minutes", type=float, default=700.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/role-aware-alpha-v1-audit.json",
    )
    args = parser.parse_args()
    grades = [
        json.loads(line)
        for line in args.grades.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    positions = Counter(str(row.get("scoring_position") or "unknown") for row in grades)
    eligible = [
        row for row in grades if float(row.get("minutes") or 0.0) >= args.minimum_reference_minutes
    ]
    eligible_positions = Counter(
        str(row.get("scoring_position") or "unknown") for row in eligible
    )
    pillars = {}
    for pillar in PILLAR_METRICS:
        by_position = {}
        for position in ("FW", "CM", "FB", "CB", "GK"):
            all_rows = [row for row in grades if row.get("scoring_position") == position]
            reference_rows = [
                row for row in eligible if row.get("scoring_position") == position
            ]
            all_supplied = [
                (row, _pillar_raw(row, pillar)) for row in all_rows
            ]
            reference_supplied = [
                (row, _pillar_raw(row, pillar)) for row in reference_rows
            ]
            by_position[position] = {
                "configured_metrics": list(PILLAR_METRICS[pillar][position]),
                "players": len(all_rows),
                "players_with_pillar": sum(raw is not None for _, (raw, _) in all_supplied),
                "reference_players": len(reference_rows),
                "reference_players_with_pillar": sum(
                    raw is not None for _, (raw, _) in reference_supplied
                ),
                "metric_supply": dict(
                    sorted(
                        Counter(
                            metric
                            for _, (_, supplied) in all_supplied
                            for metric in supplied
                        ).items()
                    )
                ),
            }
        pillars[pillar] = by_position
    report = {
        "version": ROLE_ALPHA_VERSION,
        "source": args.grades.name,
        "player_grade_formula_versions": sorted(
            {str(row.get("formula_version")) for row in grades}
        ),
        "minimum_reference_minutes": args.minimum_reference_minutes,
        "players": len(grades),
        "players_by_alpha_position": dict(sorted(positions.items())),
        "reference_players": len(eligible),
        "reference_players_by_alpha_position": dict(sorted(eligible_positions.items())),
        "pillars": pillars,
        "decision_boundaries": {
            "locked_alpha_formula_changed": False,
            "selection_policy_changed_by_alpha": False,
            "pillar_metrics_are_existing_grade_metrics_only": True,
            "missing_metric_treated_as_zero": False,
            "market_probabilities_created": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("players", "players_by_alpha_position", "reference_players", "reference_players_by_alpha_position")}, indent=2))


if __name__ == "__main__":
    main()
