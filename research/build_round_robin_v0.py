#!/usr/bin/env python3
"""Build a fixed-strength 380-fixture Premier League shadow round robin."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fixture_state import historical_residuals  # noqa: E402
from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_team_stats,
    league_matches,
    normalize_fixture,
)
from clubalpha.historical_fixtures import (  # noqa: E402
    build_fixture_history,
    dedupe_team_match_rows,
    score_history_rows,
)
from clubalpha.prediction_lab import simulate_fixture  # noqa: E402
from clubalpha.round_robin_archive import sha256_file  # noqa: E402
from clubalpha.style_matchup import evaluate_style_matchup  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path, *, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def input_record(role: str, path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return {"role": role, "filename": path.name, "used": False}
    return {
        "role": role,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "used": True,
    }


def cache_record(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"used": False}
    if not path.is_dir():
        raise FileNotFoundError(path)
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest_rows = [
        f"{item.relative_to(path)}:{sha256_file(item)}" for item in files
    ]
    digest = hashlib.sha256("\n".join(digest_rows).encode("utf-8")).hexdigest()
    return {
        "used": True,
        "directory_name": path.name,
        "files": len(files),
        "aggregate_sha256": digest,
    }


def current_team_rows(cache: Path | None, as_of: date) -> list[dict[str, Any]]:
    if cache is None:
        return []
    client = FotMobClient(cache, refresh=False)
    league = client.league(47, "2026/2027")
    rows: list[dict[str, Any]] = []
    for source in league_matches(league):
        fixture = normalize_fixture(source, source_scope="premier_league_current")
        if not fixture.get("finished") or str(fixture.get("kickoff_utc") or "")[:10] > as_of.isoformat():
            continue
        fixture["competition_id"] = 47
        fixture["competition"] = "Premier League"
        rows.extend(flatten_match_team_stats(client.match(int(fixture["match_id"])), fixture))
    return rows


def lineup_inputs(alpha_club: dict[str, Any]) -> tuple[float, float]:
    alpha = alpha_club["alpha"]["overall_alpha_ability"]
    quality = float(alpha["z"])
    coverage = float(alpha.get("coverage") or 0.0)
    weighted_matches = float((alpha_club.get("evidence") or {}).get("weighted_matches") or 0.0)
    maturity = weighted_matches / (weighted_matches + 2.0) if weighted_matches > 0 else 0.0
    return quality, coverage * maturity


def fixture_state(
    fixture: dict[str, Any],
    home: dict[str, Any],
    away: dict[str, Any],
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

    def side(form_signal: float, lineup_signal: float, history_side: dict[str, Any]) -> dict[str, Any]:
        return {
            "components": {
                "club_form": {"effective_signal_z": round(form_signal, 6)},
                "player_quality_lineup": {"effective_signal_z": round(lineup_signal, 6)},
                "historical_residual": {
                    "effective_signal_z": float(history_side["effective_signal_z"]),
                },
            }
        }

    return {
        "fixture_state_version": fixture_config["version"],
        "as_of": as_of.isoformat(),
        "fixture": fixture,
        "component_weights": fixture_config["component_weights"],
        "home": side(
            float(home["attack_z"]) - float(away["defense_z"]),
            home_lineup,
            history["home"],
        ),
        "away": side(
            float(away["attack_z"]) - float(home["defense_z"]),
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
            "lineups_fixture_specific": False,
            "lineups_confirmed": False,
            "probability_ready": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": [
            "fixed_strength_round_robin",
            "lineup_not_confirmed",
            "lineup_not_fixture_specific",
            "style_matchup_zero_weight",
        ],
    }


def aggregate_table(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "matches": 0.0,
            "expected_wins": 0.0,
            "expected_draws": 0.0,
            "expected_losses": 0.0,
            "expected_points": 0.0,
            "expected_goals_for": 0.0,
            "expected_goals_against": 0.0,
        }
    )
    for row in predictions:
        fixture = row["fixture"]
        probabilities = row["probabilities"]
        home = totals[fixture["home_team"]]
        away = totals[fixture["away_team"]]
        home["matches"] += 1
        away["matches"] += 1
        home["expected_wins"] += probabilities["home_win"]
        home["expected_draws"] += probabilities["draw"]
        home["expected_losses"] += probabilities["away_win"]
        away["expected_wins"] += probabilities["away_win"]
        away["expected_draws"] += probabilities["draw"]
        away["expected_losses"] += probabilities["home_win"]
        home["expected_points"] += 3 * probabilities["home_win"] + probabilities["draw"]
        away["expected_points"] += 3 * probabilities["away_win"] + probabilities["draw"]
        home["expected_goals_for"] += row["predicted_xg"]["home"]
        home["expected_goals_against"] += row["predicted_xg"]["away"]
        away["expected_goals_for"] += row["predicted_xg"]["away"]
        away["expected_goals_against"] += row["predicted_xg"]["home"]

    table = []
    for team, values in totals.items():
        matches = int(values["matches"])
        row = {
            "team": team,
            "matches": matches,
            **{
                key: round(value, 2)
                for key, value in values.items()
                if key != "matches"
            },
            "average_probabilities": {
                "win": round(values["expected_wins"] / matches, 4),
                "draw": round(values["expected_draws"] / matches, 4),
                "loss": round(values["expected_losses"] / matches, 4),
            },
        }
        row["expected_goal_difference"] = round(
            values["expected_goals_for"] - values["expected_goals_against"], 2
        )
        table.append(row)
    table.sort(
        key=lambda row: (
            -float(row["expected_points"]),
            -float(row["expected_goal_difference"]),
            row["team"],
        )
    )
    for rank, row in enumerate(table, 1):
        row["rank"] = rank
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-08-25")
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=ROOT / "data/processed/foundation",
    )
    parser.add_argument(
        "--domestic-dir",
        type=Path,
        default=ROOT / "data/processed/domestic_history",
    )
    parser.add_argument(
        "--deep-dir",
        type=Path,
        default=ROOT / "data/processed/deep_history",
    )
    parser.add_argument("--fotmob-cache", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new empty dated directory; frozen archives are never overwritten",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    if args.output_dir.exists() and (
        not args.output_dir.is_dir() or any(args.output_dir.iterdir())
    ):
        raise FileExistsError(
            f"refusing to overwrite non-empty output directory: {args.output_dir}"
        )

    input_provenance = {
        "version": "clubalpha_round_robin_input_provenance_v1",
        "as_of": as_of.isoformat(),
        "history_inputs": [
            input_record("deep_history", args.deep_dir / "match_team_stats.jsonl"),
            input_record(
                "foundation_historical",
                args.foundation_dir / "historical_match_team_stats.jsonl",
            ),
            input_record(
                "foundation_current",
                args.foundation_dir / "current_match_team_stats.jsonl",
                required=False,
            ),
            input_record(
                "domestic_history", args.domestic_dir / "match_team_stats.jsonl"
            ),
        ],
        "fotmob_cache": cache_record(args.fotmob_cache),
    }

    prediction_report = load_json(ROOT / "artifacts/prediction_lab/2026-08-24/report.json")
    alpha_report = load_json(ROOT / "reports/premier-league-alpha-snapshot-2026-08-25.json")
    style_snapshot = load_json(ROOT / "artifacts/style_matchup/2026-08-25/style-matchups.json")
    scale_artifact = load_json(ROOT / "artifacts/prediction_lab/2026-08-24/component-scales.json")
    goal_artifact = load_json(ROOT / "artifacts/prediction_lab/2026-08-24/goal-model.json")
    prediction_config = load_json(ROOT / "config/prediction-lab-v0.json")
    fixture_config = load_json(ROOT / "config/fixture-state-v1.json")
    historical_config = load_json(ROOT / "config/historical-fixtures-v2.json")
    player_config = load_json(ROOT / "config/player-quality-clubalpha-v2.json")

    history_sets = [
        load_jsonl(args.deep_dir / "match_team_stats.jsonl"),
        load_jsonl(args.foundation_dir / "historical_match_team_stats.jsonl"),
        load_jsonl(args.foundation_dir / "current_match_team_stats.jsonl", required=False),
        load_jsonl(args.domestic_dir / "match_team_stats.jsonl"),
        current_team_rows(args.fotmob_cache, as_of),
    ]
    history_rows = dedupe_team_match_rows(*history_sets)
    scored_history, _ = score_history_rows(
        history_rows,
        as_of,
        historical_config,
        player_config["league_quality"],
    )

    form_by_team = {row["team"]: row for row in prediction_report["team_scores"]}
    alpha_by_team = {row["team"]: row for row in alpha_report["clubs"]}
    style_by_team = {row["team"]: row for row in style_snapshot["teams"]}
    team_names = sorted(form_by_team)
    if set(team_names) != set(alpha_by_team) or set(team_names) != set(style_by_team):
        raise ValueError("Round-robin team universes do not match")

    predictions = []
    match_index = 0
    for home_name in team_names:
        for away_name in team_names:
            if home_name == away_name:
                continue
            match_index += 1
            home = form_by_team[home_name]
            away = form_by_team[away_name]
            fixture = {
                "match_id": 1_600_000_000 + match_index,
                "competition_id": 47,
                "competition": "Premier League",
                "source_scope": "premier_league_current",
                "season": "2026/2027",
                "round": "fixed_strength_round_robin",
                "kickoff_utc": "2026-08-26T12:00:00Z",
                "home_team_id": int(home["team_id"]),
                "home_team": home_name,
                "away_team_id": int(away["team_id"]),
                "away_team": away_name,
                "finished": False,
                "cancelled": False,
            }
            historical = build_fixture_history(
                fixture,
                scored_history,
                as_of,
                historical_config,
            )
            state = fixture_state(
                fixture,
                home,
                away,
                alpha_by_team[home_name],
                alpha_by_team[away_name],
                historical,
                scored_history,
                as_of,
                fixture_config,
                historical_config,
            )
            prediction = simulate_fixture(
                state,
                scale_artifact,
                goal_artifact,
                prediction_config,
            )
            home_style = evaluate_style_matchup(style_by_team[home_name], style_by_team[away_name])
            away_style = evaluate_style_matchup(style_by_team[away_name], style_by_team[home_name])
            prediction["style_matchup"] = {
                "composite_weight": 0,
                "home_attack_best_route": home_style["best_route"],
                "away_attack_best_route": away_style["best_route"],
            }
            predictions.append(prediction)

    table = aggregate_table(predictions)
    summary = {
        "round_robin_version": "clubalpha_fixed_strength_round_robin_v0",
        "as_of": as_of.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "format": "double_round_robin",
        "teams": len(team_names),
        "fixtures": len(predictions),
        "matches_per_team": 38,
        "simulations_per_fixture": prediction_config["simulation"]["draws"],
        "total_match_simulations": len(predictions) * prediction_config["simulation"]["draws"],
        "probability_model": {
            "fixture_components": fixture_config["component_weights"],
            "component_scales": scale_artifact["version"],
            "goal_model": goal_artifact["version"],
            "style_matchup_composite_weight": 0,
        },
        "league_table": table,
        "decision_boundaries": {
            "fixed_strength_benchmark": True,
            "probability_validated": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
        "quality_flags": [
            "current_form_held_constant_for_all_380_fixtures",
            "projected_lineups_held_constant_and_not_confirmed",
            "small_component_scale_sample",
            "small_goal_calibration_sample",
            "style_matchup_logged_but_zero_weight",
        ],
    }
    write_json(args.output_dir / "inputs.json", input_provenance)
    write_jsonl(args.output_dir / "predictions.jsonl", predictions)
    write_json(args.output_dir / "summary.json", summary)
    print(
        json.dumps(
            {
                "version": summary["round_robin_version"],
                "fixtures": len(predictions),
                "total_match_simulations": summary["total_match_simulations"],
                "leader": table[0],
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
