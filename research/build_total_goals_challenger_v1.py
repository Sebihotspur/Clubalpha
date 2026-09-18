#!/usr/bin/env python3
"""Fit and audit the zero-weight total-goals probability challenger."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.fixture_calibration import calibrate_fixture_forecast  # noqa: E402
from clubalpha.research_cycle import load_registered_cycle  # noqa: E402
from clubalpha.total_goals_challenger import (  # noqa: E402
    VERSION,
    apply_challenger,
    evaluate_probabilities,
    fit_competition_artifact,
    historical_observations,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cycle_evidence(
    registry: dict[str, Any], artifact: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations = []
    cycles = []
    for cycle in registry["cycles"]:
        normalized = load_registered_cycle(ROOT, cycle)
        results = {int(row["match_id"]): row for row in normalized["results"]}
        cycle_rows = []
        for prediction in normalized["predictions"]:
            fixture = prediction["fixture"]
            result = results.get(int(fixture["match_id"]))
            if result is None:
                continue
            probabilities = prediction["contextual"]["probabilities"]
            total_xg = float(prediction["contextual"]["predicted_xg"]["total"])
            total_goals = int(result["final_home_goals"]) + int(
                result["final_away_goals"]
            )
            row = {
                "cycle_id": cycle["cycle_id"],
                "prediction_format": cycle.get("prediction_format", "contextual"),
                "match_id": int(fixture["match_id"]),
                "kickoff_utc": fixture["kickoff_utc"],
                "fixture": f'{fixture["home_team"]} vs {fixture["away_team"]}',
                "predicted_total_xg": total_xg,
                "actual_total_goals": total_goals,
                "over_2_5": total_goals > 2,
                "baseline_probability": float(probabilities["over"]["2.5"]),
                "challenger_probability": apply_challenger(
                    total_xg, artifact, "premier_league"
                ),
            }
            observations.append(row)
            cycle_rows.append(row)
        cycles.append(
            {
                "cycle_id": cycle["cycle_id"],
                "prediction_format": cycle.get("prediction_format", "contextual"),
                "metrics": evaluate_probabilities(cycle_rows),
            }
        )
    return observations, cycles


def build_upcoming(
    contextual_path: Path,
    artifact: dict[str, Any],
    calibration_artifact_path: Path,
    calibration_config_path: Path,
) -> list[dict[str, Any]]:
    calibration_artifact = load_json(calibration_artifact_path)
    calibration_config = load_json(calibration_config_path)
    output = []
    for row in load_jsonl(contextual_path):
        fixture = row["fixture"]
        calibrated = calibrate_fixture_forecast(
            {
                "fixture": fixture,
                "predicted_xg": row["contextual"]["predicted_xg"],
                "probabilities": row["contextual"]["probabilities"],
            },
            calibration_artifact,
            calibration_config,
        )
        total_xg = float(calibrated["predicted_xg"]["total"])
        baseline = float(calibrated["probabilities"]["over"]["2.5"])
        challenger = apply_challenger(total_xg, artifact, "premier_league")
        output.append(
            {
                "fixture": fixture,
                "calibrated_predicted_xg": calibrated["predicted_xg"],
                "baseline_over_2_5": round(baseline, 6),
                "challenger_over_2_5": round(challenger, 6),
                "probability_delta": round(challenger - baseline, 6),
                "baseline_direction": "over" if baseline >= 0.5 else "under",
                "challenger_direction": "over" if challenger >= 0.5 else "under",
                "decision_boundaries": {
                    "research_only": True,
                    "changes_frozen_pick": False,
                    "capital_deployment_ready": False,
                },
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/total-goals-challenger-v1.json"
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=ROOT / "data/processed/deep_history/match_team_stats.jsonl",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "config/research-loop-2026-27.json",
    )
    parser.add_argument(
        "--upcoming-contextual",
        type=Path,
        default=ROOT
        / "artifacts/contextual_interaction/2026-09-16-mw5/predictions.jsonl",
    )
    parser.add_argument(
        "--fixture-calibration",
        type=Path,
        default=ROOT / "artifacts/fixture_calibration/2026-09-15/calibration.json",
    )
    parser.add_argument(
        "--fixture-calibration-config",
        type=Path,
        default=ROOT / "config/fixture-calibration-v1.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts/total_goals_challenger/2026-09-16",
    )
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite challenger archive: {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    config = load_json(args.config)
    history = load_jsonl(args.history)
    competitions = []
    for competition in config["competitions"]:
        observations = historical_observations(
            history,
            competition_id=int(competition["competition_id"]),
            before=config["training_cutoff"],
        )
        competitions.append(
            fit_competition_artifact(
                observations,
                key=competition["key"],
                competition_id=int(competition["competition_id"]),
                config=config,
            )
        )
    artifact = {
        "version": VERSION,
        "status": "research_challenger_zero_live_weight",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_cutoff": config["training_cutoff"],
        "method": {
            "target": "P(total goals > 2.5 | predicted total xG)",
            "estimator": "recency-weighted Gaussian kernel with independent-Poisson prior and monotone PAVA projection",
            "parameter_selection": "chronological season-forward validation",
        },
        "competitions": competitions,
        "decision_boundaries": {
            **config["boundaries"],
            "automatic_application": False,
            "probability_validated": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
    }
    registry = load_json(args.registry)
    rows, cycles = cycle_evidence(registry, artifact)
    official_rows = [row for row in rows if row["prediction_format"] == "official_shadow"]
    overall = evaluate_probabilities(rows)
    official = evaluate_probabilities(official_rows)
    activation = config["activation"]
    eligible = (
        len(official_rows) >= int(activation["minimum_official_frozen_fixtures"])
        and official["improvement_positive_is_better"]["brier"] > 0
        and official["improvement_positive_is_better"]["log_loss"] > 0
    )
    evaluation = {
        "version": "clubalpha_total_goals_challenger_v1_evaluation",
        "status": "research_only",
        "frozen_fixture_observations": rows,
        "cycles": cycles,
        "metrics": {"all_frozen": overall, "official_only": official},
        "activation_gate": {
            "minimum_official_frozen_fixtures": int(
                activation["minimum_official_frozen_fixtures"]
            ),
            "observed_official_frozen_fixtures": len(official_rows),
            "brier_improvement_required": True,
            "log_loss_improvement_required": True,
            "eligible_for_promotion": eligible,
        },
    }
    upcoming = build_upcoming(
        args.upcoming_contextual,
        artifact,
        args.fixture_calibration,
        args.fixture_calibration_config,
    )
    write_json(args.output_dir / "artifact.json", artifact)
    write_json(args.output_dir / "evaluation.json", evaluation)
    write_json(args.output_dir / "upcoming-mw5.json", upcoming)
    manifest = {
        "version": "clubalpha_total_goals_challenger_v1_manifest",
        "files": {
            name: sha256(args.output_dir / name)
            for name in ("artifact.json", "evaluation.json", "upcoming-mw5.json")
        },
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (
                args.config,
                args.history,
                args.registry,
                args.upcoming_contextual,
                args.fixture_calibration,
                args.fixture_calibration_config,
            )
        },
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "output": str(args.output_dir.relative_to(ROOT)),
                "training_matches": {
                    row["key"]: row["training_matches"] for row in competitions
                },
                "official_evaluation": official,
                "eligible_for_promotion": eligible,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
