#!/usr/bin/env python3
"""Freeze or verify the dated Premier League round-robin experiment."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.round_robin_archive import (
    hash_files,
    load_jsonl,
    validate_round_robin,
    verify_hashes,
)


ARCHIVE_VERSION = "clubalpha_round_robin_archive_v0"
DEFAULT_AS_OF = "2026-08-25"


def relative_archive_files(archive_dir: str) -> list[str]:
    return [
        f"{archive_dir}/predictions.jsonl",
        f"{archive_dir}/summary.json",
        f"{archive_dir}/README.md",
    ]


SOURCE_FILES = [
    "artifacts/style_matchup/2026-08-25/style-matchups.json",
    "artifacts/prediction_lab/2026-08-24/component-scales.json",
    "artifacts/prediction_lab/2026-08-24/goal-model.json",
    "artifacts/prediction_lab/2026-08-24/report.json",
    "reports/premier-league-alpha-snapshot-2026-08-25.json",
    "config/fixture-state-v1.json",
    "config/prediction-lab-v0.json",
    "config/historical-fixtures-v2.json",
    "research/build_round_robin_v0.py",
    "research/build_style_matchup_v0.py",
    "clubalpha/prediction_lab.py",
    "clubalpha/fixture_state.py",
    "clubalpha/style_matchup.py",
]


def load_and_validate(repo_root: Path, archive_dir: str) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = repo_root / archive_dir
    predictions = load_jsonl(directory / "predictions.jsonl")
    summary = json.loads((directory / "summary.json").read_text())
    validation = validate_round_robin(predictions, summary)
    return summary, validation


def build_manifest(
    *,
    archive_dir: str,
    summary: dict[str, Any],
    validation: dict[str, Any],
    hashes: dict[str, str],
) -> dict[str, Any]:
    results_path = f"{archive_dir}/results.jsonl"
    return {
        "archive_version": ARCHIVE_VERSION,
        "status": "frozen",
        "as_of": summary["as_of"],
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": {
            "competition": "Premier League",
            "format": summary["format"],
            "season": validation["season"],
            "teams": validation["teams"],
            "fixtures": validation["fixtures"],
            "matches_per_team": validation["matches_per_team"],
            "simulations_per_fixture": summary["simulations_per_fixture"],
            "total_match_simulations": summary["total_match_simulations"],
            "outcomes_used_at_freeze": False,
        },
        "model": {
            "round_robin_version": summary["round_robin_version"],
            "probability_model": summary["probability_model"],
            "decision_status": "shadow_only",
            "style_matchup_probability_weight": 0,
        },
        "reconciliation": {
            "join_key": "season|home_team_id|away_team_id",
            "join_fields": ["season", "home_team_id", "away_team_id"],
            "unique_join_keys": validation["unique_join_keys"],
            "synthetic_match_id_is_join_key": False,
            "result_stream": results_path,
            "result_stream_policy": "append_only",
            "required_result_fields": [
                "result_version",
                "recorded_at_utc",
                "season",
                "home_team_id",
                "away_team_id",
                "kickoff_utc",
                "final_home_goals",
                "final_away_goals",
                "outcome",
                "source",
                "source_match_id",
            ],
        },
        "integrity": {
            "algorithm": "sha256",
            "immutable_files": sorted(hashes),
            "hashes": dict(sorted(hashes.items())),
            "manifest_self_hashed": False,
            "append_only_result_stream_hashed": False,
        },
        "evaluation_plan": {
            "primary": ["multiclass_brier_score", "log_loss", "calibration"],
            "secondary": ["1x2_accuracy", "predicted_xg_mae"],
            "challenger": "style_matchup_ablation_at_zero_live_weight",
        },
        "safeguards": [
            "never_regenerate_this_dated_archive_in_place",
            "create_a_new_dated_archive_after_model_adjustments",
            "append_observed_results_without_mutating_predictions",
            "keep_style_matchup_outside_probabilities_until_validated",
            "do_not_deploy_capital_from_this_shadow_experiment",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        default=f"artifacts/round_robin/{DEFAULT_AS_OF}",
        help="repository-relative dated archive directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = ROOT
    archive_dir = args.archive_dir.rstrip("/")
    directory = repo_root / archive_dir
    manifest_path = directory / "manifest.json"
    results_path = directory / "results.jsonl"

    summary, validation = load_and_validate(repo_root, archive_dir)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("archive_version") != ARCHIVE_VERSION:
            raise ValueError("archive manifest version is not supported")
        verify_hashes(repo_root, manifest["integrity"]["hashes"])
        if not results_path.is_file():
            raise FileNotFoundError("append-only result stream is missing")
        print(
            f'Verified frozen archive: {validation["fixtures"]} fixtures, '
            f'{validation["unique_join_keys"]} unique join keys'
        )
        return

    if results_path.exists() and results_path.stat().st_size:
        raise ValueError("refusing to freeze around a non-empty result stream")
    results_path.touch(exist_ok=True)

    frozen_files = relative_archive_files(archive_dir) + SOURCE_FILES
    hashes = hash_files(repo_root, frozen_files)
    manifest = build_manifest(
        archive_dir=archive_dir,
        summary=summary,
        validation=validation,
        hashes=hashes,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f'Frozen archive: {validation["fixtures"]} fixtures, '
        f'{validation["unique_join_keys"]} unique join keys'
    )


if __name__ == "__main__":
    main()
