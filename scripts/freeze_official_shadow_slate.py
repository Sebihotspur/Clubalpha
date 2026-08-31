#!/usr/bin/env python3
"""Freeze or verify an official Premier League shadow-prediction slate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.contextual_interaction import contextualize_prediction  # noqa: E402
from clubalpha.official_shadow import (  # noqa: E402
    picked_team,
    score_results,
    validate_predictions,
)


DEFAULT_CONFIG = ROOT / "config/official-shadow-mw3-2026-08-31.json"
DEFAULT_OUTPUT = ROOT / "artifacts/official_shadow/2026-08-31-mw3"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probability_leader(probabilities: dict[str, Any]) -> str:
    return max(
        ("home_win", "draw", "away_win"),
        key=lambda key: float(probabilities[key]),
    )


def side_leader(home: float, away: float) -> str:
    return "home_win" if home >= away else "away_win"


def compact_research(team: dict[str, Any] | None) -> dict[str, Any]:
    if team is None:
        return {
            "completed_matches": 0,
            "beliefs": {},
            "lineup_reliability": None,
            "research_flags": ["round_2_result_pending_at_cutoff"],
        }
    beliefs = {}
    for key, value in team["beliefs"].items():
        beliefs[key] = {
            "multiplier": value["posterior_multiplier"],
            "confidence": value["evidence_confidence"],
            "direction": value["direction"],
            "applied_to_forecast": value["applied_to_forecast"],
        }
    return {
        "completed_matches": team["completed_matches"],
        "beliefs": beliefs,
        "lineup_reliability": team["lineup_projection"][
            "posterior_xi_reliability"
        ],
        "research_flags": team["research_flags"],
    }


def official_probability(row: dict[str, Any]) -> float:
    return float(row["model"]["probabilities"][row["official_pick"]["outcome"]])


def build_predictions(config: dict[str, Any]) -> list[dict[str, Any]]:
    inputs = {key: ROOT / value for key, value in config["inputs"].items()}
    schedule = load_json(inputs["fixture_schedule"])
    base_rows = load_jsonl(inputs["base_predictions"])
    style_snapshot = load_json(inputs["style_snapshot"])
    context_config = load_json(inputs["context_config"])
    research = load_json(inputs["research_checkpoint"])

    scheduled = [
        row
        for row in schedule["fixtures"]["allMatches"]
        if int(row["round"]) == int(config["round"])
    ]
    decisions = {int(row["match_id"]): row for row in config["decisions"]}
    if len(scheduled) != 10 or set(decisions) != {int(row["id"]) for row in scheduled}:
        raise ValueError("official decisions do not reconcile with the scheduled round")

    base_by_fixture = {
        (row["fixture"]["home_team"], row["fixture"]["away_team"]): row
        for row in base_rows
    }
    style_by_team = {row["team"]: row for row in style_snapshot["teams"]}
    research_by_team = {row["team"]: row for row in research["teams"]}
    output = []
    for scheduled_fixture in scheduled:
        match_id = int(scheduled_fixture["id"])
        home = scheduled_fixture["home"]["name"]
        away = scheduled_fixture["away"]["name"]
        decision = decisions[match_id]
        if (decision["home_team"], decision["away_team"]) != (home, away):
            raise ValueError(f"decision identity mismatch for match {match_id}")
        base = base_by_fixture[(home, away)]
        contextual = contextualize_prediction(
            base, style_by_team[home], style_by_team[away], context_config
        )
        probabilities = contextual["contextual"]["probabilities"]
        model = {
            "source_prediction_match_id": base["fixture"]["match_id"],
            "base_predicted_xg": contextual["baseline"]["predicted_xg"],
            "predicted_xg": contextual["contextual"]["predicted_xg"],
            "probabilities": {
                "home_win": probabilities["home_win"],
                "draw": probabilities["draw"],
                "away_win": probabilities["away_win"],
                "over_2_5": probabilities["over"]["2.5"],
                "under_2_5": probabilities["under"]["2.5"],
                "over_3_5": probabilities["over"]["3.5"],
                "under_3_5": probabilities["under"]["3.5"],
                "btts_yes": probabilities["btts_yes"],
            },
            "most_likely_scorelines": contextual["contextual"][
                "most_likely_scorelines"
            ],
            "fixture_intelligence": base["fixture_intelligence"],
            "context": {
                "verdict": contextual["context_read"]["verdict"],
                "goal_environment": contextual["context_read"][
                    "goal_environment"
                ],
                "home_attack": contextual["directional_context"]["home_attack"],
                "away_attack": contextual["directional_context"]["away_attack"],
            },
        }
        alpha_home = style_by_team[home]["projected_xi"]["attacking_unit"]
        alpha_away = style_by_team[away]["projected_xi"]["attacking_unit"]
        fixture_home = base["fixture_intelligence"]["home"]["fixture_signal_z"]
        fixture_away = base["fixture_intelligence"]["away"]["fixture_signal_z"]
        official_pick = {
            "outcome": decision["outcome"],
            "team": (
                home
                if decision["outcome"] == "home_win"
                else away if decision["outcome"] == "away_win" else "Draw"
            ),
            "confidence": decision["confidence"],
            "primary_read": decision["primary_read"],
            "secondary_read": decision["secondary_read"],
            "thesis": decision["thesis"],
            "override_reason": decision.get("override_reason"),
        }
        row = {
            "prediction_version": config["slate_version"],
            "status": config["status"],
            "as_of_utc": config["as_of_utc"],
            "fixture": {
                "match_id": match_id,
                "competition_id": config["competition_id"],
                "competition": config["competition"],
                "season": config["season"],
                "round": int(config["round"]),
                "kickoff_utc": scheduled_fixture["status"]["utcTime"],
                "home_team_id": int(scheduled_fixture["home"]["id"]),
                "home_team": home,
                "away_team_id": int(scheduled_fixture["away"]["id"]),
                "away_team": away,
            },
            "model": model,
            "official_pick": official_pick,
            "translation_audit": {
                "probability_leader": probability_leader(model["probabilities"]),
                "fixture_signal_leader": side_leader(fixture_home, fixture_away),
                "projected_xi_alpha_leader": side_leader(alpha_home, alpha_away),
            },
            "research_lens": {
                "checkpoint_as_of": research["as_of"],
                "learned_through_kickoff_utc": research[
                    "learned_through_kickoff_utc"
                ],
                "home": compact_research(research_by_team.get(home)),
                "away": compact_research(research_by_team.get(away)),
                "tentative_only": True,
            },
            "decision_boundaries": {
                "official_for_backtesting": True,
                "probability_validated": False,
                "market_ready": False,
                "capital_deployment_ready": False,
                "research_beliefs_applied_to_probability": False,
            },
            "quality_flags": sorted(
                set(
                    contextual["quality_flags"]
                    + ["official_shadow_not_market_ready"]
                    + (
                        ["latest_august_31_fixture_excluded_by_cutoff"]
                        if home in {"Arsenal", "Aston Villa"}
                        or away in {"Arsenal", "Aston Villa"}
                        else []
                    )
                )
            ),
        }
        row["translation_audit"]["official_overrides_probability_leader"] = (
            official_pick["outcome"]
            != row["translation_audit"]["probability_leader"]
        )
        row["official_pick"]["model_probability"] = official_probability(row)
        output.append(row)
    output.sort(key=lambda row: (row["fixture"]["kickoff_utc"], row["fixture"]["match_id"]))
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    predictions = build_predictions(config)
    validation = validate_predictions(
        predictions,
        expected_round=int(config["round"]),
        expected_fixtures=10,
        as_of_utc=config["as_of_utc"],
    )
    if args.verify:
        frozen = load_jsonl(args.output_dir / "predictions.jsonl")
        if frozen != predictions:
            raise ValueError("frozen official predictions do not reproduce")
        results = load_jsonl(args.output_dir / "results.jsonl")
        score = score_results(frozen, results)
        print(json.dumps({"validation": validation, "score": score}, indent=2))
        return 0
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite official slate: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "predictions.jsonl", predictions)
    (args.output_dir / "results.jsonl").touch()
    report = {
        "report_version": config["slate_version"],
        "status": config["status"],
        "as_of_utc": config["as_of_utc"],
        "competition": config["competition"],
        "season": config["season"],
        "round": config["round"],
        "validation": validation,
        "promotion_gate": config["promotion_gate"],
        "score": score_results(predictions, []),
        "decision_rules": [
            "one official 1X2 outcome is frozen for every scheduled fixture",
            "model probabilities remain visible when the official audit overrides them",
            "tentative research beliefs inform confidence and thesis but do not alter xG",
            "results append after full time and never mutate a prediction",
            "passing the hit-rate gate opens paper allocation and price validation only",
        ],
        "featured_match_id": 5795442,
        "capital_deployment_ready": False,
    }
    write_json(args.output_dir / "report.json", report)
    readme = f"""# Official Matchweek 3 shadow slate\n\nFrozen: {config['as_of_utc']}\n\nThis directory is Clubalpha's first full official 1X2 slate. Every fixture has\none auditable outcome pick for hit-rate scoring. Model probabilities, contextual\nroutes, the latest research checkpoint and any decision override remain visible.\n\nReal capital is not authorized. The promotion gate requires a cumulative hit\nrate above 50% after at least 30 settled official fixtures, then advances only\nto paper allocation and price validation.\n"""
    (args.output_dir / "README.md").write_text(readme, encoding="utf-8")
    inputs = {
        key: ROOT / value for key, value in config["inputs"].items()
    }
    immutable = {
        str(args.config.relative_to(ROOT)): sha256(args.config),
        "clubalpha/official_shadow.py": sha256(ROOT / "clubalpha/official_shadow.py"),
        "scripts/freeze_official_shadow_slate.py": sha256(
            ROOT / "scripts/freeze_official_shadow_slate.py"
        ),
        **{
            str(path.relative_to(ROOT)): sha256(path)
            for path in inputs.values()
        },
        str((args.output_dir / "predictions.jsonl").relative_to(ROOT)): sha256(
            args.output_dir / "predictions.jsonl"
        ),
        str((args.output_dir / "report.json").relative_to(ROOT)): sha256(
            args.output_dir / "report.json"
        ),
        str((args.output_dir / "README.md").relative_to(ROOT)): sha256(
            args.output_dir / "README.md"
        ),
    }
    manifest = {
        "archive_version": "clubalpha_official_shadow_archive_v1",
        "status": "frozen_official_shadow",
        "as_of_utc": config["as_of_utc"],
        "integrity": {"algorithm": "sha256", "hashes": immutable},
        "append_only_files": [
            str((args.output_dir / "results.jsonl").relative_to(ROOT))
        ],
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps({"output": str(args.output_dir), **validation}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
