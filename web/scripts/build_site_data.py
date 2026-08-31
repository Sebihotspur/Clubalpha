#!/usr/bin/env python3
"""Build the static Clubalpha website payload from frozen model artifacts."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.official_shadow import score_results, validate_predictions  # noqa: E402
from clubalpha.round_robin_archive import validate_results  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts/prediction_lab/2026-08-24"
STYLE_MATCHUP_ARTIFACT = ROOT / "artifacts/style_matchup/2026-08-25/style-matchups.json"
ROUND_ROBIN_DIR = ROOT / "artifacts/round_robin/2026-08-25"
CONTEXTUAL_DIR = ROOT / "artifacts/contextual_interaction/2026-08-26"
OFFICIAL_DIR = ROOT / "artifacts/official_shadow/2026-08-31-mw3"
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
    round_robin_results = load_jsonl(ROUND_ROBIN_DIR / "results.jsonl")
    contextual_report = load_json(CONTEXTUAL_DIR / "report.json")
    contextual_predictions = load_jsonl(CONTEXTUAL_DIR / "predictions.jsonl")
    official_report = load_json(OFFICIAL_DIR / "report.json")
    official_predictions = load_jsonl(OFFICIAL_DIR / "predictions.jsonl")
    official_results = load_jsonl(OFFICIAL_DIR / "results.jsonl")
    if contextual_report["decision_boundaries"]["capital_deployment_ready"]:
        raise ValueError("website refuses capital-ready contextual shadow data")
    if contextual_report["method"]["archetype_labels_used_in_math"]:
        raise ValueError("website refuses context that uses archetype labels in math")
    official_validation = validate_predictions(
        official_predictions,
        expected_round=int(official_report["round"]),
        expected_fixtures=10,
        as_of_utc=official_report["as_of_utc"],
    )
    official_score = score_results(official_predictions, official_results)
    result_validation = validate_results(
        round_robin_predictions, round_robin_results
    )

    official_web_predictions = []
    for row in official_predictions:
        fixture = row["fixture"]
        match_id = int(fixture["match_id"])
        model = row["model"]
        probabilities = model["probabilities"]
        home_direction = model["context"]["home_attack"]
        away_direction = model["context"]["away_attack"]
        official_web_predictions.append(
            {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "baseline": {"predicted_xg": model["base_predicted_xg"]},
                "predicted_xg": model["predicted_xg"],
                "probabilities": probabilities,
                "top_scoreline": model["most_likely_scorelines"][0]["score"],
                "official_pick": row["official_pick"],
                "translation_audit": row["translation_audit"],
                "research_lens": row["research_lens"],
                "verdict": model["context"]["verdict"],
                "goal_environment": model["context"]["goal_environment"],
                "directions": {
                    "home": {
                        "archetype": home_direction["attacker_archetype"],
                        "preferred_route": home_direction["preferred_route"]["label"],
                        "signal": home_direction["continuous_signal"],
                        "reliability": home_direction["combined_reliability"],
                        "xg_multiplier": home_direction["xg_multiplier"],
                    },
                    "away": {
                        "archetype": away_direction["attacker_archetype"],
                        "preferred_route": away_direction["preferred_route"]["label"],
                        "signal": away_direction["continuous_signal"],
                        "reliability": away_direction["combined_reliability"],
                        "xg_multiplier": away_direction["xg_multiplier"],
                    },
                },
                "status": "pending",
                "quality_flags": row["quality_flags"],
            }
        )
    official_web_predictions.sort(
        key=lambda row: (row["kickoff_utc"], row["match_id"])
    )
    featured_match_id = int(official_report["featured_match_id"])
    featured = next(
        row
        for row in official_web_predictions
        if row["match_id"] == featured_match_id
    )
    featured_pick = featured["official_pick"]
    promotion_gate = official_report["promotion_gate"]
    hit_rate = official_score["hit_rate"]
    review_ready = (
        official_score["settled"] >= promotion_gate["minimum_settled_fixtures"]
        and hit_rate is not None
        and hit_rate > promotion_gate["threshold_exclusive"]
    )

    # Preserve the original Prediction Lab and Holy Grail records exactly as
    # published. The official Matchweek 3 slate is a new scoring stream, not a
    # rewrite of either earlier experiment.
    by_match = {int(row["match_id"]): row for row in report["next_round"]}
    original_pick_match_id = 5795429
    legacy_predictions = []
    for row in predictions:
        fixture = row["fixture"]
        match_id = int(fixture["match_id"])
        context = by_match[match_id]
        probabilities = row["probabilities"]
        legacy_predictions.append(
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
                "official_pick": match_id == original_pick_match_id,
                "status": "pending",
            }
        )

    baseline_match_ids = {row["match_id"] for row in legacy_predictions}
    contextual_match_ids = {
        int(row["fixture"]["match_id"]) for row in contextual_predictions
    }
    if contextual_match_ids != baseline_match_ids:
        raise ValueError("contextual and baseline website slates do not reconcile")

    holy_grail_predictions = []
    for row in contextual_predictions:
        fixture = row["fixture"]
        match_id = int(fixture["match_id"])
        base = row["baseline"]
        context = row["contextual"]
        probabilities = context["probabilities"]
        home_direction = row["directional_context"]["home_attack"]
        away_direction = row["directional_context"]["away_attack"]
        holy_grail_predictions.append(
            {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "baseline": {
                    "predicted_xg": base["predicted_xg"],
                    "probabilities": {
                        "home_win": base["probabilities"]["home_win"],
                        "draw": base["probabilities"]["draw"],
                        "away_win": base["probabilities"]["away_win"],
                        "over_2_5": base["probabilities"]["over"]["2.5"],
                        "btts_yes": base["probabilities"]["btts_yes"],
                    },
                },
                "predicted_xg": context["predicted_xg"],
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
                "probability_change": row["change"]["probabilities"],
                "xg_change": row["change"]["predicted_xg"],
                "favorite": row["context_read"]["base_favorite"],
                "favorite_probability_delta": row["context_read"][
                    "favorite_probability_delta"
                ],
                "verdict": row["context_read"]["verdict"],
                "goal_environment": row["context_read"]["goal_environment"],
                "top_scoreline": context["most_likely_scorelines"][0]["score"],
                "directions": {
                    "home": {
                        "archetype": home_direction["attacker_archetype"],
                        "preferred_route": home_direction["preferred_route"]["label"],
                        "signal": home_direction["continuous_signal"],
                        "reliability": home_direction["combined_reliability"],
                        "xg_multiplier": home_direction["xg_multiplier"],
                    },
                    "away": {
                        "archetype": away_direction["attacker_archetype"],
                        "preferred_route": away_direction["preferred_route"]["label"],
                        "signal": away_direction["continuous_signal"],
                        "reliability": away_direction["combined_reliability"],
                        "xg_multiplier": away_direction["xg_multiplier"],
                    },
                },
                "quality_flags": row["quality_flags"],
            }
        )
    holy_grail_predictions.sort(
        key=lambda row: (row["kickoff_utc"], row["match_id"])
    )
    original_pick = next(
        row for row in legacy_predictions if row["official_pick"]
    )
    original_fair_decimal = 1.0 / original_pick["probabilities"]["over_2_5"]

    site = {
        "meta": {
            "site_version": "clubalpha_web_v0_3_official_mw3",
            "prediction_version": official_report["report_version"],
            "as_of": official_report["as_of_utc"],
            "generated_at_utc": official_report["as_of_utc"],
            "context_as_of": "2026-08-26",
            "context_version": contextual_report["report_version"],
            "simulations": 50000,
            "fixture_count": len(official_web_predictions),
            "scale_training_sides": report["counts"]["scale_training_fixture_sides"],
            "scale_validation_sides": 200,
            "goal_training_matches": report["counts"]["goal_training_matches"],
            "goal_validation_matches": 100,
        },
        "official_shadow_pick": {
            "match_id": original_pick_match_id,
            "fixture": f"{original_pick['home_team']} vs {original_pick['away_team']}",
            "kickoff_utc": original_pick["kickoff_utc"],
            "market": "Over 2.5 total goals",
            "model_probability": original_pick["probabilities"]["over_2_5"],
            "fair_decimal": round(original_fair_decimal, 3),
            "minimum_price": 1.80,
            "shadow_units": 0.25,
            "real_units": 0.0,
            "reasons": [
                {"value": "3 / 3", "label": "Intelligence layers favor City"},
                {
                    "value": f"{original_pick['predicted_xg']['total']:.2f}",
                    "label": "Projected total xG",
                },
                {
                    "value": f"{original_pick['probabilities']['btts_yes'] * 100:.1f}%",
                    "label": "Both teams to score",
                },
            ],
        },
        "featured_official_pick": {
            "match_id": featured_match_id,
            "fixture": f"{featured['home_team']} vs {featured['away_team']}",
            "kickoff_utc": featured["kickoff_utc"],
            "market": featured_pick["primary_read"],
            "model_probability": featured_pick["model_probability"],
            "confidence": featured_pick["confidence"],
            "secondary_read": featured_pick["secondary_read"],
            "projected_xg": featured["predicted_xg"],
            "real_units": 0.0,
            "reasons": [
                {"value": "HIGH", "label": "Official conviction"},
                {"value": f"{featured['predicted_xg']['home']:.2f}", "label": "City projected xG"},
                {"value": "10 / 10", "label": "Fixtures frozen"},
            ],
        },
        "predictions": legacy_predictions,
        "official_slate": {
            "report_version": official_report["report_version"],
            "status": official_report["status"],
            "round": official_report["round"],
            "as_of": official_report["as_of_utc"],
            "fixtures": len(official_web_predictions),
            "validation": official_validation,
            "predictions": official_web_predictions,
        },
        "holy_grail": {
            "name": "Holy Grail v1",
            "status": contextual_report["status"],
            "as_of": "2026-08-26",
            "fixtures": contextual_report["fixtures"],
            "simulations_per_fixture": contextual_report["method"][
                "simulations_per_fixture"
            ],
            "total_simulations": contextual_report["fixtures"]
            * contextual_report["method"]["simulations_per_fixture"],
            "base_weights": {
                "club_form": 60,
                "projected_xi_player_quality": 30,
                "historical_fixture_residual": 10,
            },
            "context_formula": (
                "contextual xG = base xG × exp(max sensitivity × "
                "directional signal × reliability)"
            ),
            "maximum_absolute_log_xg_adjustment": contextual_report["method"][
                "maximum_absolute_log_xg_adjustment"
            ],
            "archetype_labels_used_in_math": contextual_report["method"][
                "archetype_labels_used_in_math"
            ],
            "coefficient_learned": contextual_report["decision_boundaries"][
                "coefficient_learned_from_residuals"
            ],
            "capital_deployment_ready": contextual_report["decision_boundaries"][
                "capital_deployment_ready"
            ],
            "predictions": holy_grail_predictions,
        },
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
            "status": "official_shadow_collection",
            "matches_logged": official_score["settled"],
            "sample_gate": promotion_gate["minimum_settled_fixtures"],
            "hits": official_score["hits"],
            "misses": official_score["misses"],
            "pending": official_score["pending"],
            "hit_rate": hit_rate,
            "hit_rate_gate": promotion_gate["threshold_exclusive"],
            "review_ready": review_ready,
            "next_stage": promotion_gate["next_stage"],
            "capital_deployment_ready": False,
            "scorecards": [
                "Official 1X2 hit rate above 50%",
                "Minimum 30 settled official fixtures",
                "1X2 Brier + log loss",
                "Expected-goals MAE",
                "Totals calibration",
                "Closing-line value",
                "Lineup evidence coverage",
            ],
        },
        "historical_ledger": {
            "status": "shadow_collection",
            "matches_logged": result_validation["results"],
            "sample_gate": 100,
            "capital_deployment_ready": False,
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
                "Ten latest results are tentative research evidence",
                "Official MW3 probabilities remain shadow-only",
                "Projected lineups are not confirmed starting XIs",
                "Market prices are not yet an automated model input",
                "Historical August 11 roster is reconstructed and flagged",
                "Player scorer and assist heads remain deferred",
                "Style Matchup v0 is a zero-weight research challenger",
                "Holy Grail context sensitivity is not yet learned from residuals",
            ],
        },
    }

    data_dir = PUBLIC_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "site.json").write_text(
        json.dumps(site, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for route in (
        "predictions",
        "holy-grail",
        "matchups",
        "ledger",
        "methodology",
    ):
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
                "fixtures": payload["official_slate"]["fixtures"],
                "featured_prediction": payload["featured_official_pick"]["fixture"],
            },
            indent=2,
        )
    )
