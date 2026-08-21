#!/usr/bin/env python3
"""Build dated squad hierarchy, expected-minute priors, and a baseline XI."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.squad_selection import build_squad_selection_priors  # noqa: E402


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
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


def _example(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": row["team_id"],
        "shape_prior": row["shape_prior"],
        "evidence": row["evidence"],
        "expected_starting_xi_prior": row["expected_starting_xi_prior"],
        "unavailable_players": [
            {
                "player_id": player["player_id"],
                "player": player["player"],
                "scoring_position": player["scoring_position"],
                "baseline_expected_minutes": player["baseline_expected_minutes"],
                "expected_minutes_prior": player["expected_minutes_prior"],
            }
            for player in row["players"]
            if player["availability_status"] == "unavailable"
        ],
        "quality_flags": row["quality_flags"],
    }


def build_audit(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    flags = Counter(flag for row in rows for flag in row["quality_flags"])
    minute_sum_failures = [
        {
            "team_id": row["team_id"],
            "team": row["team"],
            "expected_minutes": round(
                sum(player["expected_minutes_prior"] for player in row["players"]), 3
            ),
            "reason": (
                "no_selection_evidence"
                if "no_selection_evidence" in row["quality_flags"]
                else "unexpected_minute_total"
            ),
        }
        for row in rows
        if abs(
            sum(player["expected_minutes_prior"] for player in row["players"])
            - float(config["expected_team_minutes"])
        )
        > 0.01
    ]
    examples = {
        row["team"]: _example(row)
        for row in rows
        if row["team"]
        in {
            "Arsenal",
            "Chelsea",
            "Manchester City",
            "Coventry City",
            "Shakhtar Donetsk",
        }
    }
    return {
        "selection_prior_version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": rows[0]["as_of"] if rows else None,
        "counts": {
            "teams": len(rows),
            "lineup_prior_ready": sum(
                row["decision_boundaries"]["lineup_prior_ready"] for row in rows
            ),
            "teams_with_recent_match_detail": sum(
                row["evidence"]["recent_matches"] > 0 for row in rows
            ),
            "teams_with_exact_recent_lineup": sum(
                row["evidence"]["exact_lineup_matches"] > 0 for row in rows
            ),
            "teams_using_default_shape": sum(
                row["shape_prior"]["used_default_shape"] for row in rows
            ),
            "players": sum(len(row["players"]) for row in rows),
            "unavailable_players": sum(
                player["availability_status"] == "unavailable"
                for row in rows
                for player in row["players"]
            ),
            "questionable_players": sum(
                player["availability_status"] == "questionable"
                for row in rows
                for player in row["players"]
            ),
            "teams_without_selection_evidence": sum(
                "no_selection_evidence" in row["quality_flags"] for row in rows
            ),
            "teams_with_availability_adjustment": sum(
                row["decision_boundaries"]["availability_adjustment_applied"]
                for row in rows
            ),
        },
        "quality_flags": dict(sorted(flags.items())),
        "expected_minute_sum_exceptions": minute_sum_failures,
        "decision_boundaries": config["decision_boundaries"],
        "examples": examples,
        "warnings": [
            "The XI is a dated squad-selection prior, not a fixture-specific or confirmed lineup.",
            "Only FotMob-declared starter flags count as starts; minutes never infer starter status.",
            "Questionable and unknown injury cases remain available in the baseline and stay flagged.",
            "Alpha Ability is attached for downstream player-impact analysis and never selects the XI.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/squad-selection-prior-v1.json",
    )
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=ROOT / "data/processed/foundation",
    )
    parser.add_argument(
        "--player-grades",
        type=Path,
        default=ROOT / "data/processed/player_quality_v2/player_grades.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/squad_selection_prior",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/squad-selection-prior-v1-audit.json",
    )
    parser.add_argument("--as-of", default=None, help="Inclusive YYYY-MM-DD snapshot date.")
    args = parser.parse_args()

    print("[1/4] Load squad, grades, and recent player-match evidence")
    config = load_json(args.config)
    coverage = load_json(args.foundation_dir / "coverage.json")
    as_of = date.fromisoformat(args.as_of or coverage["as_of"])
    teams = load_json(args.foundation_dir / "teams.json")
    squads = load_jsonl(args.foundation_dir / "squads.jsonl")
    grades = load_jsonl(args.player_grades)
    current_rows = load_jsonl(args.foundation_dir / "current_match_player_stats.jsonl")
    preseason_rows = load_jsonl(args.foundation_dir / "preseason_match_player_stats.jsonl")

    print("[2/4] Build recent selection evidence and previous-season workload prior")
    rows = build_squad_selection_priors(
        teams,
        squads,
        grades,
        current_rows,
        preseason_rows,
        as_of,
        config,
    )
    if len(rows) != len(teams):
        raise RuntimeError(f"Selection prior emitted {len(rows)} rows for {len(teams)} teams")

    print("[3/4] Write ignored player-level snapshot")
    count = write_jsonl(args.output_dir / "squad_selection_prior.jsonl", rows)
    write_json(
        args.output_dir / "manifest.json",
        {
            "selection_prior_version": config["version"],
            "as_of": as_of.isoformat(),
            "inputs": {
                "foundation_dir": str(args.foundation_dir),
                "player_grades": str(args.player_grades),
            },
            "outputs": {"team_rows": count},
            "fixture_specific": False,
            "projection_ready": False,
        },
    )

    print("[4/4] Audit")
    audit = build_audit(rows, config)
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
