#!/usr/bin/env python3
"""Build the evidence-shrunk fixture calibration used by future shadow slates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fixture_calibration import (  # noqa: E402
    build_calibration_observations,
    calibrate_fixture_forecast,
    fit_fixture_calibration,
)
from clubalpha.research_cycle import load_registered_cycle  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "config/research-loop-2026-27.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/fixture-calibration-v1.json",
    )
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def brier(probabilities: dict[str, float], outcome: str) -> float:
    return sum(
        (float(probabilities[key]) - float(key == outcome)) ** 2
        for key in ("home_win", "draw", "away_win")
    )


def log_loss(probabilities: dict[str, float], outcome: str) -> float:
    return -math.log(max(1e-12, float(probabilities[outcome])))


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"matches": 0}
    return {
        "matches": len(rows),
        "one_x_two_brier": round(
            sum(brier(row["probabilities"], row["outcome"]) for row in rows)
            / len(rows),
            6,
        ),
        "one_x_two_log_loss": round(
            sum(log_loss(row["probabilities"], row["outcome"]) for row in rows)
            / len(rows),
            6,
        ),
        "top_pick_accuracy": round(
            sum(
                max(
                    ("home_win", "draw", "away_win"),
                    key=row["probabilities"].get,
                )
                == row["outcome"]
                for row in rows
            )
            / len(rows),
            6,
        ),
        "home_probability_leader_rate": round(
            sum(
                max(
                    ("home_win", "draw", "away_win"),
                    key=row["probabilities"].get,
                )
                == "home_win"
                for row in rows
            )
            / len(rows),
            6,
        ),
        "mean_draw_probability": round(
            sum(row["probabilities"]["draw"] for row in rows) / len(rows),
            6,
        ),
    }


def _forecast(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture": {
            key: observation[key]
            for key in (
                "match_id",
                "kickoff_utc",
                "home_team_id",
                "home_team",
                "away_team_id",
                "away_team",
            )
        },
        "predicted_xg": {
            **observation["predicted_xg"],
            "total": sum(observation["predicted_xg"].values()),
        },
        "probabilities": observation["probabilities"],
    }


def calibration_audit(
    observations: list[dict[str, Any]],
    artifact: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    baseline = [
        {"probabilities": row["probabilities"], "outcome": row["outcome"]}
        for row in observations
    ]
    replay = []
    draw_zone = []
    for row in observations:
        calibrated = calibrate_fixture_forecast(
            _forecast(row), artifact, config, enforce_chronology=False
        )
        replay.append(
            {"probabilities": calibrated["probabilities"], "outcome": row["outcome"]}
        )
        if calibrated["calibration_read"]["draw_zone"]:
            draw_zone.append(
                {
                    "match_id": row["match_id"],
                    "fixture": f"{row['home_team']} vs {row['away_team']}",
                    "outcome": row["outcome"],
                    "draw_probability": calibrated["probabilities"]["draw"],
                    "correct_draw_flag": row["outcome"] == "draw",
                }
            )
    return {
        "interpretation": "same-sample sensitivity only; not validation",
        "baseline": score(baseline),
        "calibrated": score(replay),
        "draw_zone": {
            "flagged": len(draw_zone),
            "actual_draws_flagged": sum(row["correct_draw_flag"] for row in draw_zone),
            "rows": draw_zone,
        },
    }


def chronological_audit(
    cycle_observations: list[list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    baseline = []
    calibrated = []
    training = []
    evaluated_cycles = 0
    for index, holdout in enumerate(cycle_observations):
        if index == 0:
            training.extend(holdout)
            continue
        if len(training) < int(config["minimum_training_matches"]):
            training.extend(holdout)
            continue
        artifact = fit_fixture_calibration(
            training,
            config,
            as_of=str(holdout[0]["kickoff_utc"])[:10],
        )
        evaluated_cycles += 1
        for row in holdout:
            baseline.append(
                {"probabilities": row["probabilities"], "outcome": row["outcome"]}
            )
            forecast = calibrate_fixture_forecast(_forecast(row), artifact, config)
            calibrated.append(
                {"probabilities": forecast["probabilities"], "outcome": row["outcome"]}
            )
        training.extend(holdout)
    return {
        "interpretation": "cycle-forward; each calibration uses only earlier cycles",
        "evaluated_cycles": evaluated_cycles,
        "baseline": score(baseline),
        "calibrated": score(calibrated),
    }


def write_once(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"refusing to overwrite changed calibration file: {path}")
        return
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    registry = load_json(args.registry)
    config = load_json(args.config)
    all_observations = []
    cycle_observations = []
    cycle_ids = []
    for cycle in registry["cycles"]:
        normalized = load_registered_cycle(ROOT, cycle)
        observations = build_calibration_observations(
            normalized["predictions"], normalized["results"]
        )
        cycle_ids.append(cycle["cycle_id"])
        cycle_observations.append(observations)
        all_observations.extend(observations)
    artifact = fit_fixture_calibration(all_observations, config, as_of=args.as_of)
    audit = {
        "version": "clubalpha_fixture_calibration_audit_v1",
        "generated_at_utc": f"{args.as_of}T00:00:00+00:00",
        "as_of": args.as_of,
        "cycle_ids": cycle_ids,
        "training_matches": len(all_observations),
        "same_sample_sensitivity": calibration_audit(
            all_observations, artifact, config
        ),
        "chronological_audit": chronological_audit(cycle_observations, config),
        "decision_boundaries": {
            "same_sample_metrics_are_validation": False,
            "core_architecture_changed": False,
            "player_alpha_changed": False,
            "base_weights_changed": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
    }
    output = args.output_dir or ROOT / "artifacts/fixture_calibration" / args.as_of
    output.mkdir(parents=True, exist_ok=True)
    artifact_path = output / "calibration.json"
    audit_path = output / "audit.json"
    readme_path = output / "README.md"
    write_once(
        artifact_path,
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
    )
    write_once(audit_path, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    readme = (
        "# Fixture Calibration v1\n\n"
        f"As of: {args.as_of}\n\n"
        "This shadow-only layer shrinks the current league home-xG ratio and "
        "draw frequency toward strong neutral priors. It identifies draw-risk "
        "zones and waits for five home plus five away observations before a "
        "team-specific venue effect can activate. It does not change Player "
        "Alpha, the 60/30/10 base, contextual coefficients, frozen predictions, "
        "or capital authorization.\n"
    )
    write_once(readme_path, readme)
    manifest = {
        "version": "clubalpha_fixture_calibration_archive_v1",
        "as_of": args.as_of,
        "files": {
            "calibration.json": sha256(artifact_path),
            "audit.json": sha256(audit_path),
            "README.md": sha256(readme_path),
        },
        "inputs": {
            str(args.registry.relative_to(ROOT)): sha256(args.registry),
            str(args.config.relative_to(ROOT)): sha256(args.config),
        },
        "implementation": {
            "clubalpha/fixture_calibration.py": sha256(
                ROOT / "clubalpha/fixture_calibration.py"
            ),
            "research/build_fixture_calibration_v1.py": sha256(Path(__file__)),
        },
    }
    write_once(
        output / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    print(
        f"Fixture calibration ready: {len(all_observations)} completed matches, "
        f"venue correction {artifact['league_venue']['applied_log_ratio_correction']:+.4f}, "
        f"draw logit correction {artifact['draw_calibration']['applied_logit_correction']:+.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
