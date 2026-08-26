#!/usr/bin/env python3
"""Run Contextual Interaction v1 over an immutable upcoming baseline slate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.contextual_interaction import contextualize_prediction  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "artifacts/prediction_lab/2026-08-24/predictions.jsonl",
    )
    parser.add_argument(
        "--style-snapshot",
        type=Path,
        default=ROOT / "artifacts/style_matchup/2026-08-25/style-matchups.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/contextual-interaction-v1.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts/contextual_interaction/2026-08-26",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite contextual archive: {args.output_dir}"
        )
    baseline = load_jsonl(args.baseline)
    style_snapshot = load_json(args.style_snapshot)
    config = load_json(args.config)
    style_by_team = {row["team"]: row for row in style_snapshot["teams"]}
    outputs = []
    for row in baseline:
        fixture = row["fixture"]
        home = style_by_team.get(fixture["home_team"])
        away = style_by_team.get(fixture["away_team"])
        if home is None or away is None:
            raise ValueError(
                f"Style profile missing for {fixture['home_team']} vs "
                f"{fixture['away_team']}"
            )
        outputs.append(contextualize_prediction(row, home, away, config))
    outputs.sort(key=lambda row: (row["fixture"]["kickoff_utc"], row["fixture"]["match_id"]))

    summary = []
    for row in outputs:
        fixture = row["fixture"]
        base = row["baseline"]
        context = row["contextual"]
        home_direction = row["directional_context"]["home_attack"]
        away_direction = row["directional_context"]["away_attack"]
        summary.append(
            {
                "match_id": fixture["match_id"],
                "kickoff_utc": fixture["kickoff_utc"],
                "fixture": f"{fixture['home_team']} vs {fixture['away_team']}",
                "home_archetype": home_direction["attacker_archetype"],
                "away_archetype": away_direction["attacker_archetype"],
                "base_xg": base["predicted_xg"],
                "contextual_xg": context["predicted_xg"],
                "base_1x2": {
                    key: base["probabilities"][key]
                    for key in ("home_win", "draw", "away_win")
                },
                "contextual_1x2": {
                    key: context["probabilities"][key]
                    for key in ("home_win", "draw", "away_win")
                },
                "probability_change_percentage_points": {
                    key: round(100.0 * row["change"]["probabilities"][key], 3)
                    for key in ("home_win", "draw", "away_win", "btts_yes")
                },
                "home_preferred_route": home_direction["preferred_route"]["label"],
                "away_preferred_route": away_direction["preferred_route"]["label"],
                "home_context_reliability": home_direction["combined_reliability"],
                "away_context_reliability": away_direction["combined_reliability"],
                **row["context_read"],
                "quality_flags": row["quality_flags"],
            }
        )

    report = {
        "report_version": "clubalpha_contextual_next_round_2026_08_26_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": config["status"],
        "fixtures": len(outputs),
        "source_provenance": {
            "baseline": {
                "filename": args.baseline.name,
                "sha256": sha256(args.baseline),
            },
            "style_snapshot": {
                "filename": args.style_snapshot.name,
                "sha256": sha256(args.style_snapshot),
            },
            "config": {
                "filename": args.config.name,
                "sha256": sha256(args.config),
            },
            "fixture_schedule_verified_against": (
                "https://www.premierleague.com/en/news/4678381/"
                "fixture-amendments-for-premier-league-matches-in-august-and-september/"
            ),
        },
        "method": {
            "base_model_unchanged": True,
            "archetype_labels_used_in_math": False,
            "directional": True,
            "continuous": True,
            "reliability_shrunk": True,
            "link": "contextual_xg = base_xg * exp(bounded_context_signal * reliability * maximum_log_sensitivity)",
            "maximum_absolute_log_xg_adjustment": config[
                "maximum_absolute_log_xg_adjustment"
            ],
            "simulations_per_fixture": config["simulation"]["draws"],
            "same_deterministic_seed_as_baseline": True,
            "common_random_numbers_with_baseline": False,
            "probability_deltas_are_unpaired_monte_carlo_comparisons": True,
        },
        "fixtures_summary": summary,
        "decision_boundaries": config["decision_boundaries"],
        "quality_flags": [
            "first_live_contextual_shadow",
            "context_coefficient_not_learned_from_residuals",
            "do_not_use_for_capital_deployment",
        ],
    }
    write_jsonl(args.output_dir / "predictions.jsonl", outputs)
    write_json(args.output_dir / "report.json", report)
    print(
        json.dumps(
            {
                "report_version": report["report_version"],
                "fixtures": report["fixtures"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
