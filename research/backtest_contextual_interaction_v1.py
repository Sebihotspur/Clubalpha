#!/usr/bin/env python3
"""Score the frozen base and Holy Grail forecasts on completed fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.contextual_backtest import (  # noqa: E402
    evaluate_contextual_backtest,
    evaluate_goal_coefficient_ablation,
)
from clubalpha.research_cycle import normalize_cycle_data  # noqa: E402
from clubalpha.round_robin_archive import load_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ROOT / "artifacts/contextual_interaction/2026-08-26",
    )
    parser.add_argument(
        "--lineup-snapshot",
        type=Path,
        default=ROOT / "reports/premier-league-alpha-snapshot-2026-08-25.json",
    )
    parser.add_argument(
        "--base-predictions",
        type=Path,
        default=ROOT / "artifacts/prediction_lab/2026-08-24/predictions.jsonl",
    )
    parser.add_argument(
        "--goal-model-artifact",
        type=Path,
        default=ROOT / "artifacts/prediction_lab/2026-08-24/goal-model.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "reports/contextual-interaction-v1-backtest-2026-08-31.json",
    )
    parser.add_argument(
        "--prediction-format",
        choices=("contextual", "official_shadow"),
        default="contextual",
    )
    return parser.parse_args()


def relative_source(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def main() -> int:
    args = parse_args()
    raw_predictions = load_jsonl(args.archive_dir / "predictions.jsonl")
    raw_results = load_jsonl(args.archive_dir / "results.jsonl")
    raw_snapshot = json.loads(args.lineup_snapshot.read_text(encoding="utf-8"))
    raw_base_predictions = load_jsonl(args.base_predictions)
    cycle = normalize_cycle_data(
        raw_predictions,
        raw_results,
        raw_base_predictions,
        raw_snapshot,
        prediction_format=args.prediction_format,
    )
    predictions = cycle["predictions"]
    results = cycle["results"]
    snapshot = cycle["lineup_snapshot"]
    base_predictions = cycle["base_predictions"]
    goal_model_artifact = json.loads(
        args.goal_model_artifact.read_text(encoding="utf-8")
    )
    evaluation = evaluate_contextual_backtest(
        predictions,
        results,
        lineup_snapshot=snapshot,
    )
    structural = [
        row["fixture"]
        for row in evaluation["fixtures"]
        if row["review_class"] == "structural_miss"
    ]
    lineup = evaluation["lineup_projection"] or {}
    dispersion = evaluation["diagnostics"]["goal_environment_dispersion"]
    route_coverage = evaluation["diagnostics"]["preferred_route_coverage"]
    coefficient_ablation = evaluate_goal_coefficient_ablation(
        base_predictions,
        results,
        goal_model_artifact,
    )
    report = {
        "backtest_version": "clubalpha_contextual_interaction_v1_backtest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "prediction_freeze_date": str(
            raw_predictions[0].get("as_of_utc")
            or raw_predictions[0].get("fixture", {}).get("kickoff_utc")
            or "unknown"
        )[:10],
        "status": "partial_shadow_backtest",
        "sources": {
            "predictions": str(
                relative_source(args.archive_dir / "predictions.jsonl")
            ),
            "results": relative_source(args.archive_dir / "results.jsonl"),
            "lineup_snapshot": relative_source(args.lineup_snapshot),
            "base_predictions": relative_source(args.base_predictions),
            "goal_model_artifact": relative_source(args.goal_model_artifact),
            "observed_match_data": "FotMob final scores, expected goals, team stats, and declared lineups",
            "score_crosscheck": sorted(
                {
                    str(row.get("source_url"))
                    for row in raw_results
                    if row.get("source_url")
                }
            ),
        },
        "interpretation_rules": {
            "outcomes_and_xg_are_scored_separately": True,
            "xg_process_draw_gap": evaluation["sample"][
                "xg_process_draw_threshold"
            ],
            "positive_improvement_means_holy_grail_beat_base": True,
            "multiclass_brier_range": [0.0, 2.0],
            "lower_is_better_except_accuracy": True,
        },
        **evaluation,
        "pre_match_goal_coefficient_ablation": coefficient_ablation,
        "audit_read": {
            "structural_review_queue": structural,
            "evidence_findings": [
                (
                    f"The frozen XI averaged {lineup.get('mean_xi_hits_of_11', 0):.2f}/11 "
                    "starters; selection error still reaches Player Alpha before kickoff."
                ),
                (
                    "Observed match xG totals spanned "
                    f"{dispersion['observed_xg_total']['minimum']:.2f}-"
                    f"{dispersion['observed_xg_total']['maximum']:.2f}, while the base "
                    "forecast spanned only "
                    f"{dispersion['baseline_predicted_xg_total']['minimum']:.2f}-"
                    f"{dispersion['baseline_predicted_xg_total']['maximum']:.2f}; "
                    "the goal environment is over-compressed in this sample."
                ),
                (
                    f"Only {route_coverage['covered_routes']}/"
                    f"{route_coverage['known_routes']} route families became preferred; "
                    f"missing {', '.join(route_coverage['missing'])}."
                ),
                (
                    "The best side-xG MAE among coefficient choices frozen before "
                    "kickoff is "
                    f"{coefficient_ablation['best_side_xg_mae_candidate']}; this "
                    "result does not fit a new coefficient or authorize a change."
                ),
            ],
            "coefficient_action": "hold_at_shadow_value",
            "capital_action": "zero_allocation",
            "next_iteration": (
                "Audit the route and lineup assumptions behind structural misses; "
                "do not refit the context coefficient on this partial sample."
            ),
        },
        "decision_boundaries": {
            "base_weights_changed": False,
            "context_coefficient_changed": False,
            "predictions_mutated": False,
            "sample_sufficient_for_calibration": False,
            "capital_deployment_ready": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    metrics = report["metrics"]
    print(
        f"Scored {report['sample']['matches']}/"
        f"{report['validation']['frozen_fixtures']} fixtures."
    )
    print("Base:", metrics["baseline"])
    print("Holy Grail:", metrics["contextual"])
    print("Improvement:", metrics["holy_grail_improvement_positive_is_better"])
    print("Structural review:", structural)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
