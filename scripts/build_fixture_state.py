#!/usr/bin/env python3
"""Build Fixture State v1 from Clubalpha's three intelligence foundations."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fixture_state import build_fixture_states  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    return len(materialized)


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"minimum": None, "mean": None, "maximum": None}
    return {
        "minimum": round(min(values), 4),
        "mean": round(statistics.mean(values), 4),
        "maximum": round(max(values), 4),
    }


def build_audit(
    states: list[dict[str, Any]],
    config: dict[str, Any],
    historical_config: dict[str, Any],
) -> dict[str, Any]:
    flags = Counter(flag for state in states for flag in state["quality_flags"])
    scopes = Counter(str(state["fixture"].get("source_scope")) for state in states)

    def side_values(field: str) -> list[float]:
        return [float(state[side][field]) for state in states for side in ("home", "away")]

    def component_values(component: str) -> list[float]:
        return [
            float(state[side]["components"][component]["effective_signal_z"])
            for state in states
            for side in ("home", "away")
        ]

    examples = []
    for state in states[:12]:
        examples.append(
            {
                "match_id": state["fixture"]["match_id"],
                "kickoff_utc": state["fixture"]["kickoff_utc"],
                "fixture": (
                    f"{state['fixture']['home_team']} vs "
                    f"{state['fixture']['away_team']}"
                ),
                "competition_baseline_xg": state["goal_engine_input"][
                    "competition_baseline"
                ],
                "home_fixture_signal_z": state["home"]["fixture_signal_z"],
                "away_fixture_signal_z": state["away"]["fixture_signal_z"],
                "home_contributions_z": state["home"]["weighted_contributions_z"],
                "away_contributions_z": state["away"]["weighted_contributions_z"],
                "home_evidence_confidence": state["home"]["evidence_confidence"],
                "away_evidence_confidence": state["away"]["evidence_confidence"],
                "lineup_priors_complete": state["decision_boundaries"][
                    "lineup_priors_complete"
                ],
                "quality_flags": state["quality_flags"],
            }
        )

    return {
        "fixture_state_version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": states[0]["as_of"] if states else None,
        "counts": {
            "fixtures": len(states),
            "fixture_scopes": dict(sorted(scopes.items())),
            "walk_forward_input_ready": sum(
                state["decision_boundaries"][
                    "input_ready_for_walk_forward_calibration"
                ]
                for state in states
            ),
            "lineup_priors_complete": sum(
                state["decision_boundaries"]["lineup_priors_complete"]
                for state in states
            ),
            "fixture_specific_lineups": sum(
                state["decision_boundaries"]["lineups_fixture_specific"]
                for state in states
            ),
            "competition_xg_baselines": sum(
                state["goal_engine_input"]["competition_baseline"]["home_xg"]
                is not None
                and state["goal_engine_input"]["competition_baseline"]["away_xg"]
                is not None
                for state in states
            ),
            "calibrated_goal_outputs": sum(
                state["goal_engine_input"]["home_calibrated_xg"] is not None
                for state in states
            ),
        },
        "signal_distributions": {
            "fixture_signal_z": _summary(side_values("fixture_signal_z")),
            "evidence_confidence": _summary(side_values("evidence_confidence")),
            "club_form_effective_z": _summary(component_values("club_form")),
            "player_quality_lineup_effective_z": _summary(
                component_values("player_quality_lineup")
            ),
            "historical_residual_effective_z": _summary(
                component_values("historical_residual")
            ),
        },
        "quality_flags": dict(sorted(flags.items())),
        "examples": examples,
        "decision_boundaries": {
            **config["decision_boundaries"],
            "competition_baseline_outside_component_weights": True,
            "club_form_source_confidence_applied_once": True,
            "direct_history_maximum_complete_signal_share": round(
                config["component_weights"]["historical_residual"]
                * historical_config["direct_history"]["maximum_signal_share"],
                4,
            ),
            "missing_component_weight_redistributed": False,
            "calibration_coefficient_fitted": False,
        },
        "warnings": [
            "Fixture State is an auditable calibration input, not a probability or wager.",
            "Club Form v1 released z-scores already contain reliability shrinkage and are not shrunk a second time.",
            "Player Quality changes the fixture only through availability-adjusted expected minutes versus each club's baseline XI.",
            "Squad Selection Prior v1 is dated but not fixture-specific or confirmed.",
            "Historical Context contributes only venue and capped direct-matchup residuals.",
            "Competition xG is a separate starting environment and does not consume any of the 60/30/10 weights.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/fixture-state-v1.json"
    )
    parser.add_argument(
        "--club-form",
        type=Path,
        default=ROOT / "data/processed/club_form/club_form.jsonl",
    )
    parser.add_argument(
        "--selection-prior",
        type=Path,
        default=ROOT
        / "data/processed/squad_selection_prior/squad_selection_prior.jsonl",
    )
    parser.add_argument(
        "--historical-fixtures",
        type=Path,
        default=ROOT
        / "data/processed/historical_fixtures_v2/historical_fixture_intelligence.jsonl",
    )
    parser.add_argument(
        "--scored-history",
        type=Path,
        default=ROOT
        / "data/processed/historical_fixtures_v2/scored_history_observations.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/fixture_state",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/fixture-state-v1-audit.json",
    )
    args = parser.parse_args()

    config = load_json(args.config)
    historical_config = load_json(ROOT / config["historical_fixtures_config"])

    print("[1/4] Load the three dated intelligence foundations")
    club_forms = load_jsonl(args.club_form)
    selection_priors = load_jsonl(args.selection_prior)
    historical_fixtures = load_jsonl(args.historical_fixtures)
    history_rows = load_jsonl(args.scored_history)

    print("[2/4] Build confidence-aware 60/30/10 fixture states")
    states = build_fixture_states(
        historical_fixtures,
        club_forms,
        selection_priors,
        history_rows,
        config,
        historical_config,
    )

    print("[3/4] Materialize ignored dated fixture inputs")
    count = write_jsonl(args.output_dir / "fixture_states.jsonl", states)
    write_json(
        args.output_dir / "manifest.json",
        {
            "fixture_state_version": config["version"],
            "as_of": states[0]["as_of"] if states else None,
            "source_versions": config["source_versions"],
            "component_weights": config["component_weights"],
            "outputs": {"fixture_states": count},
            "decision_boundaries": config["decision_boundaries"],
        },
    )

    print("[4/4] Write tracked audit")
    audit = build_audit(states, config, historical_config)
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
