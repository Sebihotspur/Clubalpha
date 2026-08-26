#!/usr/bin/env python3
"""Freeze or verify the dated Contextual Interaction v1 shadow slate."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_VERSION = "clubalpha_contextual_interaction_archive_v1"
ARCHIVE_DIR = "artifacts/contextual_interaction/2026-08-26"

IMMUTABLE_FILES = [
    f"{ARCHIVE_DIR}/predictions.jsonl",
    f"{ARCHIVE_DIR}/report.json",
    f"{ARCHIVE_DIR}/README.md",
    "artifacts/prediction_lab/2026-08-24/predictions.jsonl",
    "artifacts/style_matchup/2026-08-25/style-matchups.json",
    "config/contextual-interaction-v1.json",
    "clubalpha/contextual_interaction.py",
    "clubalpha/style_matchup.py",
    "research/run_contextual_next_round_v1.py",
    "scripts/freeze_contextual_interaction_archive.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_archive() -> dict[str, Any]:
    archive = ROOT / ARCHIVE_DIR
    predictions = load_jsonl(archive / "predictions.jsonl")
    report = json.loads((archive / "report.json").read_text(encoding="utf-8"))
    if len(predictions) != 10 or report.get("fixtures") != 10:
        raise ValueError("contextual archive must contain exactly ten fixtures")
    prediction_ids = [row["fixture"]["match_id"] for row in predictions]
    report_ids = [row["match_id"] for row in report["fixtures_summary"]]
    if len(set(prediction_ids)) != 10 or prediction_ids != report_ids:
        raise ValueError("prediction and report fixture identities do not reconcile")
    if any(
        row["decision_boundaries"]["capital_deployment_ready"]
        for row in predictions
    ):
        raise ValueError("capital deployment must remain disabled in this archive")
    return {"fixtures": len(predictions), "unique_match_ids": len(set(prediction_ids))}


def hashes() -> dict[str, str]:
    missing = [name for name in IMMUTABLE_FILES if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"immutable files missing: {missing}")
    return {name: sha256(ROOT / name) for name in sorted(IMMUTABLE_FILES)}


def main() -> None:
    archive = ROOT / ARCHIVE_DIR
    manifest_path = archive / "manifest.json"
    results_path = archive / "results.jsonl"
    validation = validate_archive()

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("archive_version") != ARCHIVE_VERSION:
            raise ValueError("contextual archive manifest version is not supported")
        current = hashes()
        if current != manifest["integrity"]["hashes"]:
            changed = sorted(
                name
                for name in set(current) | set(manifest["integrity"]["hashes"])
                if current.get(name) != manifest["integrity"]["hashes"].get(name)
            )
            raise ValueError(f"frozen contextual archive changed: {changed}")
        if not results_path.is_file():
            raise FileNotFoundError("append-only result stream is missing")
        print(
            f"Verified frozen contextual archive: {validation['fixtures']} fixtures, "
            f"{validation['unique_match_ids']} unique match ids"
        )
        return

    if results_path.exists() and results_path.stat().st_size:
        raise ValueError("refusing to freeze around a non-empty result stream")
    results_path.touch(exist_ok=True)
    manifest = {
        "archive_version": ARCHIVE_VERSION,
        "status": "frozen_shadow",
        "as_of": "2026-08-26",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": {
            **validation,
            "competition": "Premier League",
            "simulations_per_fixture": 50000,
            "outcomes_used_at_freeze": False,
        },
        "model": {
            "base_fixture_weights": {
                "club_form": 0.60,
                "projected_xi_player_quality": 0.30,
                "historical_fixture_residual": 0.10,
            },
            "context_directional": True,
            "archetype_labels_used_in_math": False,
            "context_coefficient_learned": False,
            "capital_deployment_allowed": False,
        },
        "integrity": {
            "algorithm": "sha256",
            "hashes": hashes(),
            "manifest_self_hashed": False,
            "append_only_result_stream_hashed": False,
        },
        "safeguards": [
            "never_regenerate_this_dated_archive_in_place",
            "append_observed_results_without_mutating_predictions",
            "fit_context_only_on_earlier_residuals",
            "do_not_deploy_capital_from_this_shadow_experiment",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Frozen contextual archive: {validation['fixtures']} fixtures, "
        f"{validation['unique_match_ids']} unique match ids"
    )


if __name__ == "__main__":
    main()
