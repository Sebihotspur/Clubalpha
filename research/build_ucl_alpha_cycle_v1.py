#!/usr/bin/env python3
"""Join completed UCL learning with an uncalibrated upcoming Alpha slate.

The football stack is shared with the Premier League: projected-XI Player
Alpha, 60/30/10 Fixture Intelligence, Contextual Interaction and the selective
decision policy.  UCL calibration remains deliberately separate.  Until a
chronological UCL forecast sample exists, policy outputs are research
candidates rather than promoted calls.
"""

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

from clubalpha.decision_policy import evaluate_side, evaluate_total  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def raw_ucl_forecast(
    contextual: dict[str, Any], calibration_config: dict[str, Any]
) -> dict[str, Any]:
    """Expose contextual probabilities without pretending UCL calibration."""

    model = contextual["contextual"]
    probabilities = model["probabilities"]
    side_probability = max(
        float(probabilities["home_win"]), float(probabilities["away_win"])
    )
    draw_probability = float(probabilities["draw"])
    draw = calibration_config["draw"]
    draw_zone = bool(
        abs(side_probability - draw_probability)
        <= float(draw["draw_zone_max_probability_gap"])
        and side_probability <= float(draw["draw_zone_max_side_probability"])
    )
    return {
        "fixture": contextual["fixture"],
        "predicted_xg": model["predicted_xg"],
        "probabilities": probabilities,
        "calibration_read": {
            "draw_zone": draw_zone,
            "goal_environment_log_correction": 0.0,
            "ucl_specific_calibration_applied": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--matchday", type=int, required=True)
    parser.add_argument("--matchday-review", type=Path, action="append", required=True)
    parser.add_argument("--alpha", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--contextual", type=Path, required=True)
    parser.add_argument(
        "--domestic-coverage",
        type=Path,
        default=ROOT / "reports/domestic-current-coverage.json",
    )
    parser.add_argument(
        "--club-form-audit",
        type=Path,
        default=ROOT / "reports/club-form-v1-audit.json",
    )
    parser.add_argument(
        "--decision-config",
        type=Path,
        default=ROOT / "config/decision-policy-v1.json",
    )
    parser.add_argument(
        "--calibration-config",
        type=Path,
        default=ROOT / "config/fixture-calibration-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reviews = [load_json(path) for path in args.matchday_review]
    if any(row["status"] != "complete" for row in reviews):
        raise ValueError("UCL catch-up requires complete matchday reviews")
    if len({int(row["matchday"]) for row in reviews}) != len(reviews):
        raise ValueError("UCL catch-up matchdays must be unique")
    alpha = load_json(args.alpha)
    if alpha.get("as_of") != args.as_of:
        raise ValueError("UCL Alpha snapshot date does not match cycle date")
    baseline = load_jsonl(args.baseline)
    contextual = load_jsonl(args.contextual)
    domestic_coverage = load_json(args.domestic_coverage)
    club_form_audit = load_json(args.club_form_audit)
    if domestic_coverage.get("as_of") != args.as_of:
        raise ValueError("foreign domestic coverage date does not match cycle date")
    if club_form_audit.get("as_of") != args.as_of:
        raise ValueError("Club Form audit date does not match cycle date")
    league_strength = (
        (club_form_audit.get("normalisation") or {}).get("league_strength") or {}
    )
    if not league_strength.get("enabled"):
        raise ValueError("UCL cycle requires league-strength-adjusted Club Form")
    baseline_by_id = {int(row["fixture"]["match_id"]): row for row in baseline}
    contextual_by_id = {
        int(row["fixture"]["match_id"]): row for row in contextual
    }
    if set(baseline_by_id) != set(contextual_by_id) or len(baseline_by_id) != 18:
        raise ValueError("UCL base and context must reconcile to 18 fixtures")
    if any(int(row["fixture"]["round"]) != args.matchday for row in baseline):
        raise ValueError("UCL cycle contains the wrong matchday")

    decision_config = load_json(args.decision_config)
    calibration_config = load_json(args.calibration_config)
    predictions = []
    for match_id in sorted(
        baseline_by_id,
        key=lambda value: (
            baseline_by_id[value]["fixture"]["kickoff_utc"], value
        ),
    ):
        base = baseline_by_id[match_id]
        context = contextual_by_id[match_id]
        raw = raw_ucl_forecast(context, calibration_config)
        side = evaluate_side(base, context, raw, decision_config)
        total = evaluate_total(raw, decision_config)
        fixture = base["fixture"]
        predictions.append(
            {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "predicted_xg": raw["predicted_xg"],
                "probabilities": raw["probabilities"],
                "side_research_candidate": side,
                "total_research_candidate": total,
                "context_verdict": context["context_read"]["verdict"],
                "home_preferred_route": context["directional_context"][
                    "home_attack"
                ]["preferred_route"],
                "away_preferred_route": context["directional_context"][
                    "away_attack"
                ]["preferred_route"],
                "ucl_calibrated": False,
                "final_call_eligible": False,
            }
        )

    aggregates = [row["aggregate"] for row in reviews]
    completed = sum(row["scope"]["completed_matches"] for row in reviews)
    alpha_clubs = alpha["clubs"]
    rated = [
        row
        for row in alpha_clubs
        if row["alpha"]["overall_alpha_ability"]["z"] is not None
    ]
    payload = {
        "version": "clubalpha_ucl_alpha_cycle_v1_1_league_strength",
        "status": "provisional_research_uncalibrated",
        "as_of": args.as_of,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "competition": "Champions League",
        "season": "2026/2027",
        "completed_evidence": {
            "matchdays": sorted(int(row["matchday"]) for row in reviews),
            "matches": completed,
            "goals": sum(int(row["goals"]) for row in aggregates),
            "total_xg": round(sum(float(row["total_xg"]) for row in aggregates), 2),
            "home_wins": sum(int(row["home_wins"]) for row in aggregates),
            "draws": sum(int(row["draws"]) for row in aggregates),
            "away_wins": sum(int(row["away_wins"]) for row in aggregates),
            "over_2_5": sum(int(row["over_2_5"]) for row in aggregates),
            "score_xg_winner_alignment": sum(
                int(row["score_xg_winner_alignment"]) for row in aggregates
            ),
            "alpha_minute_coverage_by_matchday": [
                {
                    "matchday": int(row["matchday"]),
                    "coverage": row["player_alpha"]["actual_minute_coverage"],
                    "rating_alpha_correlation": row["player_alpha"][
                        "rating_alpha_correlation"
                    ],
                }
                for row in sorted(reviews, key=lambda item: item["matchday"])
            ],
        },
        "domestic_evidence": {
            "as_of": domestic_coverage["as_of"],
            "competitions": domestic_coverage["counts"]["competitions"],
            "foreign_ucl_clubs": domestic_coverage["counts"]["target_teams"],
            "completed_matches": domestic_coverage["counts"][
                "finished_selected_fixtures"
            ],
            "matches_with_player_detail": domestic_coverage["counts"][
                "matches_with_target_player_stats"
            ],
            "player_detail_coverage_pct": domestic_coverage["counts"][
                "target_player_detail_coverage_pct"
            ],
            "player_match_rows": domestic_coverage["counts"]["match_player_rows"],
            "league_strength_application": league_strength.get("application"),
            "league_strength_offsets_used": league_strength.get("offsets_used"),
        },
        "projected_xi_alpha": {
            "clubs": len(alpha_clubs),
            "rated_clubs": len(rated),
            "unrated_clubs": [
                row["team"] for row in alpha_clubs if row not in rated
            ],
            "top_clubs": [
                {
                    "rank": row["rank"],
                    "team": row["team"],
                    "grade": row["display_grade"],
                    "strength_index": row["league_relative_strength_index"],
                    "alpha_z": row["alpha"]["overall_alpha_ability"]["z"],
                    "coverage": row["alpha"]["overall_alpha_ability"]["coverage"],
                }
                for row in rated[:10]
            ],
        },
        "upcoming": {
            "matchday": args.matchday,
            "fixtures": len(predictions),
            "simulations": len(predictions) * 50000,
            "predictions": predictions,
            "summary": {
                "side_research_candidates": sum(
                    row["side_research_candidate"]["call"] != "pass"
                    for row in predictions
                ),
                "side_passes": sum(
                    row["side_research_candidate"]["call"] == "pass"
                    for row in predictions
                ),
                "total_research_candidates": sum(
                    row["total_research_candidate"]["call"] != "pass"
                    for row in predictions
                ),
                "total_passes": sum(
                    row["total_research_candidate"]["call"] == "pass"
                    for row in predictions
                ),
            },
        },
        "integrity": {
            "same_player_alpha_formulas_as_premier_league": True,
            "same_squad_selection_policy_as_premier_league": True,
            "same_60_30_10_foundation": True,
            "club_form_league_strength_adjusted": True,
            "ucl_calibration_separate": True,
            "ucl_specific_calibration_available": False,
            "retroactive_prediction_record_created": False,
            "research_candidates_are_promoted_calls": False,
            "capital_deployment_ready": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "completed_matches": completed,
                "rated_clubs": len(rated),
                **payload["upcoming"]["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
