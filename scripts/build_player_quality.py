#!/usr/bin/env python3
"""Build WCALPHA-compatible attacker and defender Alpha Ability grades."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.player_quality import (  # noqa: E402
    build_player_features,
    build_quality_audit,
    score_population,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=ROOT / "data/processed/foundation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/player_quality",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/player-quality-wcalpha-v1.json",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/player-quality-audit.json",
    )
    args = parser.parse_args()

    required = {
        "squads": args.foundation_dir / "squads.jsonl",
        "teams": args.foundation_dir / "teams.json",
        "historical player-match stats": args.foundation_dir / "historical_match_player_stats.jsonl",
        "season player stats": args.foundation_dir / "season_player_stats.jsonl",
    }
    missing = [f"{label}: {path}" for label, path in required.items() if not path.exists()]
    if missing:
        raise SystemExit("Missing foundation inputs. Run pull_fotmob_foundation.py first:\n" + "\n".join(missing))

    print("[1/4] Load normalized FotMob foundation")
    config = load_json(args.config)
    squads = load_jsonl(required["squads"])
    teams = load_json(required["teams"])
    historical_rows = load_jsonl(required["historical player-match stats"])
    season_rows = load_jsonl(required["season player stats"])

    print("[2/4] Aggregate canonical current-player features")
    features = build_player_features(squads, teams, historical_rows, season_rows, config)
    feature_count = write_jsonl(args.output_dir / "player_features.jsonl", features)

    print("[3/4] Score WCALPHA attacker, centre-back, and fullback populations")
    grades = score_population(features, config)
    grades.sort(key=lambda row: (row["scoring_position"], -row["alpha_ability_z"], row["player"]))
    grade_count = write_jsonl(args.output_dir / "player_grades.jsonl", grades)

    print("[4/4] Write quality audit")
    audit = build_quality_audit(features, grades, config)
    audit["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    audit["inputs"] = {
        "squad_rows": len(squads),
        "historical_match_player_rows": len(historical_rows),
        "season_player_stat_rows": len(season_rows),
    }
    write_json(args.audit, audit)
    write_json(
        args.output_dir / "manifest.json",
        {
            "generated_at_utc": audit["generated_at_utc"],
            "formula_version": config["version"],
            "feature_rows": feature_count,
            "grade_rows": grade_count,
            "inputs": audit["inputs"],
        },
    )

    print(f"Features: {feature_count}")
    print(f"Grades: {grade_count}")
    print(f"Ranking eligible: {audit['ranking_eligible_players']}")
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
