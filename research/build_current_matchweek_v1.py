#!/usr/bin/env python3
"""Build a dated, fixture-specific Premier League shadow baseline.

This runner reuses the locked component scales and goal model.  It refreshes
only the pre-match football inputs: Club Form, the v2 projected XI, Player
Alpha, and Historical Fixtures.  Context and fixture calibration remain
separate downstream layers so every change stays auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fixture_state import historical_residuals  # noqa: E402
from clubalpha.prediction_lab import build_prediction_slate  # noqa: E402


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
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    """Store portable repository paths whenever the input lives under root."""

    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def lineup_inputs(alpha_club: dict[str, Any]) -> tuple[float, float]:
    alpha = alpha_club["alpha"]["overall_alpha_ability"]
    quality = float(alpha["z"])
    coverage = float(alpha.get("coverage") or 0.0)
    weighted_matches = float(
        (alpha_club.get("evidence") or {}).get("weighted_matches") or 0.0
    )
    maturity = weighted_matches / (weighted_matches + 2.0) if weighted_matches else 0.0
    return quality, coverage * maturity


def build_state(
    fixture: dict[str, Any],
    home_form: dict[str, Any],
    away_form: dict[str, Any],
    home_alpha: dict[str, Any],
    away_alpha: dict[str, Any],
    historical: dict[str, Any],
    scored_history: list[dict[str, Any]],
    as_of: date,
    fixture_config: dict[str, Any],
    historical_config: dict[str, Any],
) -> dict[str, Any]:
    history = historical_residuals(
        historical,
        scored_history,
        historical_config,
        as_of,
        rows_validated=True,
    )
    home_quality, home_confidence = lineup_inputs(home_alpha)
    away_quality, away_confidence = lineup_inputs(away_alpha)
    home_lineup = home_quality * home_confidence - away_quality * away_confidence
    away_lineup = -home_lineup
    baseline = historical["competition_baseline"]["expected_goals"]

    def side(
        form_signal: float,
        lineup_signal: float,
        history_side: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "components": {
                "club_form": {"effective_signal_z": round(form_signal, 6)},
                "player_quality_lineup": {
                    "effective_signal_z": round(lineup_signal, 6)
                },
                "historical_residual": {
                    "effective_signal_z": float(history_side["effective_signal_z"])
                },
            }
        }

    return {
        "fixture_state_version": fixture_config["version"],
        "as_of": as_of.isoformat(),
        "fixture": fixture,
        "component_weights": fixture_config["component_weights"],
        "home": side(
            float(home_form["attack_z"]) - float(away_form["defense_z"]),
            home_lineup,
            history["home"],
        ),
        "away": side(
            float(away_form["attack_z"]) - float(home_form["defense_z"]),
            away_lineup,
            history["away"],
        ),
        "goal_model_handoff": {
            "competition_baseline": {
                "competition_family": "premier_league",
                "home_xg": baseline["home_mean"],
                "away_xg": baseline["away_mean"],
            }
        },
        "decision_boundaries": {
            "raw_components_ready_for_scale_fitting": True,
            "lineup_priors_complete": True,
            "lineups_fixture_specific": True,
            "lineups_confirmed": False,
            "probability_ready": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": sorted(
            set(
                [
                    "current_matchweek_shadow",
                    "lineup_not_confirmed",
                    "player_alpha_attached_after_xi_projection",
                    "team_research_beliefs_not_automatically_applied",
                    *list(historical.get("quality_flags") or []),
                    *list(home_alpha.get("quality_flags") or []),
                    *list(away_alpha.get("quality_flags") or []),
                ]
            )
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=ROOT / "data/processed/foundation/fixtures.jsonl",
    )
    parser.add_argument(
        "--club-form",
        type=Path,
        default=ROOT / "data/processed/club_form/club_form.jsonl",
    )
    parser.add_argument("--premier-league-alpha", type=Path, required=True)
    parser.add_argument(
        "--historical-fixtures",
        type=Path,
        default=(
            ROOT
            / "data/processed/historical_fixtures_v2/"
            "historical_fixture_intelligence.jsonl"
        ),
    )
    parser.add_argument(
        "--scored-history",
        type=Path,
        default=(
            ROOT
            / "data/processed/historical_fixtures_v2/"
            "scored_history_observations.jsonl"
        ),
    )
    parser.add_argument(
        "--component-scales",
        type=Path,
        default=ROOT / "artifacts/prediction_lab/2026-08-24/component-scales.json",
    )
    parser.add_argument(
        "--goal-model",
        type=Path,
        default=ROOT / "artifacts/prediction_lab/2026-08-24/goal-model.json",
    )
    parser.add_argument(
        "--prediction-config",
        type=Path,
        default=ROOT / "config/prediction-lab-v0.json",
    )
    parser.add_argument(
        "--fixture-config",
        type=Path,
        default=ROOT / "config/fixture-state-v1.json",
    )
    parser.add_argument(
        "--historical-config",
        type=Path,
        default=ROOT / "config/historical-fixtures-v2.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite dated slate: {args.output_dir}")
    as_of = date.fromisoformat(args.as_of)
    fixtures = [
        row
        for row in load_jsonl(args.fixtures)
        if row.get("source_scope") == "premier_league_current"
        and int(row.get("round") or -1) == args.round
        and not row.get("finished")
        and not row.get("cancelled")
        and str(row.get("kickoff_utc") or "")[:10] > args.as_of
    ]
    if len(fixtures) != 10:
        raise ValueError(
            f"expected ten future Premier League fixtures in round {args.round}; "
            f"found {len(fixtures)}"
        )

    forms = {row["team"]: row for row in load_jsonl(args.club_form)}
    alpha_report = load_json(args.premier_league_alpha)
    if alpha_report.get("as_of") != args.as_of:
        raise ValueError("projected-XI Alpha snapshot date does not match slate date")
    alpha = {row["team"]: row for row in alpha_report["clubs"]}
    historical_rows = load_jsonl(args.historical_fixtures)
    historical = {int(row["fixture"]["match_id"]): row for row in historical_rows}
    scored_history = load_jsonl(args.scored_history)
    scale_artifact = load_json(args.component_scales)
    goal_artifact = load_json(args.goal_model)
    prediction_config = load_json(args.prediction_config)
    fixture_config = load_json(args.fixture_config)
    historical_config = load_json(args.historical_config)

    states = []
    for fixture in fixtures:
        match_id = int(fixture["match_id"])
        home = fixture["home_team"]
        away = fixture["away_team"]
        if match_id not in historical:
            raise ValueError(f"missing historical intelligence for match {match_id}")
        for team in (home, away):
            if team not in forms or team not in alpha:
                raise ValueError(f"missing current team input for {team}")
            projected_match_id = int(alpha[team]["next_fixture"]["match_id"])
            if projected_match_id != match_id:
                raise ValueError(
                    f"projected XI for {team} targets {projected_match_id}, "
                    f"not round fixture {match_id}"
                )
        states.append(
            build_state(
                fixture,
                forms[home],
                forms[away],
                alpha[home],
                alpha[away],
                historical[match_id],
                scored_history,
                as_of,
                fixture_config,
                historical_config,
            )
        )

    predictions = build_prediction_slate(
        states,
        scale_artifact,
        goal_artifact,
        prediction_config,
    )
    summary = []
    for row in predictions:
        probabilities = row["probabilities"]
        summary.append(
            {
                "match_id": row["fixture"]["match_id"],
                "fixture": (
                    f"{row['fixture']['home_team']} vs "
                    f"{row['fixture']['away_team']}"
                ),
                "predicted_xg": row["predicted_xg"],
                "probability_leader": max(
                    ("home_win", "draw", "away_win"),
                    key=lambda key: float(probabilities[key]),
                ),
                "probabilities": {
                    key: probabilities[key]
                    for key in ("home_win", "draw", "away_win")
                },
                "over_2_5": probabilities["over"]["2.5"],
                "btts_yes": probabilities["btts_yes"],
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "predictions.jsonl", predictions)
    write_json(
        args.output_dir / "report.json",
        {
            "version": "clubalpha_current_matchweek_v1",
            "status": "shadow_only",
            "as_of": args.as_of,
            "round": args.round,
            "fixtures": len(predictions),
            "simulations_per_fixture": prediction_config["simulation"]["draws"],
            "summary": summary,
            "decision_boundaries": {
                "locked_60_30_10_preserved": True,
                "player_alpha_selects_xi": False,
                "research_beliefs_applied": False,
                "probability_validated": False,
                "market_ready": False,
                "capital_deployment_ready": False,
            },
        },
    )
    input_paths = {
        "fixtures": args.fixtures,
        "club_form": args.club_form,
        "premier_league_alpha": args.premier_league_alpha,
        "historical_fixtures": args.historical_fixtures,
        "scored_history": args.scored_history,
        "component_scales": args.component_scales,
        "goal_model": args.goal_model,
        "prediction_config": args.prediction_config,
        "fixture_config": args.fixture_config,
        "historical_config": args.historical_config,
    }
    write_json(
        args.output_dir / "manifest.json",
        {
            "version": "clubalpha_current_matchweek_manifest_v1",
            "as_of": args.as_of,
            "round": args.round,
            "inputs": {
                key: {"path": display_path(path), "sha256": sha256(path)}
                for key, path in input_paths.items()
            },
            "outputs": {
                "predictions": sha256(args.output_dir / "predictions.jsonl"),
                "report": sha256(args.output_dir / "report.json"),
            },
        },
    )
    print(
        json.dumps(
            {
                "output": str(args.output_dir),
                "fixtures": len(predictions),
                "simulations": len(predictions)
                * int(prediction_config["simulation"]["draws"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
