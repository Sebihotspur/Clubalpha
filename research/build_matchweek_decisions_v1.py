#!/usr/bin/env python3
"""Build selective provisional or final shadow decisions for one matchweek."""

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

from clubalpha.decision_policy import (  # noqa: E402
    evaluate_side,
    evaluate_total,
    refresh_gate,
)
from clubalpha.fixture_calibration import calibrate_fixture_forecast  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--stage", choices=("provisional", "final"), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--contextual", type=Path, required=True)
    parser.add_argument("--prematch-load", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument(
        "--calibration-config",
        type=Path,
        default=ROOT / "config/fixture-calibration-v1.json",
    )
    parser.add_argument(
        "--decision-config",
        type=Path,
        default=ROOT / "config/decision-policy-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite decision packet: {args.output}")
    baseline_rows = load_jsonl(args.baseline)
    contextual_rows = load_jsonl(args.contextual)
    load = load_json(args.prematch_load)
    calibration = load_json(args.calibration)
    calibration_config = load_json(args.calibration_config)
    decision_config = load_json(args.decision_config)
    baseline_by_id = {
        int(row["fixture"]["match_id"]): row for row in baseline_rows
    }
    contextual_by_id = {
        int(row["fixture"]["match_id"]): row for row in contextual_rows
    }
    if set(baseline_by_id) != set(contextual_by_id) or len(baseline_by_id) != 10:
        raise ValueError("baseline and contextual slates must reconcile to ten fixtures")
    if any(int(row["fixture"]["round"]) != args.round for row in baseline_rows):
        raise ValueError("decision packet contains a different matchweek round")
    if any(str(row.get("as_of")) != args.as_of for row in baseline_rows):
        raise ValueError("baseline as-of date does not match decision packet")

    fixture_teams = {
        team
        for row in baseline_rows
        for team in (row["fixture"]["home_team"], row["fixture"]["away_team"])
    }
    refresh = refresh_gate(
        load,
        fixture_teams,
        stage=args.stage,
        config=decision_config,
    )
    decisions = []
    for match_id in sorted(
        baseline_by_id,
        key=lambda value: (
            baseline_by_id[value]["fixture"]["kickoff_utc"], value
        ),
    ):
        baseline = baseline_by_id[match_id]
        contextual = contextual_by_id[match_id]
        context_model = contextual["contextual"]
        calibrated = calibrate_fixture_forecast(
            {
                "fixture": contextual["fixture"],
                "predicted_xg": context_model["predicted_xg"],
                "probabilities": context_model["probabilities"],
            },
            calibration,
            calibration_config,
        )
        side = evaluate_side(baseline, contextual, calibrated, decision_config)
        total = evaluate_total(calibrated, decision_config)
        fixture = contextual["fixture"]
        decisions.append(
            {
                "match_id": match_id,
                "fixture": f"{fixture['home_team']} vs {fixture['away_team']}",
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "calibrated_predicted_xg": calibrated["predicted_xg"],
                "calibrated_probabilities": calibrated["probabilities"],
                "side_decision": side,
                "total_decision": total,
                "final_call_eligible": refresh["final_call_eligible"],
            }
        )

    payload = {
        "version": "clubalpha_matchweek_decisions_v1",
        "status": f"{args.stage}_shadow",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": args.as_of,
        "round": args.round,
        "refresh_gate": refresh,
        "fixtures": decisions,
        "summary": {
            "side_calls": sum(
                row["side_decision"]["call"] != "pass" for row in decisions
            ),
            "side_passes": sum(
                row["side_decision"]["call"] == "pass" for row in decisions
            ),
            "totals_calls": sum(
                row["total_decision"]["call"] != "pass" for row in decisions
            ),
            "totals_passes": sum(
                row["total_decision"]["call"] == "pass" for row in decisions
            ),
            "capital_deployment_ready": False,
        },
        "provenance": {
            display_path(path): sha256(path)
            for path in (
                args.baseline,
                args.contextual,
                args.prematch_load,
                args.calibration,
                args.calibration_config,
                args.decision_config,
            )
        },
        "locked_boundaries": decision_config["locked_boundaries"],
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
                "stage": args.stage,
                "side_calls": payload["summary"]["side_calls"],
                "totals_calls": payload["summary"]["totals_calls"],
                "final_call_eligible": refresh["final_call_eligible"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
