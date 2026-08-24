#!/usr/bin/env python3
"""Compare dated Historical Fixtures snapshots with later FotMob match detail."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import flatten_match_team_stats  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def observed_match(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    general = payload.get("general") or {}
    status = (payload.get("header") or {}).get("status") or {}
    home = general.get("homeTeam") or {}
    away = general.get("awayTeam") or {}
    fixture = {
        "match_id": int(general["matchId"]),
        "source_scope": "observed_backtest",
        "competition_id": general.get("leagueId"),
        "competition": general.get("leagueName"),
        "kickoff_utc": general.get("matchTimeUTCDate"),
        "home_team_id": int(home["id"]),
        "home_team": home.get("name"),
        "away_team_id": int(away["id"]),
        "away_team": away.get("name"),
        "score": status.get("scoreStr"),
    }
    rows = flatten_match_team_stats(payload, fixture)
    home_row = next(row for row in rows if row["venue"] == "home")
    return {
        **fixture,
        "home_goals": home_row.get("goals_for"),
        "away_goals": home_row.get("goals_against"),
        "home_xg": home_row.get("expected_goals_for"),
        "away_xg": home_row.get("expected_goals_against"),
    }


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left, right)
    )
    denominator = (
        sum((value - left_mean) ** 2 for value in left)
        * sum((value - right_mean) ** 2 for value in right)
    ) ** 0.5
    return numerator / denominator if denominator else None


def rounded_pearson(pairs: list[tuple[float, float]]) -> float | None:
    value = pearson(
        [left for left, _ in pairs], [right for _, right in pairs]
    )
    return round(value, 4) if value is not None else None


def evaluate(
    prediction_rows: list[dict[str, Any]],
    actuals: dict[int, dict[str, Any]],
    meaningful_edge: float,
) -> dict[str, Any]:
    predictions = {
        int(row["fixture"]["match_id"]): row for row in prediction_rows
    }
    fixtures: list[dict[str, Any]] = []
    for match_id, actual in sorted(
        actuals.items(), key=lambda item: str(item[1].get("kickoff_utc") or "")
    ):
        prediction = predictions.get(match_id)
        if prediction is None:
            continue
        signal = prediction["historical_signals"]
        baseline = signal["descriptive_xg_baseline"]
        if actual["home_xg"] is None or actual["away_xg"] is None:
            continue
        actual_edge = float(actual["home_xg"]) - float(actual["away_xg"])
        actual_total = float(actual["home_xg"]) + float(actual["away_xg"])
        predicted_edge = signal.get("home_edge_z")
        correct = (
            float(predicted_edge) * actual_edge > 0
            if predicted_edge is not None and actual_edge != 0
            else None
        )
        fixtures.append(
            {
                "match_id": match_id,
                "kickoff_utc": actual.get("kickoff_utc"),
                "fixture": f"{actual['home_team']} vs {actual['away_team']}",
                "score": f"{int(actual['home_goals'])}-{int(actual['away_goals'])}",
                "actual_xg": {
                    "home": actual["home_xg"],
                    "away": actual["away_xg"],
                    "total": round(actual_total, 3),
                    "home_edge": round(actual_edge, 3),
                },
                "prediction": {
                    "home_edge_z": predicted_edge,
                    "total_goal_environment_z": signal.get(
                        "total_goal_environment_z"
                    ),
                    "descriptive_xg_baseline": baseline,
                    "direct_signal_share": prediction["direct_history"][
                        "signal_share"
                    ],
                },
                "direction_correct": correct,
                "meaningful_edge": predicted_edge is not None
                and abs(float(predicted_edge)) >= meaningful_edge,
            }
        )

    directional = [row for row in fixtures if row["direction_correct"] is not None]
    meaningful = [row for row in directional if row["meaningful_edge"]]
    edge_pairs = [
        (float(row["prediction"]["home_edge_z"]), row["actual_xg"]["home_edge"])
        for row in fixtures
        if row["prediction"]["home_edge_z"] is not None
    ]
    environment_pairs = [
        (
            float(row["prediction"]["total_goal_environment_z"]),
            row["actual_xg"]["total"],
        )
        for row in fixtures
        if row["prediction"]["total_goal_environment_z"] is not None
    ]
    total_errors = [
        abs(
            float(row["prediction"]["descriptive_xg_baseline"]["total"])
            - row["actual_xg"]["total"]
        )
        for row in fixtures
        if row["prediction"]["descriptive_xg_baseline"]["total"] is not None
    ]
    side_errors: list[float] = []
    for row in fixtures:
        baseline = row["prediction"]["descriptive_xg_baseline"]
        if baseline["home"] is None or baseline["away"] is None:
            continue
        side_errors.extend(
            [
                abs(float(baseline["home"]) - row["actual_xg"]["home"]),
                abs(float(baseline["away"]) - row["actual_xg"]["away"]),
            ]
        )
    return {
        "historical_fixtures_version": prediction_rows[0][
            "historical_fixtures_version"
        ],
        "snapshot_as_of": prediction_rows[0]["as_of"],
        "metrics": {
            "evaluated_matches": len(fixtures),
            "xg_direction_correct": sum(
                row["direction_correct"] is True for row in directional
            ),
            "xg_direction_evaluable": len(directional),
            "meaningful_edge_threshold": meaningful_edge,
            "meaningful_xg_direction_correct": sum(
                row["direction_correct"] is True for row in meaningful
            ),
            "meaningful_xg_direction_evaluable": len(meaningful),
            "home_edge_z_to_actual_xg_edge_pearson": rounded_pearson(edge_pairs),
            "goal_environment_z_to_actual_total_xg_pearson": rounded_pearson(
                environment_pairs
            ),
            "descriptive_total_xg_mae": round(statistics.mean(total_errors), 4)
            if total_errors
            else None,
            "descriptive_side_xg_mae": round(statistics.mean(side_errors), 4)
            if side_errors
            else None,
        },
        "fixtures": fixtures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-dir", type=Path, required=True)
    parser.add_argument(
        "--prediction",
        action="append",
        required=True,
        help="Label=path to historical_fixture_intelligence.jsonl; repeatable",
    )
    parser.add_argument("--meaningful-edge", type=float, default=0.1)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/historical-fixtures-v2-backtest.json",
    )
    args = parser.parse_args()

    actuals = {
        int(row["match_id"]): row
        for row in (
            observed_match(path) for path in sorted(args.match_dir.glob("match_*.json"))
        )
    }
    evaluations: dict[str, Any] = {}
    for item in args.prediction:
        label, separator, raw_path = item.partition("=")
        if not separator:
            raise SystemExit("--prediction must use Label=path")
        evaluations[label] = evaluate(
            load_jsonl(Path(raw_path)), actuals, args.meaningful_edge
        )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "observed_matches": len(actuals),
        "evaluations": evaluations,
        "metric_definitions": {
            "direction": "Sign of home_edge_z versus sign of observed home xG minus away xG.",
            "meaningful_edge": "Predeclared absolute home_edge_z threshold; default 0.10.",
            "mae": "Mean absolute error against observed FotMob xG; descriptive, not calibrated probability loss.",
        },
        "warnings": [
            "Nine matches are a smoke test, not a model validation sample.",
            "These outcomes were already known from the v1 review, so the v2 comparison is not a clean out-of-sample test; no coefficient was optimized against the sample.",
            "This audit does not test odds, calibration, closing-line value, or capital deployment.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value["metrics"] for key, value in evaluations.items()}, indent=2))
    print(f"Audit: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
