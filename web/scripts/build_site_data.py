#!/usr/bin/env python3
"""Build the static Clubalpha website payload from frozen model artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts/prediction_lab/2026-08-24"
STYLE_MATCHUP_ARTIFACT = ROOT / "artifacts/style_matchup/2026-08-25/style-matchups.json"
ROUND_ROBIN_DIR = ROOT / "artifacts/round_robin/2026-08-25"
PUBLIC_DIR = ROOT / "web/public"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build():
    report = load_json(ARTIFACT_DIR / "report.json")
    predictions = load_jsonl(ARTIFACT_DIR / "predictions.jsonl")
    style_matchup = load_json(STYLE_MATCHUP_ARTIFACT)
    round_robin_summary = load_json(ROUND_ROBIN_DIR / "summary.json")
    round_robin_predictions = load_jsonl(ROUND_ROBIN_DIR / "predictions.jsonl")
    by_match = {int(row["match_id"]): row for row in report["next_round"]}
    official_match_id = 5795429

    web_predictions = []
    for row in predictions:
        fixture = row["fixture"]
        match_id = int(fixture["match_id"])
        context = by_match[match_id]
        probabilities = row["probabilities"]
        web_predictions.append(
            {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "predicted_xg": row["predicted_xg"],
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
                "lean": context["lean"],
                "support": context["support"],
                "component_votes": context["component_votes"],
                "top_scoreline": row["most_likely_scorelines"][0]["score"],
                "official_pick": match_id == official_match_id,
                "status": "pending",
            }
        )

    official = next(row for row in web_predictions if row["official_pick"])
    fair_decimal = 1.0 / official["probabilities"]["over_2_5"]
    site = {
        "meta": {
            "site_version": "clubalpha_web_v0_1",
            "prediction_version": report["prediction_version"],
            "as_of": report["as_of"],
            "generated_at_utc": report["generated_at_utc"],
            "simulations": 50000,
            "fixture_count": len(web_predictions),
            "scale_training_sides": report["counts"]["scale_training_fixture_sides"],
            "scale_validation_sides": 200,
            "goal_training_matches": report["counts"]["goal_training_matches"],
            "goal_validation_matches": 100,
        },
        "official_shadow_pick": {
            "match_id": official_match_id,
            "fixture": f"{official['home_team']} vs {official['away_team']}",
            "kickoff_utc": official["kickoff_utc"],
            "market": "Over 2.5 total goals",
            "model_probability": official["probabilities"]["over_2_5"],
            "fair_decimal": round(fair_decimal, 3),
            "minimum_price": 1.80,
            "shadow_units": 0.25,
            "real_units": 0.0,
            "reasons": [
                {"value": "3 / 3", "label": "Intelligence layers favor City"},
                {"value": f"{official['predicted_xg']['total']:.2f}", "label": "Projected total xG"},
                {"value": f"{official['probabilities']['btts_yes'] * 100:.1f}%", "label": "Both teams to score"},
            ],
        },
        "predictions": web_predictions,
        "style_matchup": style_matchup,
        "round_robin": {
            "meta": {
                key: round_robin_summary[key]
                for key in (
                    "round_robin_version",
                    "as_of",
                    "format",
                    "teams",
                    "fixtures",
                    "matches_per_team",
                    "simulations_per_fixture",
                    "total_match_simulations",
                    "decision_boundaries",
                    "quality_flags",
                )
            },
            "league_table": round_robin_summary["league_table"],
            "fixtures": [
                {
                    "match_id": row["fixture"]["match_id"],
                    "home_team": row["fixture"]["home_team"],
                    "away_team": row["fixture"]["away_team"],
                    "predicted_xg": row["predicted_xg"],
                    "probabilities": {
                        key: row["probabilities"][key]
                        for key in ("home_win", "draw", "away_win")
                    },
                    "style_matchup": row["style_matchup"],
                }
                for row in round_robin_predictions
            ],
        },
        "ledger": {
            "status": "shadow_collection",
            "matches_logged": 0,
            "sample_gate": 100,
            "capital_deployment_ready": False,
            "scorecards": [
                "1X2 Brier + log loss",
                "Expected-goals MAE",
                "Totals calibration",
                "Closing-line value",
                "Lineup evidence coverage",
            ],
        },
        "methodology": {
            "components": [
                {
                    "name": "Club Form",
                    "weight": 60,
                    "description": "Current attack and defence, prior season plus preseason and competitive evidence, released with confidence already applied.",
                },
                {
                    "name": "Player Quality",
                    "weight": 30,
                    "description": "Expected-minute projected XI built from the locked positional Alpha Ability grades and explicit coverage.",
                },
                {
                    "name": "Historical Fixtures",
                    "weight": 10,
                    "description": "Five-season venue context and a tightly capped direct-matchup residual around the competition baseline.",
                },
            ],
            "caveats": [
                "34 of 200 component-scale sides collected",
                "10 of 100 goal-calibration matches collected",
                "Projected lineups are not confirmed starting XIs",
                "Market prices are not yet an automated model input",
                "Historical August 11 roster is reconstructed and flagged",
                "Player scorer and assist heads remain deferred",
                "Style Matchup v0 is a zero-weight research challenger",
            ],
        },
    }

    data_dir = PUBLIC_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "site.json").write_text(
        json.dumps(site, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for route in ("predictions", "matchups", "ledger", "methodology"):
        route_dir = PUBLIC_DIR / route
        route_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PUBLIC_DIR / "index.html", route_dir / "index.html")
    return site


if __name__ == "__main__":
    payload = build()
    print(
        json.dumps(
            {
                "site_version": payload["meta"]["site_version"],
                "fixtures": len(payload["predictions"]),
                "official_shadow_pick": payload["official_shadow_pick"]["fixture"],
            },
            indent=2,
        )
    )
